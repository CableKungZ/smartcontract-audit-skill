#!/usr/bin/env python3
"""Recon pass over a Solidity codebase. Prints an inventory, not a verdict.

    python scripts/scan.py contracts/
    python scripts/scan.py contracts/ --json > recon.json

This is deliberately dumb: regex over source, no compiler, no dependencies.
Its job is to give the audit a starting map and a list of lines to read --
every hit still has to be read in context. It finds nothing on its own.

Sections printed:
  files       loc, pragma, licence, imports (which library + version pinned?)
  surface     external/public functions, their modifiers, payable, view
  risk        one line per pattern hit, grouped -- see PATTERNS below
  loops       every for/while with the bound expression (see references/gas.md)
  casts       every narrowing cast (see references/arithmetic.md)
  math        every division and exponentiation
"""

import json
import os
import re
import sys
from collections import defaultdict

# pattern name -> (regex, why it matters, reference file)
PATTERNS = [
    ("delegatecall",   r"\.delegatecall\b",
     "arbitrary delegatecall = storage takeover", "wallet.md"),
    ("low-level-call", r"\.call\s*[{(]",
     "return value checked? reentrancy? gas griefing?", "arithmetic.md"),
    ("transfer-2300",  r"\.(transfer|send)\s*\(\s*[^)]*\)\s*;",
     "2300-gas stipend breaks contract wallets", "gas.md"),
    ("selfdestruct",   r"\bselfdestruct\b",
     "contract can be killed", "arithmetic.md"),
    ("tx.origin",      r"\btx\.origin\b",
     "auth via tx.origin is phishable and breaks AA", "methodology.md"),
    ("assembly",       r"\bassembly\s*\{",
     "bypasses 0.8 overflow checks", "arithmetic.md"),
    ("unchecked",      r"\bunchecked\s*\{",
     "overflow is silent here -- prove it cannot happen", "arithmetic.md"),
    ("block.timestamp", r"\bblock\.(timestamp|number)\b",
     "validator-influenceable; block.number differs per chain", "methodology.md"),
    ("blockhash",      r"\b(blockhash|block\.difficulty|block\.prevrandao)\b",
     "not a safe randomness source", "methodology.md"),
    ("ecrecover",      r"\becrecover\s*\(",
     "check for address(0), malleability, replay binding", "wallet.md"),
    ("approve",        r"\.approve\s*\(",
     "race condition; ignored return value on non-standard tokens", "token.md"),
    ("balanceOf-self", r"balanceOf\s*\(\s*address\s*\(\s*this\s*\)\s*\)",
     "donation-manipulable accounting", "liquidity.md"),
    ("getReserves",    r"\b(getReserves|slot0)\s*\(",
     "spot price = flash-loan manipulable", "defi.md"),
    ("latestAnswer",   r"\blatestAnswer\s*\(",
     "deprecated; no staleness data -- use latestRoundData", "defi.md"),
    ("initializer",    r"\b(initializer|reinitializer)\b",
     "is the implementation locked with _disableInitializers()?", "methodology.md"),
    ("min-out-zero",   r"\b(amountOutMin|minOut|minAmountOut|amountMin)\s*[:=]\s*0\b",
     "no slippage protection = guaranteed sandwich", "swap.md"),
    ("deadline-now",   r"deadline\s*[:=]\s*block\.timestamp",
     "deadline of now is a no-op", "swap.md"),
    ("renounce",       r"\brenounceOwnership\b",
     "can permanently brick admin functions", "arithmetic.md"),
    ("push-in-loop",   r"\.push\s*\(",
     "who can grow this array, and is it looped over?", "gas.md"),
    ("hardcoded-1e18", r"\b(1e18|1 ether|10\s*\*\*\s*18)\b",
     "hardcoded 18 decimals -- wrong for USDC(6)/WBTC(8); normalize instead",
     "arithmetic.md"),
    ("decimals-call",  r"\.decimals\s*\(",
     "read per token at point of use; never cache across a mutable address",
     "arithmetic.md"),
    ("mint-site",      r"\b_mint\s*\(|\btotalSupply\s*\+=|\b_update\s*\(\s*address\s*\(\s*0",
     "supply increase -- which entry points reach it, and does each take custody?",
     "custody.md"),
    ("payout-to-param",
     r"function\s+\w*(?:[Ww]ithdraw|[Rr]ecover|[Rr]escue|[Ss]weep|[Cc]laim|[Tt]ransfer)"
     r"\w*\s*\([^)]*\baddress\b",
     "value leaves to a caller-supplied address -- bounded to their own balance?",
     "custody.md"),
]

