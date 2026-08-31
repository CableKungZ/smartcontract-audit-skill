#!/usr/bin/env python3
"""Convert Slither JSON output into findings.json entries.

    slither . --json slither.json
    python scripts/slither_to_findings.py slither.json > draft.findings.json

The output is a DRAFT, not a report. Slither's impact levels are not audit
severities: it has no idea what the code is supposed to do, so it cannot tell
a drainable reentrancy from a harmless one. Every entry comes out with
"status": "Unverified" and must be either

  * confirmed  -- rewrite description/impact/recommendation in your own words,
                  add a concrete failure scenario, set the real severity, and
                  set status to "Open"; or
  * dropped    -- it is a false positive or not reachable.

Never ship an entry that still says "Unverified".

Mapping (Slither impact x confidence -> our severity), deliberately
conservative -- everything lands one level below what Slither claims:

    High   + High     -> High          (you promote to Critical if it drains)
    High   + Medium   -> Medium
    Medium + any      -> Medium
    Low    + any      -> Low
    Informational     -> Informational
    Optimization      -> Informational

Stdlib only. Requires slither installed separately (pip install slither-analyzer).
"""

import json
import sys

SEV = {
    ("High", "High"): "High",
    ("High", "Medium"): "Medium",
    ("High", "Low"): "Medium",
    ("Medium", "High"): "Medium",
    ("Medium", "Medium"): "Medium",
    ("Medium", "Low"): "Low",
    ("Low", "High"): "Low",
    ("Low", "Medium"): "Low",
    ("Low", "Low"): "Low",
}
PREFIX = {"Critical": "C", "High": "H", "Medium": "M",
          "Low": "L", "Informational": "I"}

# Slither checks worth a louder note than its own impact rating suggests.
LOUD = {
    "arbitrary-send-eth", "arbitrary-send-erc20", "controlled-delegatecall",
    "delegatecall-loop", "reentrancy-eth", "unchecked-transfer",
    "uninitialized-state", "suicidal", "unprotected-upgrade", "weak-prng",
}


def severity(el):
    imp = el.get("impact", "Informational")
    if imp in ("Informational", "Optimization"):
        return "Informational"
    return SEV.get((imp, el.get("confidence", "Medium")), "Low")


def location(el):
    parts = []
    for src in el.get("elements", []):
        m = src.get("source_mapping") or {}
        f, lines = m.get("filename_short"), m.get("lines") or []
        if not f:
            continue
        span = f"{lines[0]}-{lines[-1]}" if len(lines) > 1 else (str(lines[0]) if lines else "")
        loc = f"{f}:{span}" if span else f
        if loc not in parts:
            parts.append(loc)
    return ", ".join(parts[:4]) or "unknown"


def convert(slither_json):
    dets = (slither_json.get("results") or {}).get("detectors") or []
    counters, out = {}, []
    for el in sorted(dets, key=lambda e: list(SEV.values()).index(severity(e))
                     if severity(e) in SEV.values() else 99):
        sev = severity(el)
        check = el.get("check", "?")
        counters[sev] = counters.get(sev, 0) + 1
        desc = " ".join((el.get("description") or "").split())
        note = ("Slither flags this as a high-impact check; verify it first. "
                if check in LOUD else "")
        out.append({
            "id": f"{PREFIX[sev]}-{counters[sev]:02d}",
            "title": f"[slither:{check}] {desc[:80]}",
            "severity": sev,
            "status": "Unverified",
            "location": location(el),
            "description": (f"{note}Reported by Slither detector `{check}` "
                            f"(impact {el.get('impact')}, confidence "
                            f"{el.get('confidence')}).\n\n{desc}"),
            "impact": "TODO: state the concrete loss. Drop this entry if there isn't one.",
            "recommendation": "TODO: specific code-level fix.",
            "references": [
                "https://github.com/crytic/slither/wiki/Detector-Documentation#"
                + check.replace("-", "-")],
        })
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    with open(argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    findings = convert(data)
    print(json.dumps({
        "project": "TODO",
        "summary": "TODO: written by the auditor, not by Slither.",
        "trust_assumptions": [],
        "findings": findings,
    }, indent=2))
    print(f"\n{len(findings)} draft entries -- all marked Unverified",
          file=sys.stderr)


def _selftest():
    sample = {"results": {"detectors": [
        {"check": "reentrancy-eth", "impact": "High", "confidence": "High",
         "description": "X.a() has reentrancy", "elements": [
             {"source_mapping": {"filename_short": "A.sol", "lines": [10, 11, 12]}}]},
        {"check": "naming-convention", "impact": "Informational",
         "confidence": "High", "description": "bad name", "elements": []},
    ]}}
    r = convert(sample)
    assert r[0]["severity"] == "High" and r[0]["id"] == "H-01", r[0]
    assert r[0]["location"] == "A.sol:10-12", r[0]["location"]
    assert r[0]["status"] == "Unverified"
    assert "verify it first" in r[0]["description"]
    assert r[1]["severity"] == "Informational" and r[1]["id"] == "I-01"
    print("selftest ok")


if __name__ == "__main__":
    _selftest() if sys.argv[1:2] == ["--selftest"] else main(sys.argv)
