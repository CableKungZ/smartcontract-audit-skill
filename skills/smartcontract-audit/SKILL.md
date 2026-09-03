---
name: smartcontract-audit
description: >
  Audit an EVM smart contract for security vulnerabilities, classify findings by
  severity (Critical / High / Medium / Low / Informational), and produce a
  self-contained HTML report with red "vulnerable code" / green "recommended fix"
  blocks, impact analysis and concrete remediation.
  Use when the user asks to audit, security-review, or find vulnerabilities in a
  Solidity contract (Vyper: catalogs apply, tooling does not - see below).
  Shared methodology plus per-contract-type catalogs
  (staking, token, lending, defi, swap, liquidity, wallet, launchpad/governance,
  and custody: deposit/withdraw, escrow, and wrapped 1:1 receipt tokens such as
  WETH or KKUB where no mint path may exist besides depositing the underlying),
  mandatory arithmetic/overflow/liveness, loop & gas, and custody passes, an
  incident-replay pass derived from real 2024-2026 exploits, Quick / Hard /
  Reaudit modes with an optional parallel mode that fans the passes out to
  concurrent subagents, a runnable-PoC requirement on every Critical and High, checks of
  the pinned OpenZeppelin and solc versions against known advisories, an
  on-chain state pass for deployed contracts, reference
  implementations to diff forks against, and chain-specific notes including
  KUB Chain / KAP standards.
model: opus
effort: high
license: MIT
---

# Smart Contract Audit

## Modes: Quick, Hard, Reaudit

Pick one **before** loading anything, and say which one you ran in the report.

A third mode, **Reaudit**, runs when the user supplies a previous
`findings.json`: verify each old finding at code level and set its status
(`Fixed` with the commit and line, `Open` with why the fix is incomplete, or
`Acknowledged`), then run the full Hard passes over the **changed** code —
fixes introduce findings, which is why Uranium is in `examples.md`. Generate
with `--previous`, which renders the remediation-status table above the
findings and marks anything new.

| | **Quick** (triage) | **Hard** (audit — the default) |
|---|---|---|
| When | first look, a fork you are sizing up, a PR diff, a contract you have already audited | anything holding real value, anything before deployment, anything a client pays for |
| Loads | `methodology.md` + `postmortems.md` + the type catalog(s) `scan.py` points at | every catalog in the table below, all seven passes |
| Effort | `medium` acceptable | `high` minimum, `xhigh` for large value |
| Reads | `scan.py` output, then only the lines it flags | every in-scope file end to end |
| Output | a ranked markdown list in the terminal: what to look at and why | `findings.json` → HTML report |
| Cost | roughly a third of Hard | full |

**Ask which mode when the user did not say.** One question, before the scan,
alongside a Yes/No for every optional step that applies to this run (Slither
import if `slither` is installed, HTML report, fork diff against an upstream in
`examples.md`, `forge test --gas-report` if Foundry is set up). Do not default
silently: quick and hard differ by roughly 3x in cost and produce different
deliverables, so the choice is the user's. Whatever they decline goes in the
report's Scope as **not performed**.

**Quick mode is not an audit and must never be presented as one.** End every
Quick run with this line verbatim:

> Triage only — catalogs partially loaded, code not read end to end. Not an
> audit. Run `/audit <path> hard` before deploying or relying on this.

Quick may *raise* an alarm; it may never clear one. "Nothing found in Quick" is
reported as "nothing found in the flagged lines", never as "looks safe".
Anything Quick finds at Critical or High stops the triage — switch to Hard.

Everything below this section describes **Hard**. In Quick, skip step 2, run
step 3's passes only against the lines `scan.py` flagged, and stop after a
terminal list — no `findings.json`, no HTML.

## Parallel mode (Hard, faster)

Hard mode serially walks seven passes plus the type catalogs over the same code.
That is the slow part, and the passes do not depend on each other — so run them
as concurrent subagents. Same coverage, same catalogs, wall-clock roughly the
length of the slowest pass.