FUNC = re.compile(
    r"^\s*function\s+(\w+)\s*\(([^)]*)\)\s*([^{;]*)", re.M)
LOOP = re.compile(r"^\s*(for|while)\s*\(([^)]*)\)", re.M)
CAST = re.compile(r"\b(u?int(?:8|16|24|32|40|48|64|96|112|128|160|192|224))\s*\(")
DIV = re.compile(r"[^/\s]\s*/\s*[^/=\s]|\*\*")
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]+);")
LICENSE = re.compile(r"SPDX-License-Identifier:\s*(\S+)")
IMPORT = re.compile(r'^\s*import\s+.*?["\']([^"\']+)["\']', re.M)
VISIBLE = re.compile(r"\b(external|public)\b")


def strip_comments(src):
    """Blank out comments and strings but keep line count and offsets."""
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), src, flags=re.S)
    out = re.sub(r"//[^\n]*", lambda m: " " * len(m.group()), out)
    return re.sub(r'"[^"\n]*"', lambda m: " " * len(m.group()), out)


def line_of(src, pos):
    return src.count("\n", 0, pos) + 1


def scan_file(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    src = strip_comments(raw)
    rel = path.replace("\\", "/")

    funcs = []
    for m in FUNC.finditer(src):
        name, args, tail = m.group(1), m.group(2), m.group(3)
        if not VISIBLE.search(tail):
            continue
        mods = [w for w in re.findall(r"\b\w+\b", tail)
                if w not in ("external", "public", "view", "pure", "payable",
                             "returns", "override", "virtual", "memory",
                             "calldata", "storage", "uint256", "address", "bool",
                             "bytes", "string", "int256", "uint")]
        funcs.append({
            "line": line_of(src, m.start()), "name": name,
            "args": " ".join(args.split()),
            "payable": "payable" in tail, "view": bool(re.search(r"\b(view|pure)\b", tail)),
            "modifiers": mods,
        })

    risks = defaultdict(list)
    for name, pat, why, ref in PATTERNS:
        for m in re.finditer(pat, src):
            risks[name].append({"line": line_of(src, m.start()), "why": why, "ref": ref})

    loops = [{"line": line_of(src, m.start()), "kind": m.group(1),
              "bound": " ".join(m.group(2).split())} for m in LOOP.finditer(src)]
    casts = [{"line": line_of(src, m.start()), "type": m.group(1)} for m in CAST.finditer(src)]
    math = sorted({line_of(src, m.start()) for m in DIV.finditer(src)})

    return {
        "file": rel,
        "loc": raw.count("\n") + 1,
        "pragma": (PRAGMA.search(src) or [None, None])[1],
        "license": (LICENSE.search(raw) or [None, None])[1],
        "imports": IMPORT.findall(src),
        "functions": funcs,
        "risks": dict(risks),
        "loops": loops,
        "casts": casts,
        "division_lines": math,
    }


def collect(target):
    if os.path.isfile(target):
        return [scan_file(target)]
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in
                   ("node_modules", ".git", "lib", "out", "cache", "artifacts")]
        for f in sorted(files):
            if f.endswith(".sol"):
                out.append(scan_file(os.path.join(root, f)))
    return out


