---
description: Full security audit of a Solidity contract or directory, ending in an HTML report
argument-hint: <path-to-contract-or-dir> [chain] [type]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

Run a complete smart contract security audit of: **$ARGUMENTS**

Follow `SKILL.md` in this repo exactly. Do not skip steps and do not write a
single finding before step 4 is done.

## 1. Recon

```
python scripts/scan.py $1
```

Read the output. It gives you the external surface, every loop, every narrowing
cast, every division, and every risk-pattern hit. It proves nothing on its own —
it tells you which lines to read.

If `slither` is installed, also run it and import the draft:

```
slither $1 --json slither.json && python scripts/slither_to_findings.py slither.json > draft.findings.json
```

Every draft entry is `"status": "Unverified"`. Confirm or drop each one; never
ship an Unverified entry.

## 2. Load the catalogs

Always: `references/methodology.md`, `references/arithmetic.md`,
`references/gas.md`.

Then by contract type (load every one that applies — most contracts are two
types at once):

| Type | File |
|---|---|
| staking, farms, veToken, LST, NFT staking | `references/staking.md` |
| ERC-20/721/1155/4626, KAP tokens | `references/token.md` |
| lending, borrowing, CDP | `references/lending.md` |
| vaults, strategies, perps, bridges, oracles | `references/defi.md` |
| AMM, router, aggregator, any internal swap | `references/swap.md` |
| LP accounting, shares, zaps, V3 managers | `references/liquidity.md` |
| multisig, 4337/7702, timelock, vesting, custodial | `references/wallet.md` |
| launchpad/IDO, governance, airdrop, marketplace | `references/misc.md` |
| **anything on KUB Chain** | `references/kub.md` (on top of the type catalog) |

If the contract is a fork, find its upstream in `references/examples.md` and
**diff it line by line first**. Most fork exploits are one changed constant.

## 3. Read the code end to end

Before any finding, build:
- a roles & permissions table (who can call what),
- the value-flow path (deposit → accounting → withdraw → rewards),
- an inventory of every external call.

## 4. Walk the catalogs as a checklist

For each item: is it reachable here? Write the exploit as **concrete steps with
numbers**. If you can't, it is Informational or not a finding. Drop what doesn't
apply — do not pad.

Mandatory passes, whatever the contract type:
- **Arithmetic** (`arithmetic.md`): every narrowing cast, every denominator,
  every monotonic accumulator against its type max, rounding direction on every
  shares path.
- **Liveness**: can any required function be made to revert forever? Answer the
  seven positive checks at the end of `arithmetic.md` explicitly.
- **Loops & gas** (`gas.md`): for every loop, who controls the bound and what
  breaks past the gas limit.
- **Centralization**: every privileged function, who holds it, loss on compromise.

## 5. Classify

Use the rubric in `references/methodology.md`. Impact first, then adjust for
likelihood and privilege. Only downgrade when a *concrete* precondition gates
the exploit.

## 6. Write `findings.json` and generate the report

Shape is documented at the top of `report/gen_report.py`. For each finding
include `code` (the vulnerable snippet, red) and `fix` (the recommended
snippet, green), using `-`/`+` line prefixes to highlight the exact lines.

```
python report/gen_report.py --validate findings.json    # fix warnings first
python report/gen_report.py findings.json report.html
```

Fix every warning before shipping. Then tell the user the counts by severity and
the single most important thing to fix first.