**Decide this yourself — do not ask.** The deliverable and the rules are
identical either way, so it is a scheduling call, not the user's call, and you
have the numbers to make it after step 0. `scan.py`'s header line
(`N file(s), M lines`) plus the catalogs step 1 selected give you all three
inputs:

Go parallel when **any** of these holds:
- more than ~600 in-scope lines, or
- more than 3 in-scope files, or
- step 1 selected 3 or more catalogs (a farm that is staking + token + KUB, say).

Stay serial otherwise — under those thresholds one context walks the passes
faster than five agents can be briefed, and the fragments cost more to merge
than the passes cost to run. Also stay serial, whatever the size, when the
contract is one tightly coupled unit whose passes keep referring to each other
(a single AMM core where the rounding, the loop and the fee split are the same
twenty lines), or in Reaudit where the changed surface is small.

Say the call in one line before dispatching — "1,400 lines across 6 files,
4 catalogs → running the passes in parallel" — so the user can override it.
`/audit … parallel` or `… serial` forces the choice and skips the rule.

Steps 0, 1 and 2 stay in the main context — recon, type inference and reading
the contract end to end are what let you judge the fragments that come back.
Then dispatch these agents **in one message** (`general-purpose`), each with the
prompt template below:

| Agent | Passes | Loads |
|---|---|---|
| `arith` | 1 Arithmetic, 2 Liveness | `arithmetic.md` |
| `gas` | 3 Loops & gas, 4 Centralization | `gas.md`, `methodology.md` |
| `custody` | 5 Custody, 7 Value accounting | `custody.md`, `economics.md` |
| `replay` | 6 Incident replay, library/solc advisories | `postmortems.md`, `examples.md` |
| `type` | the type-catalog walk (step 3's checklist) | every catalog step 1 selected, plus `kub.md` / `onchain.md` if they apply |

Two type catalogs with little overlap (staking + token) split into two `type`
agents; more than that and you are paying dispatch overhead for nothing. Five to
six agents is the ceiling.

Prompt each with:

> You are running the **<name>** pass of a smart contract audit. Read
> `SKILL_DIR/references/<catalogs>` and every in-scope file end to end:
> `<paths>`. Walk your catalog as a checklist — for each item, is it reachable
> in *this* code? A finding needs a concrete failure scenario with numbers
> (inputs -> wrong state / loss); if you cannot write one it is Informational or
> not a finding. Do not pad, do not fix anything, do not write a report.
> Context you do not have to re-derive: <paste the roles table, value-flow path
> and external-call inventory from step 2>.
> Write `<scratch>/<name>.findings.json` — a JSON array of finding objects in
> the shape at the top of `report/gen_report.py`, with `id` prefixed `<name>-`.
> Leave `poc` empty. Reply with one line per finding: id, severity, location.

**The main context owns everything after that**, and this is not optional:

- **Merge and renumber.** Read every fragment. Deduplicate — two agents finding
  the same bug from different angles is one finding with the better description.
  Assign the real `C-01` / `H-02` ids only here.
- **The cross-cutting pass.** Ask what no single agent could see: does a Medium
  from `arith` become Critical given a `gas` unbounded loop, or a `custody`
  withdrawal path? This pass is the price of splitting; skip it and Parallel
  mode is worse than serial.
- **Severity, PoCs, self-review, the report** — steps 4, 5 and 6 unchanged. A
  subagent's severity is a proposal, not a verdict.
- **Say so in the report's method section**: run in parallel, which passes went
  to which agent, and that dedup and cross-cutting synthesis were done in the
  main context.

Quick mode does not parallelize — it is already cheap, and dispatch overhead
would eat the saving.

## Run conditions — do not audit below these

This skill sets `model: opus` and `effort: high` in its frontmatter so every run
starts from the same footing. Two audits of the same contract should reach the
same findings, and they only do if the reasoning budget is the same.

These apply to **Hard**. Quick relaxes effort and coverage, and pays for it by
being labelled as triage — it does not get to relax the labelling.

- **Effort must be `high` or above.** Drop to `low`/`medium` and the seven
  mandatory passes in step 3 get skimmed — the failures that go missing first
  are exactly the ones that need arithmetic carried through: type-range
  overflow, rounding direction, and the "can this revert forever" question.
  For a contract holding significant value, or one where the money map in
  `economics.md` is non-trivial, raise it to `xhigh`.
- **If the frontmatter override did not apply** — an org `availableModels`
  allowlist can exclude a model, in which case the session keeps its own — say
  so in the report's method section rather than silently producing a thinner
  audit. The reader needs to know what produced it.
- **Do not fan out below the pass level.** Splitting a *file* across agents is
  how cross-cutting findings (a rounding bug that only matters because of an
  unbounded loop) get lost. Splitting the *passes*, each agent reading the whole
  contract, does not — that is Parallel mode below.
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

It also prints three things that are findings in their own right: the
**CONTRACT TYPE** inference with its name-vs-body check (step 1), the
**COMPILER** section — every pragma against the solc team's own bug list, where
a floating pragma is itself a finding (`methodology.md`) — and the **TESTS**
section, whose invariant/fuzz counts belong in the report's method section.
The solc data is vendored; refresh it with `python scripts/solc_bugs.py
--update`, and query one pragma directly with `python scripts/solc_bugs.py
'^0.8.13'`.

If `slither` is available:

```
slither <path> --json slither.json
python scripts/slither_to_findings.py slither.json > draft.findings.json
```

Every imported entry is `"status": "Unverified"`. Confirm it (rewrite in your
own words, add a concrete failure scenario, set the real severity) or drop it.
Never ship an Unverified entry.

### 1. Identify contract type + chain, load catalogs

**Type comes from the identifiers, never from the file name.** `Token.sol`
routinely holds a staking pool, `Vault.sol` is whatever its functions say it is,
and a fork renames things freely. `scan.py`'s `CONTRACT TYPE` section does this
pass for you: it maps the function, variable and event names actually present in
the source to catalogs, and prints a **name-vs-body** check —

- *name hides this* → the file does something its name never advertises. Load
  those catalogs anyway; this is where the missed findings live.
- *name advertises, body has nothing* → either the logic lives in another
  contract (find it, it is in scope) or it is dead code. Say which in the report.

A disagreement between a name and its behaviour is a finding in its own right
once it is inside the code too: a `safeX` that is not safe, an `onlyOwner`-named
modifier that checks nothing, a `totalStaked` that is not the sum of stakes.
Names are a claim; the body is the evidence. Where they differ, integrators
build against the claim — file it, severity by what an integrator would lose.

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
| Deposit/withdraw vaults, escrow, wrapped & receipt tokens (WETH/KKUB), payment splitters | `references/custody.md` |
| Launchpad/IDO, governance/DAO, airdrop/merkle, NFT marketplace | `references/misc.md` |
| Any protocol that distributes value — launchpad, curve sale, fee split, settlement | `references/economics.md` |
| **Anything deployed on KUB Chain / Bitkub** | `references/kub.md` (**always**, on top of the type catalog) |
| **Anything already deployed** (an address was given) | `references/onchain.md` (**always** — source is not state) |

**Always load, regardless of type:**
- `references/methodology.md` — severity rubric, general EVM catalog, chain table.
- `references/arithmetic.md` — overflow / narrowing casts / precision, and the
  **contract-liveness (bricking)** pass.
- `references/gas.md` — loops, gas griefing, and optimization.
- `references/postmortems.md` — checks derived from real 2024–2026 incidents
  (rounding inconsistency, a wrong overflow *check*, donation on a fresh market,
  cross-chain verifier config, uninitialized proxies, EIP-7702, expiring pauses).

**Vyper contracts.** Every catalog here applies — the vulnerability classes are
language-independent — but the tooling is not: `scan.py`, `slither_to_findings.py`
and the identifier/type inference are Solidity-only, and `.vy` files are not
collected. Audit Vyper by hand against the same catalogs, state in Scope that
the recon pass did not run, and pay attention to the two places Vyper differs:
its `@nonreentrant` locks are per-key and were themselves broken in 0.2.15–0.3.0
(Curve, 2023, ~$70M — `swap.md`), and `raw_call` forwards all gas by default.
Check the Vyper release notes for the pinned version the same way `examples.md`
checks OpenZeppelin's.

**If the contract is a fork**, find its upstream in `references/examples.md` and
diff it line by line *before* anything else. Uranium Finance lost $50M to one
constant changed in one branch. Check the upstream's **security advisories**
too, not only its current source — Balancer V2's 2025 exploit hit its forks on
other chains the same day.

**Resolve the pinned version of every library** (OpenZeppelin, Solmate, Solady)
and check it against the advisory table in `references/examples.md`. A
vulnerable version whose affected component is actually used is a finding at the
listed severity.

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

Seven passes are mandatory whatever the contract type:

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
5. **Custody** (`custody.md`) — if the contract holds anyone else's value:
   list every path value can leave by, its destination and its bound. The
   operator must not be able to move a user's balance under **any**
   circumstance; a supply-increasing path must take custody in the same
   transaction. Put the conclusion in the executive summary as a sentence.
6. **Incident replay** (`postmortems.md`) — walk each numbered class against
   this code. Two of them apply to almost every contract: the paired-rounding
   check (does splitting an operation into N smaller ones ever yield more than
   doing it once?) and the pinned-library-version check against the advisory
   table in `examples.md`. Cite the incident in any finding it produces.
7. **Value accounting** (`economics.md`) — the money map: where every unit
   ends up, whether pricing/settlement parameters are snapshotted per item or
   read from mutable globals, and whether capital is placed somewhere the
   finite float can never reach. Compute every number you state.

### 4. Classify

Use the rubric in `references/methodology.md`. Impact first, then adjust for
likelihood and privilege required. When torn between two levels, state why, and
pick the lower one only if a *concrete* precondition (trusted role, oracle
failure, specific ordering) gates the exploit. "Unlikely in practice" is not a
precondition.

### 5. Prove it, then review yourself

**Every Critical and High needs a runnable PoC.** Write a Foundry test that
fails against the unfixed code and passes against the fix, and paste the real
command and its real output into the finding's `poc` field
(`{"file": …, "command": …, "output": …}`). The validator refuses to generate a
report where a Critical or High has neither a `poc` nor a `poc_waiver`. A
finding you cannot reproduce is an opinion.

If the repo has no test harness, `scan.py`'s `TESTS` section says so — write the
PoC against a minimal `forge init` scaffold, or use `poc_waiver` and recommend a
harness. The same section's invariant/fuzz counts belong in the report's method
section, with the specific invariants this contract needs where there are none.

Then run **the self-review pass** — the five questions in
`references/methodology.md` — against every finding, and record the outcome in
`review_note`. Drop what fails, explicitly, never silently.

### 6. Write `findings.json`, validate, generate

```
python report/gen_report.py --validate findings.json   # fix every warning
python report/gen_report.py findings.json report.html

# re-audit: previous findings become a remediation-status table
python report/gen_report.py --previous prev.findings.json findings.json report.html
```

Shape is documented at the top of `report/gen_report.py`;
`report/example.findings.json` is a filled-in sample. Output is one
self-contained HTML file — no assets, no network, light/dark aware, prints to
PDF cleanly.

End the report with the sequenced remediation stages from `economics.md` §5 — a
flat list of fixes leaves the team to guess the order. Then tell the user the
counts by severity and the single most important thing to fix first.

The validator's warnings are shipping blockers: a missing executive summary,
missing trust assumptions, a leftover `Unverified` status, a `TODO`
recommendation, or a duplicate id all mean the report isn't done. A Critical or
High with no `poc` and no `poc_waiver` is a hard **error**, not a warning — the
report will not generate.

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
              kub (KAP standards), postmortems (checks from real 2024-2026
              incidents), examples (upstreams to diff forks against, plus the
              OpenZeppelin known-vulnerable-version table)
report/       gen_report.py (JSON -> HTML + validator), example.findings.json
scripts/      scan.py (recon), slither_to_findings.py (import)
commands/     /audit and /audit-report slash commands
```
