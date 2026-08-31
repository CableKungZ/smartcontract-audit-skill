<div align="center">

# 🛡️ Smart Contract Audit Skill

### Make your smart contracts safe.

**A Claude Code skill that audits EVM smart contracts — severity-classified
findings, a mandatory arithmetic & liveness pass, and a self-contained HTML
report showing the vulnerable code in red and the fix in green.**

[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-d97757?style=flat-square)](https://docs.claude.com/en/docs/claude-code/skills)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#requirements)
[![Dependencies](https://img.shields.io/badge/dependencies-none-2f855a?style=flat-square)](#requirements)
[![Chains](https://img.shields.io/badge/chains-EVM%20%2B%20KUB-627eea?style=flat-square)](skills/smartcontract-audit/references/kub.md)

</div>

---

## What it does

Point it at a Solidity contract and it runs a structured audit: recon → catalog
walk → concrete exploit scenarios → severity classification → HTML report.

- **14 vulnerability catalogs**, one per contract type, each with real incidents
  and the exact code pattern to look for.
- **Mandatory arithmetic & liveness pass** — narrowing casts that truncate
  silently in Solidity 0.8, accumulators that overflow their type, and every way
  a contract can be **permanently bricked** so funds can never be withdrawn.
- **Loop & gas pass** — who controls each loop's bound, and what dies past the
  block gas limit. Calibrated for cheap-gas chains where griefing is affordable.
- **KUB Chain / KAP support** — the `adminTransfer` / `internalTransfer` / KYC
  layer that would be a Critical finding anywhere else and is expected here.
- **Fork diffing** — a table of upstream implementations to diff against,
  because most fork exploits are one changed constant.
- **Custody rules** — for anything holding user funds: the operator must never
  be able to withdraw a customer's balance, and a 1:1 wrapper (KUB→KKUB) must
  have no mint path other than depositing the underlying. Both are checked
  mechanically, not taken on trust.
- **Value accounting** — where every unit of value ends up, whether pricing
  parameters are per-item or global-mutable, and whether capital is placed
  somewhere participants can never reach it.
- **Reproducible runs** — the skill pins `model: opus` and `effort: high` in
  frontmatter, so two audits of the same contract start from the same footing.
- **HTML report** — one file, no assets, no network, light/dark aware, prints to
  PDF, with the vulnerable code in red and the recommended fix in green, plus
  analysis tables and a sequenced remediation roadmap.

## Install

This repo is both a Claude Code **plugin marketplace** and the plugin itself:

```bash
/plugin marketplace add CableKungZ/smartcontract-audit-skill
/plugin install smartcontract-audit@cablekungz-skills
```

Then run `/smartcontract-audit:audit contracts/Staking.sol`, or just ask —
*"audit this staking contract for KUB Chain"* — the skill triggers on its own.

To hack on it locally instead, clone it and
`/plugin marketplace add ./smartcontract-audit-skill`.

## Quick start

```bash
S=skills/smartcontract-audit

# 1. Recon: external surface, loops, casts, divisions, risk patterns
python $S/scripts/scan.py contracts/

# 2. (optional) Import Slither as a draft — every entry lands "Unverified"
slither contracts/ --json slither.json
python $S/scripts/slither_to_findings.py slither.json > draft.findings.json

# 3. Audit (in Claude Code) -- add `quick` for cheap triage instead
/audit contracts/Staking.sol

# 4. Report
python $S/report/gen_report.py --validate findings.json   # fix every warning
python $S/report/gen_report.py findings.json report.html
```

## The report

```
┌──────────────────────────────────────────────┐
│  Example Staking Pool — Security Audit       │
│  type · chain · commit · date · auditor      │
├──────────────────────────────────────────────┤
│  Scope · Executive summary                   │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐              │
│  │ 1  ││ 2  ││ 2  ││ 1  ││ 1  │  by severity │
│  │CRIT││HIGH││MED ││LOW ││INFO│              │
│  └────┘└────┘└────┘└────┘└────┘              │
│  Summary table (click an ID to jump)         │
│  Trust assumptions & out of scope            │
├──────────────────────────────────────────────┤
│ ▌C-01 · notifyRewardAmount counts principal  │
│   StakingPool.sol:184-197                    │
│   Description …                              │
│   ╭─ VULNERABLE CODE ──────────────╮  red    │
│   │ - uint256 r = balanceOf(this); │         │
│   ╰────────────────────────────────╯         │
│   Impact … Recommendation …                  │
│   ╭─ RECOMMENDED FIX ──────────────╮  green  │
│   │ + uint256 r = rewardReserve;   │         │
│   ╰────────────────────────────────╯         │
└──────────────────────────────────────────────┘
```

Severity buckets: **Critical / High / Medium / Low / Informational**, aligned
with the [Immunefi classification system](https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3)
and Code4rena/Sherlock practice. Impact first, then adjusted for likelihood and
privilege required — the full rubric is in
[`references/methodology.md`](skills/smartcontract-audit/references/methodology.md).

## Catalogs

| Contract type | Catalog | Covers |
|---|---|---|
| Staking, farms, veToken, LST, NFT staking | [`staking.md`](skills/smartcontract-audit/references/staking.md) | reward accounting, stake/unstake rounding loops, locks, withdrawal queues |
| Tokens — ERC-20/721/1155/4626, KAP | [`token.md`](skills/smartcontract-audit/references/token.md) | mint control, honeypot taxes, permit, rebasing, vault-share inflation |
| Lending, borrowing, CDP | [`lending.md`](skills/smartcontract-audit/references/lending.md) | interest accrual, health factors, liquidation, bad debt, empty-market donation |
| Vaults, perps, bridges, oracles | [`defi.md`](skills/smartcontract-audit/references/defi.md) | oracle manipulation, strategy losses, flash loans, cross-chain replay |
| AMM, routers, aggregators | [`swap.md`](skills/smartcontract-audit/references/swap.md) | slippage/deadline, `k` invariant, V3 callback auth, MEV |
| LP accounting, zaps, V3 managers | [`liquidity.md`](skills/smartcontract-audit/references/liquidity.md) | first-depositor inflation, share rounding, LP pricing |
| Wallets, 4337/7702, timelocks | [`wallet.md`](skills/smartcontract-audit/references/wallet.md) | signature replay, threshold bypass, delegatecall, recovery |
| Deposit/withdraw, escrow, wrapped tokens | [`custody.md`](skills/smartcontract-audit/references/custody.md) | operator-cannot-withdraw rule, solvency invariant, escrow state machine, the no-mint rule for 1:1 wrappers |
| Launchpad, governance, airdrop, marketplace | [`misc.md`](skills/smartcontract-audit/references/misc.md) | refund paths, flash-loan voting, merkle leaves, auction griefing |
| Anything that distributes value | [`economics.md`](skills/smartcontract-audit/references/economics.md) | value map, admin levers, unreachable liquidity, sequenced remediation |
| **Every audit** | [`arithmetic.md`](skills/smartcontract-audit/references/arithmetic.md) | overflow, truncation, precision, **and contract bricking** |
| **Every audit** | [`gas.md`](skills/smartcontract-audit/references/gas.md) | unbounded loops, gas griefing, optimization |
| **Every audit** | [`methodology.md`](skills/smartcontract-audit/references/methodology.md) | severity rubric, general EVM catalog, per-chain notes |
| Reference | [`examples.md`](skills/smartcontract-audit/references/examples.md) | upstreams to diff forks against, libraries, security corpora |
| KUB Chain | [`kub.md`](skills/smartcontract-audit/references/kub.md) | KAP-20/721/1155/22, `adminTransfer`, KYC gating, chain notes |

## KUB Chain / Bitkub

KUB is EVM-compatible, so the whole methodology applies — what differs is the
**KAP layer**, a compliance framework that adds privileged functions by design:

| Function | Who can call it | Audit question |
|---|---|---|
| `adminTransfer` | the Committee address set in the constructor | is it a multisig, and can it be repointed without a delay? |
| `adminApprove` | Admin / Super Admin | admin-set allowances bypass the user entirely |
| `internalTransfer` | Super Admin + Transfer Router | are **both** parties KYC'd at `acceptedKycLevel`? |
| `externalTransfer` | Super Admin + Transfer Router | can the KYC contract be repointed? |

The correct output is **not** "Critical: admin can move user funds" — it is a
scoped centralization finding. And any DeFi protocol on KUB that accepts
arbitrary KAP-20 tokens inherits every one of those tokens' committees as a
trusted party. See [`references/kub.md`](skills/smartcontract-audit/references/kub.md).

Source: [docs.kubchain.com](https://docs.kubchain.com/quickstart/launching-a-token-on-kub/kap-token-interfaces).

## Tools

| Tool | What it does |
|---|---|
| `scripts/scan.py` | Regex recon: external surface + modifiers, every loop with its bound, every narrowing cast, every division, 27 risk patterns each pointing at the relevant catalog. `--json` for machine output. |
| `scripts/slither_to_findings.py` | Converts `slither --json` into draft findings, mapped one severity level *below* what Slither claims, every entry `Unverified` until a human confirms it. |
| `scripts/linkcheck.py` | Verifies every reference URL still resolves — a report citing a 404 is a report the reader stops trusting. Exit code = dead links, so it drops into CI. |
| `report/gen_report.py` | `findings.json` → self-contained HTML. `--validate` checks schema, duplicate ids, severity/id-prefix mismatch, leftover `Unverified`, `TODO` recommendations, missing summary or trust assumptions. |
| `/audit <path> [quick\|hard]` | `hard` (default) runs the whole workflow end to end and writes the HTML report. `quick` is triage: recon + the catalogs `scan.py` points at, a ranked list in the terminal, labelled as not-an-audit. |
| `/audit-report [json] [html]` | Validates and regenerates the report. |

Every script is stdlib-only and has a `--selftest`:

```bash
S=skills/smartcontract-audit
python $S/scripts/scan.py --selftest
python $S/scripts/slither_to_findings.py --selftest
python $S/scripts/linkcheck.py --selftest
python $S/report/gen_report.py --selftest
```

## `findings.json`

```jsonc
{
  "project": "Acme Staking", "type": "Staking", "chain": "KUB Chain (Bitkub)",
  "commit": "a1b2c3d", "date": "2026-08-31", "auditor": "Claude Code",
  "scope": ["contracts/Staking.sol"],
  "summary": "Executive summary. Markdown-lite: **bold**, `code`, - bullets.",
  "trust_assumptions": ["`owner` is a 3/5 multisig"],
  "findings": [{
    "id": "C-01",                       // prefix matches severity
    "title": "Reentrancy in withdraw() drains the pool",
    "severity": "Critical",             // Critical|High|Medium|Low|Informational
    "status": "Open",                   // Open|Acknowledged|Fixed|Disputed|Unverified
    "location": "Staking.sol:120-135",
    "description": "The mechanism.",
    "code": " function withdraw() external {\n-    token.transfer(msg.sender, a);\n     balance = 0;\n }",
    "impact": "What an attacker gains / users lose.",
    "recommendation": "Specific code-level fix.",
    "fix":  " function withdraw() external nonReentrant {\n+    balance = 0;\n+    token.safeTransfer(msg.sender, a);\n }",
    "references": ["https://swcregistry.io/docs/SWC-107"]
  }]
}
```

In `code` and `fix`, a leading `-` highlights the line red, `+` highlights it
green, anything else is plain context.

## Requirements

Python 3.8+. **No dependencies** — stdlib only.
[Slither](https://github.com/crytic/slither) and
[Foundry](https://github.com/foundry-rs/foundry) are optional and recommended;
neither is required for anything here to run.

## Layout

```
.claude-plugin/
  marketplace.json              makes this repo an installable marketplace
  plugin.json                   plugin manifest
commands/
  audit.md  audit-report.md     slash commands
skills/smartcontract-audit/
  SKILL.md                      the workflow Claude follows
  references/
    methodology.md              severity rubric, EVM catalog, per-chain notes
    arithmetic.md               overflow, casts, precision, contract bricking
    gas.md                      loops, gas griefing, optimization
    staking.md  token.md  lending.md  defi.md
    swap.md  liquidity.md  wallet.md  misc.md
    economics.md                value map, admin levers, unreachable liquidity
    custody.md                  deposit/withdraw, escrow, wrapped receipts
    kub.md                      KAP standards, KUB chain notes
    postmortems.md              checks derived from real 2024-2026 exploits
    examples.md                 upstreams, libraries, OZ advisory versions
  report/
    gen_report.py               JSON -> HTML, plus --validate
    example.findings.json       filled-in sample, 7 findings
  scripts/
    scan.py                     recon pass
    slither_to_findings.py      Slither import
    linkcheck.py                reference-URL checker
```

## Scope & honesty

This skill helps a human auditor work faster and miss less. It does not replace
one, and no report it produces is a guarantee that code is safe. Findings must
have a concrete failure scenario written with numbers — if you can't write one,
it is Informational or it isn't a finding. Every report states what was **not**
audited.

## License

MIT
