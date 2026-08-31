#!/usr/bin/env python3
"""Known solc bugs for a pragma, from the compiler team's own bug list.

    python scripts/solc_bugs.py '^0.8.13'      # what can bite this pragma
    python scripts/solc_bugs.py --update       # refresh the vendored data
    python scripts/solc_bugs.py --selftest

`scan.py` calls into this. The data lives in `solc_bugs.json` next to this
file, vendored on purpose: the audit path must work with no network. `--update`
is the only code here that touches the internet.

A pragma is not a version. `^0.8.13` compiles with anything from 0.8.13 to
0.8.30, so the audit has to consider **every** version in the range — including
the buggy ones the deployer may have used. That is why a floating pragma is a
finding in its own right: the bytecode you audited is not provably the bytecode
that shipped.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "solc_bugs.json")
SRC_BUGS = "https://raw.githubusercontent.com/ethereum/solidity/develop/docs/bugs.json"
SRC_BY_VERSION = ("https://raw.githubusercontent.com/ethereum/solidity/develop"
                  "/docs/bugs_by_version.json")

VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
COMPARATOR = re.compile(r"([<>=^~]*)\s*(\d+\.\d+\.\d+)")


def parse(v):
    m = VERSION.match(str(v))
    return tuple(int(x) for x in m.groups()) if m else None


def satisfies(version, pragma):
    """Does `version` satisfy a solidity pragma expression?

    Handles the forms that actually appear: `0.8.20`, `^0.8.20`, `~0.8.20`,
    `>=0.8.0 <0.9.0`, and `||` alternatives. Anything unparseable returns
    False rather than guessing -- a wrong "safe" answer is worse than none.
    """
    v = parse(version)
    if not v:
        return False
    for alt in str(pragma).split("||"):
        clauses = COMPARATOR.findall(alt)
        if not clauses:
            continue
        ok = True
        for op, raw in clauses:
            b = parse(raw)
            if op in ("^", "~"):
                # both mean "same leading nonzero component": ^0.8.13 -> <0.9.0
                upper = (b[0], b[1] + 1, 0) if b[0] == 0 else (b[0] + 1, 0, 0)
                ok = ok and b <= v < upper
            elif op == ">=":
                ok = ok and v >= b
            elif op == ">":
                ok = ok and v > b
            elif op == "<=":
                ok = ok and v <= b
            elif op == "<":
                ok = ok and v < b
            else:                       # "=" or bare version
                ok = ok and v == b
        if ok:
            return True
    return False


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def bugs_for(pragma, data=None):
    """-> (matching versions, [bug dicts]) for a pragma expression."""
    d = data or load()
    versions = [v for v in d["by_version"] if satisfies(v, pragma)]
    names = {n for v in versions for n in d["by_version"][v]}
    bugs = [d["bugs"][n] for n in sorted(names) if n in d["bugs"]]
    bugs.sort(key=lambda b: {"high": 0, "medium": 1, "low": 2, "very low": 3}
              .get(str(b.get("severity", "")).lower(), 4))
    return sorted(versions, key=parse), bugs


def floating(pragma):
    """Is this pragma a range rather than one exact version?"""
    return bool(re.search(r"[\^~<>]|\|\|", str(pragma or "")))


SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def describe(pragma, data=None, full=False):
    """Lines to print for one pragma. Empty list = nothing to say.

    High and medium bugs are listed; low ones are collapsed to a count unless
    `full`, because a 0.8.x range matches a dozen of them and a wall of low
    severity is how the two that matter get skipped.
    """
    d = data or load()
    out = []
    versions, bugs = bugs_for(pragma, d)
    v0 = parse(re.sub(r"[^\d.]", " ", str(pragma)).split()[0]) if VERSION.search(str(pragma)) else None
    if v0 and v0 < (0, 8, 0):
        out.append("pre-0.8: arithmetic does NOT revert on overflow -- every "
                   "finding in arithmetic.md is more severe here, and SafeMath "
                   "must be used on every operation")
    if floating(pragma):
        span = f"{versions[0]}..{versions[-1]}" if versions else "unknown range"
        out.append(f"floating pragma ({span}): the deployed bytecode may not be "
                   f"what you audited -- pin one exact version and record it")
    minor = 0
    for b in bugs:
        sev = str(b.get("severity", "?")).lower()
        if not full and sev not in ("high", "medium"):
            minor += 1
            continue
        fixed = b.get("fixed") or "unfixed"
        out.append(f"[{sev}] {b['name']} (fixed in {fixed}): {b['summary']}")
    if minor:
        out.append(f"...and {minor} low-severity bug(s): "
                   f"scripts/solc_bugs.py '{pragma}' lists them")
    return out


def update():
    """Refresh solc_bugs.json from the solidity repo. The only networked path."""
    import urllib.request
    from datetime import date

    def get(u):
        with urllib.request.urlopen(u, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    raw_bugs = get(SRC_BUGS)
    by_version = get(SRC_BY_VERSION)
    bugs = {}
    for b in raw_bugs:
        summary = " ".join(str(b.get("summary", "")).split())
        summary = re.sub(r"``([^`]+)``", r"`\1`", summary)
        if len(summary) > 240:
            summary = summary[:237].rstrip() + "..."
        bugs[b["name"]] = {"name": b["name"], "severity": b.get("severity", "?"),
                           "introduced": b.get("introduced"), "fixed": b.get("fixed"),
                           "summary": summary, "link": b.get("link")}
    data = {
        "generated": date.today().isoformat(),
        "sources": [SRC_BUGS, SRC_BY_VERSION],
        "bugs": bugs,
        "by_version": {v: sorted(info.get("bugs", []))
                       for v, info in by_version.items()},
    }
    with open(DATA, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {DATA}: {len(bugs)} bugs across {len(data['by_version'])} versions")


def _selftest():
    assert satisfies("0.8.13", "^0.8.13")
    assert satisfies("0.8.30", "^0.8.13")
    assert not satisfies("0.9.0", "^0.8.13")
    assert not satisfies("0.8.12", "^0.8.13")
    assert satisfies("0.8.5", ">=0.8.0 <0.9.0")
    assert not satisfies("0.7.6", ">=0.8.0 <0.9.0")
    assert satisfies("0.8.20", "0.8.20") and not satisfies("0.8.21", "0.8.20")
    assert floating("^0.8.13") and not floating("0.8.20")
    d = load()
    assert d["bugs"] and d["by_version"], "vendored data is empty"
    versions, bugs = bugs_for("^0.8.13", d)
    names = [b["name"] for b in bugs]
    assert "InlineAssemblyMemorySideEffects" in names, names[:5]
    lines = describe("^0.8.13", d)
    assert any("floating pragma" in l for l in lines), lines[:2]
    assert any(l.startswith("pre-0.8") for l in describe("^0.7.6", d))
    short, full = describe("^0.8.13", d), describe("^0.8.13", d, full=True)
    assert len(short) < len(full), (len(short), len(full))
    assert any("low-severity" in l for l in short), short
    print(f"selftest ok ({len(d['bugs'])} bugs, {len(d['by_version'])} versions, "
          f"data generated {d['generated']})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--update"]:
        update()
    elif a[:1] == ["--selftest"]:
        _selftest()
    elif not a:
        sys.exit(__doc__)
    else:
        for line in describe(a[0], full=True) or ["no known bugs for this pragma"]:
            print("  " + line)
