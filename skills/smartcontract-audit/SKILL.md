---
name: smartcontract-audit
description: >
  Audit an EVM smart contract for security vulnerabilities, classify findings by
  severity (Critical / High / Medium / Low / Informational), and produce a
  self-contained HTML report with red "vulnerable code" / green "recommended fix"
  blocks, impact analysis and concrete remediation.
  Use when the user asks to audit, security-review, or find vulnerabilities in a
  Solidity/Vyper contract. Shared methodology plus per-contract-type catalogs
  (staking, token, lending, defi, swap, liquidity, wallet, launchpad/governance),
  a mandatory arithmetic/overflow/liveness pass, a loop & gas pass, reference
  implementations to diff forks against, and chain-specific notes including
  KUB Chain / KAP standards.
model: opus
effort: high
license: MIT
---

# Smart Contract Audit

## Run conditions — do not audit below these

This skill sets `model: opus` and `effort: high` in its frontmatter so every run
starts from the same footing. Two audits of the same contract should reach the
same findings, and they only do if the reasoning budget is the same.

- **Effort must be `high` or above.** Drop to `low`/`medium` and the five
  mandatory passes in step 3 get skimmed — the failures that go missing first
  are exactly the ones that need arithmetic carried through: type-range
  overflow, rounding direction, and the "can this revert forever" question.
  For a contract holding significant value, or one where the money map in
  `economics.md` is non-trivial, raise it to `xhigh`.
- **If the frontmatter override did not apply** — an org `availableModels`
  allowlist can exclude a model, in which case the session keeps its own — say
  so in the report's method section rather than silently producing a thinner
  audit. The reader needs to know what produced it.
- **Never run the audit in a subagent** unless the user asks. The catalogs plus
  the contract need to sit in one context; splitting them is how cross-cutting
  findings (a rounding bug that only matters because of an unbounded loop) get
  lost between agents.
- **Do not sample.** Read every in-scope file end to end. "Reviewed the main
  contract" is not an audit, and partial coverage must be stated in Scope.
- **Record what produced the report.** Put the model, effort level, tool
  versions (`solc`, `slither`) and the commit hash in the report's method
  section, so a re-run can be compared against it.

These are the reproducibility conditions. Everything below assumes them.

## Workflow

### 0. Recon (cheap, do it first)

```
python scripts/scan.py <path>
```

Prints the external surface (who can call what, with which modifier), every
loop with its bound, every narrowing cast, every division, and every
risk-pattern hit with a pointer to the relevant catalog. **It proves nothing** —
it tells you which lines to read.

If `slither` is available:

```
slither <path> --json slither.json
python scripts/slither_to_findings.py slither.json > draft.findings.json
```

Every imported entry is `"status": "Unverified"`. Confirm it (rewrite in your
own words, add a concrete failure scenario, set the real severity) or drop it.
Never ship an Unverified entry.

### 1. Identify contract type + chain, load catalogs

Load **every** catalog that applies — most contracts are two types at once (a
farm is staking + token; a vault is liquidity + defi).

| Contract | Catalog |
|---|---|
| Staking, farms, veToken locks, liquid staking, NFT staking | `references/staking.md` |
| ERC-20/721/1155/4626 tokens, KAP tokens | `references/token.md` |
| Lending, borrowing, CDP / stablecoin vaults | `references/lending.md` |
| Yield vaults, strategies, perps, bridges, oracles, flash loans | `references/defi.md` |
| AMM cores, routers, aggregators, any internal swap | `references/swap.md` |
| LP mint/burn, share math, zaps, V3 liquidity managers | `references/liquidity.md` |
| Multisig, smart accounts (4337/7702), timelocks, vesting, custodial wallets | `references/wallet.md` |
| Launchpad/IDO, governance/DAO, airdrop/merkle, NFT marketplace | `references/misc.md` |
| Any protocol that distributes value — launchpad, curve sale, fee split, settlement | `references/economics.md` |
| **Anything deployed on KUB Chain / Bitkub** | `references/kub.md` (**always**, on top of the type catalog) |

**Always load, regardless of type:**
- `references/methodology.md` — severity rubric, general EVM catalog, chain table.
- `references/arithmetic.md` — overflow / narrowing casts / precision, and the
  **contract-liveness (bricking)** pass.
