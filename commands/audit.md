---
description: Security audit of a Solidity contract or directory. hard (default) = full audit + HTML report; quick = cheap triage list
argument-hint: <path-to-contract-or-dir> [quick|hard] [chain] [type]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
model: opus
effort: high
---

Run a smart contract security audit of: **$ARGUMENTS**

The skill lives at `${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/` — call
that **SKILL_DIR** below. Every `SKILL_DIR/...` path in this file means that
directory; resolve it before reading or running anything.

Follow `SKILL_DIR/SKILL.md` exactly. Do not skip steps, and do not write a
single finding before step 4 is done.

## 0. Mode

`$ARGUMENTS` may contain `quick` or `hard`. **Default is `hard`.**

- **hard** — everything in this file, all seven passes, HTML report.
- **quick** — triage. Run step 1, load only `methodology.md`, `postmortems.md`
  and the type catalogs `scan.py` actually points at, read only the lines it
  flags, and stop after step 4 with a **ranked markdown list in the terminal**:
  one line per suspicion — `file:line — what to check — why`. No
  `findings.json`, no HTML, no severities you cannot defend.

  End a quick run with this line verbatim:

  > Triage only — catalogs partially loaded, code not read end to end. Not an
  > audit. Run `/audit <path> hard` before deploying or relying on this.

  Quick may raise an alarm, never clear one: report "nothing found in the
  flagged lines", never "looks safe". If quick turns up anything that looks
  Critical or High, stop and tell the user to run hard — do not finish the
  triage.

## 1. Recon

```
python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/scripts/scan.py $1
```

Read the output. It gives you the external surface, every loop with its bound,
every narrowing cast, every division, and every risk-pattern hit. It proves
nothing on its own — it tells you which lines to read.

If `slither` is installed, also import a draft:

```
slither $1 --json slither.json
python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/scripts/slither_to_findings.py slither.json > draft.findings.json
```

Every draft entry is `"status": "Unverified"`. Confirm it (rewrite in your own
words, add a concrete failure scenario, set the real severity) or drop it.
Never ship an Unverified entry.

## 2. Load the catalogs

Read from `SKILL_DIR/references/`.

**Type comes from the identifiers, not the file name.** Use the `CONTRACT TYPE`
section of the `scan.py` output from step 1: load every catalog it lists, and
read the **name-vs-body** lines — a file whose name hides what the body does is
where findings get missed, and a name that advertises behaviour the body lacks
means the logic lives in another contract (find it) or is dead code. A name that
contradicts its own behaviour (`safeX` that is not safe, `totalStaked` that is
not the sum of stakes) is itself a finding: integrators build against the name.

**Always, whatever the contract is:** `methodology.md`, `arithmetic.md`, `gas.md`,
`postmortems.md` (checks derived from real 2024-2026 exploits).

Then every type catalog that applies — most contracts are two types at once
(a farm is staking + token; a vault is liquidity + defi):

| Type | File |
|---|---|
| staking, farms, veToken, LST, NFT staking | `staking.md` |
| ERC-20/721/1155/4626, KAP tokens | `token.md` |
| lending, borrowing, CDP | `lending.md` |
| vaults, strategies, perps, bridges, oracles | `defi.md` |
| AMM, router, aggregator, any internal swap | `swap.md` |
| LP accounting, shares, zaps, V3 managers | `liquidity.md` |
| multisig, 4337/7702, timelock, vesting, custodial | `wallet.md` |
| deposit/withdraw, escrow, wrapped tokens (WETH/KKUB), splitters | `custody.md` |
| launchpad/IDO, governance, airdrop, marketplace | `misc.md` |
| **any protocol that distributes value** (launchpad, curve sale, fee split, settlement) | `economics.md` |
| **anything on KUB Chain** | `kub.md` (on top of the type catalog) |

If the contract is a fork, find its upstream in `examples.md` and **diff it
line by line first**, and check the upstream's security advisories too. Uranium
Finance lost $50M to one constant changed in one branch; Balancer V2's 2025
exploit hit its forks on other chains the same day.

Resolve the **pinned version** of every library (`package-lock.json`, the
`lib/` submodule commit) and check it against the OpenZeppelin advisory table
in `examples.md`. A vulnerable version whose affected component is used is a
finding at the listed severity.

## 3. Read the code end to end

Before any finding, build:
- a roles & permissions table (who can call what),
- the value-flow path (deposit → accounting → withdraw → rewards),
- an inventory of every external call.

## 4. Walk the catalogs as a checklist

For each item: is it reachable here? Write the exploit as **concrete steps with
numbers**. If you can't, it is Informational or not a finding. Drop what doesn't
apply — do not pad.

Seven passes are mandatory whatever the type:

1. **Arithmetic** (`arithmetic.md`) — every narrowing cast (silent truncation in
   0.8), every denominator's minimum value, every monotonic accumulator against
   its type max, rounding direction on every shares path.
2. **Liveness** — can any function users need be made to revert forever? Answer
   the seven positive checks at the end of `arithmetic.md` explicitly. A
   permanent freeze is Critical, same as theft.
3. **Loops & gas** (`gas.md`) — for every loop: who controls the bound, and what
   dies past the block gas limit.
4. **Centralization** — every privileged function, who holds it, loss on compromise.
5. **Custody** (`custody.md`) — if it holds anyone else's value: every path
   value leaves by, its destination, its bound. The operator must not be able
   to move a user's balance in any case; every supply increase must take
   custody in the same transaction.
6. **Incident replay** (`postmortems.md`) — walk its numbered classes against
   this code; the paired-rounding check and the pinned-library-version check
   apply to almost everything. Cite the incident in any finding it produces.
7. **Value accounting** (`economics.md`) — where every unit ends up, whether
   pricing parameters are per-item or global-mutable, and whether any capital
   is placed somewhere participants can never reach it. Compute the numbers.

## 5. Classify

Use the rubric in `methodology.md`. Impact first, then adjust for likelihood and
privilege. Downgrade only when a *concrete* precondition gates the exploit.

## 6. Write `findings.json` and generate the report (hard only)

Shape is documented at the top of `SKILL_DIR/report/gen_report.py`;
`SKILL_DIR/report/example.findings.json` is a filled-in sample.

For each finding include `code` (the vulnerable snippet, renders red) and `fix`
(the recommended snippet, renders green), using `-` / `+` line prefixes to
highlight the exact lines.

```
python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/report/gen_report.py --validate findings.json
python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/report/gen_report.py findings.json report.html
```

End the report with the sequenced remediation stages from `economics.md` §5 —
a flat list of fixes leaves the team to guess the order.

Fix every validator warning before shipping. Then tell the user the counts by
severity and the single most important thing to fix first.