def report(results):
    w = sys.stdout.write
    total_loc = sum(r["loc"] for r in results)
    w(f"\n{len(results)} file(s), {total_loc} lines\n")

    w("\n=== FILES ===\n")
    for r in results:
        w(f"  {r['file']}  ({r['loc']} loc)  pragma {r['pragma'] or 'MISSING'}"
          f"  licence {r['license'] or 'MISSING'}\n")
        for i in r["imports"]:
            w(f"      import {i}\n")

    w("\n=== EXTERNAL SURFACE (who can call what) ===\n")
    for r in results:
        if not r["functions"]:
            continue
        w(f"  {r['file']}\n")
        for f in r["functions"]:
            tags = []
            if f["payable"]:
                tags.append("payable")
            if f["view"]:
                tags.append("view")
            guard = ", ".join(f["modifiers"]) or "NO MODIFIER"
            w(f"    :{f['line']:<5} {f['name']}({f['args']})"
              f"{'  [' + ' '.join(tags) + ']' if tags else ''}  -> {guard}\n")

    w("\n=== RISK PATTERNS (read every line, none of these is a finding by itself) ===\n")
    grouped = defaultdict(list)
    for r in results:
        for name, hits in r["risks"].items():
            for h in hits:
                grouped[name].append((r["file"], h))
    for name, _, why, ref in PATTERNS:
        if name not in grouped:
            continue
        w(f"\n  [{name}] {grouped[name][0][1]['why']}  (see references/{ref})\n")
        for path, h in grouped[name]:
            w(f"      {path}:{h['line']}\n")

    w("\n=== LOOPS (references/gas.md: who controls the bound?) ===\n")
    any_loop = False
    for r in results:
        for l in r["loops"]:
            any_loop = True
            w(f"  {r['file']}:{l['line']:<5} {l['kind']} ({l['bound']})\n")
    if not any_loop:
        w("  none\n")

    w("\n=== NARROWING CASTS (references/arithmetic.md: silent truncation in 0.8) ===\n")
    any_cast = False
    for r in results:
        for c in r["casts"]:
            any_cast = True
            w(f"  {r['file']}:{c['line']:<5} {c['type']}(...)\n")
    if not any_cast:
        w("  none\n")

    w("\n=== DIVISION / EXPONENTIATION (check order of ops and denominators) ===\n")
    for r in results:
        if r["division_lines"]:
            w(f"  {r['file']}: lines " +
              ", ".join(str(x) for x in r["division_lines"]) + "\n")

    w("\nNext: read the code. This scan proves nothing.\n\n")


def _selftest():
    import tempfile
    src = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
contract T {
    uint128 x;
    // .delegatecall in a comment must NOT be flagged
    function withdraw(uint256 a) external onlyOwner {
        for (uint256 i; i < users.length; i++) { total += a / n; }
        x = uint128(a);
        payable(msg.sender).transfer(a);
    }
    function deposit(uint256 a) external { _mint(msg.sender, a); }
    function rescue(address token, address to, uint256 a) external onlyOwner {}
    function _internal() internal {}
}
"""
    p = os.path.join(tempfile.mkdtemp(), "T.sol")
    open(p, "w").write(src)
    r = scan_file(p)
    assert r["pragma"].strip() == "^0.8.24", r["pragma"]
    assert r["license"] == "MIT"
    assert "withdraw" in [f["name"] for f in r["functions"]], r["functions"]
    assert r["functions"][0]["modifiers"] == ["onlyOwner"]
    assert "delegatecall" not in r["risks"], "comment was not stripped"
    assert "transfer-2300" in r["risks"]
    assert len(r["loops"]) == 1 and "users.length" in r["loops"][0]["bound"]
    assert any(c["type"] == "uint128" for c in r["casts"])
    assert r["division_lines"]
    assert "mint-site" in r["risks"], "supply increase not flagged"
    assert "payout-to-param" in r["risks"], "arbitrary payout destination not flagged"
    print("selftest ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--selftest"]:
        _selftest()
    elif not args:
        sys.exit(__doc__)
    else:
        res = collect(args[0])
        if not res:
            sys.exit(f"no .sol files under {args[0]}")
        print(json.dumps(res, indent=2)) if "--json" in args else report(res)
