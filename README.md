<div align="center">

# 🛡️ Smart Contract Audit Skill

### Make your smart contracts safe.

**A Claude Code skill that audits EVM smart contracts — severity-classified
findings, a mandatory arithmetic & liveness pass, and a self-contained HTML
report showing the vulnerable code in red and the fix in green.**

[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-d97757?style=flat-square)](https://docs.claude.com/en/docs/claude-code/skills)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#requirements)
[![Dependencies](https://img.shields.io/badge/dependencies-none-2f855a?style=flat-square)](#requirements)
[![Chains](https://img.shields.io/badge/chains-EVM%20%2B%20KUB-627eea?style=flat-square)](references/kub.md)

</div>

---

## What it does

Point it at a Solidity contract and it runs a structured audit: recon → catalog
walk → concrete exploit scenarios → severity classification → HTML report.

- **10 vulnerability catalogs**, one per contract type, each with real incidents
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
- **HTML report** — one file, no assets, no network, light/dark aware, prints to
  PDF, with the vulnerable code in red and the recommended fix in green.

## Quick start

```bash
# 1. Recon: external surface, loops, casts, divisions, risk patterns
python scripts/scan.py contracts/

# 2. (optional) Import Slither as a draft — every entry lands "Unverified"
slither contracts/ --json slither.json
python scripts/slither_to_findings.py slither.json > draft.findings.json

# 3. Audit (in Claude Code)
/audit contracts/Staking.sol

# 4. Report
python report/gen_report.py --validate findings.json   # fix every warning
python report/gen_report.py findings.json report.html
```

Or just ask: *"audit this staking contract for KUB Chain"* — the skill
description triggers on its own.

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
[`references/methodology.md`](references/methodology.md).

## Catalogs

| Contract type | Catalog | Covers |
|---|---|---|
| Staking, farms, veToken, LST, NFT staking | [`staking.md`](references/staking.md) | reward accounting, stake/unstake rounding loops, locks, withdrawal queues |
| Tokens — ERC-20/721/1155/4626, KAP | [`token.md`](references/token.md) | mint control, honeypot taxes, permit, rebasing, vault-share inflation |
| Lending, borrowing, CDP | [`lending.md`](references/lending.md) | interest accrual, health factors, liquidation, bad debt, empty-market donation |
| Vaults, perps, bridges, oracles | [`defi.md`](references/defi.md) | oracle manipulation, strategy losses, flash loans, cross-chain replay |
| AMM, routers, aggregators | [`swap.md`](references/swap.md) | slippage/deadline, `k` invariant, V3 callback auth, MEV |
| LP accounting, zaps, V3 managers | [`liquidity.md`](references/liquidity.md) | first-depositor inflation, share rounding, LP pricing |
| Wallets, 4337/7702, timelocks | [`wallet.md`](references/wallet.md) | signature replay, threshold bypass, delegatecall, recovery |
| Launchpad, governance, airdrop, marketplace | [`misc.md`](references/misc.md) | refund paths, flash-loan voting, merkle leaves, auction griefing |
| **Every audit** | [`arithmetic.md`](references/arithmetic.md) | overflow, truncation, precision, **and contract bricking** |
| **Every audit** | [`gas.md`](references/gas.md) | unbounded loops, gas griefing, optimization |
| **Every audit** | [`methodology.md`](references/methodology.md) | severity rubric, general EVM catalog, per-chain notes |
| Reference | [`examples.md`](references/examples.md) | upstreams to diff forks against, libraries, security corpora |
| KUB Chain | [`kub.md`](references/kub.md) | KAP-20/721/1155/22, `adminTransfer`, KYC gating, chain notes |

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
trusted party. See [`references/kub.md`](references/kub.md).

Source: [docs.kubchain.com](https://docs.kubchain.com/quickstart/launching-a-token-on-kub/kap-token-interfaces).

## Tools

| Tool | What it does |
|---|---|
| `scripts/scan.py` | Regex recon: external surface + modifiers, every loop with its bound, every narrowing cast, every division, 19 risk patterns each pointing at the relevant catalog. `--json` for machine output. |
| `scripts/slither_to_findings.py` | Converts `slither --json` into draft findings, mapped one severity level *below* what Slither claims, every entry `Unverified` until a human confirms it. |
| `report/gen_report.py` | `findings.json` → self-contained HTML. `--validate` checks schema, duplicate ids, severity/id-prefix mismatch, leftover `Unverified`, `TODO` recommendations, missing summary or trust assumptions. |
| `/audit <path>` | Runs the whole workflow end to end. |
| `/audit-report [json] [html]` | Validates and regenerates the report. |

Every script is stdlib-only and has a `--selftest`:

```bash
python scripts/scan.py --selftest
python scripts/slither_to_findings.py --selftest
python report/gen_report.py --selftest
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
SKILL.md                        the workflow Claude follows
README.md
references/
  methodology.md                severity rubric, EVM catalog, per-chain notes
  arithmetic.md                 overflow, casts, precision, contract bricking
  gas.md                        loops, gas griefing, optimization
  staking.md  token.md  lending.md  defi.md
  swap.md  liquidity.md  wallet.md  misc.md
  kub.md                        KAP standards, KUB chain notes
  examples.md                   upstreams, libraries, security corpora
report/
  gen_report.py                 JSON -> HTML, plus --validate
  example.findings.json         filled-in sample, 7 findings
scripts/
  scan.py                       recon pass
  slither_to_findings.py        Slither import
.claude/commands/
  audit.md  audit-report.md     slash commands
```

## Scope & honesty

This skill helps a human auditor work faster and miss less. It does not replace
one, and no report it produces is a guarantee that code is safe. Findings must
have a concrete failure scenario written with numbers — if you can't write one,
it is Informational or it isn't a finding. Every report states what was **not**
audited.

## License

MIT