- `references/gas.md` — loops, gas griefing, and optimization.

**If the contract is a fork**, find its upstream in `references/examples.md` and
diff it line by line *before* anything else. Uranium Finance lost $50M to one
constant changed in one branch.

### 2. Read the contract(s) end to end

Before writing any finding, build:
- a **roles & permissions table** — who can call what,
- the **value-flow path** — deposit → accounting → withdraw → rewards,
- an **inventory of every external call**.

Trace every `for`/`while`, every division, every `block.timestamp` /
`block.number` use, every narrowing cast, and every storage write in the
constructor/initializer.

### 3. Walk the catalogs as a checklist

For each item: is it reachable in *this* code? Construct a concrete failure
scenario — **inputs → wrong state / loss, with numbers**. If you can't write it,
it is Informational or not a finding. Drop what doesn't apply; don't pad.

Five passes are mandatory whatever the contract type:

1. **Arithmetic** (`arithmetic.md`) — every narrowing cast (silent truncation in
   0.8), every denominator's minimum value, every monotonic accumulator against
   its type max over the contract's lifetime, rounding direction on every shares
   path, intermediates that overflow before a division.
2. **Liveness** — can any function users *need* be made to revert forever?
   Answer the seven positive checks at the end of `arithmetic.md` explicitly in
   the report. A permanent freeze is Critical, same as theft.
3. **Loops & gas** (`gas.md`) — for every loop: who controls the bound, what the
   maximum is, and what dies past the block gas limit. On cheap-gas chains
   (BNB, Polygon, KUB) this is a real attack, not a theoretical one.
4. **Centralization** — every privileged function, the address holding it,
   whether it is an EOA / multisig / timelock, and the loss on compromise.
5. **Value accounting** (`economics.md`) — the money map: where every unit
   ends up, whether pricing/settlement parameters are snapshotted per item or
   read from mutable globals, and whether capital is placed somewhere the
   finite float can never reach. Compute every number you state.

### 4. Classify

Use the rubric in `references/methodology.md`. Impact first, then adjust for
likelihood and privilege required. When torn between two levels, state why, and
pick the lower one only if a *concrete* precondition (trusted role, oracle
failure, specific ordering) gates the exploit. "Unlikely in practice" is not a
precondition.

### 5. Write `findings.json`, validate, generate

```
python report/gen_report.py --validate findings.json   # fix every warning
python report/gen_report.py findings.json report.html
```

Shape is documented at the top of `report/gen_report.py`;
`report/example.findings.json` is a filled-in sample. Output is one
self-contained HTML file — no assets, no network, light/dark aware, prints to
PDF cleanly.

The validator's warnings are shipping blockers: a missing executive summary,
missing trust assumptions, a leftover `Unverified` status, a `TODO`
recommendation, or a duplicate id all mean the report isn't done.

## Writing findings

Each finding needs a stable id (`C-01`, `H-02`, … prefix matches severity),
title, severity, status (`Open` by default), precise `location`
(`File.sol:120-135`), **description** (the mechanism), **impact** (what an
attacker gains / users lose), and **recommendation** (a specific code-level fix,
never "add checks").

**Show the code both ways.** `code` renders as a red *Vulnerable code* block and
`fix` as a green *Recommended fix* block. Inside either, prefix a line with `-`
to highlight it red or `+` to highlight it green:

```json
"code": " function f() external {\n-    uint256 r = token.balanceOf(address(this));\n     rate = r / DURATION;\n }",
"fix":  " function f() external {\n+    uint256 r = rewardReserve;\n     rate = r / DURATION;\n }"
```

Cite a real incident or a reference implementation when one fits — the catalogs
and `references/examples.md` give them.

Always fill `trust_assumptions` (say what you did **not** audit: libraries,
oracles, tokens, admin keys, the compiler). Keep the report honest: if a
suspected issue turns out gated or unreachable, either drop it or file it as
Informational with the mitigating factor named.

## Files

```
references/   methodology, arithmetic+liveness, gas+loops, per-type catalogs,
              kub (KAP standards), examples (upstreams to diff forks against)
report/       gen_report.py (JSON -> HTML + validator), example.findings.json
scripts/      scan.py (recon), slither_to_findings.py (import)
.claude/      /audit and /audit-report slash commands
```
