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

- **15 vulnerability catalogs**, one per contract type, each with real incidents
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
- **Compiler and library versions checked** — every pragma against the solc
  team's own bug list (vendored offline) and every pinned OpenZeppelin version
  against its advisories. A floating pragma is itself a finding: the bytecode
  you audited is not provably the bytecode that shipped.
- **On-chain state, not just source** — for a deployed address: bytecode vs the
  audited source, the real proxy implementation and admin, the real role holders
  behind every privileged function, and the configured parameters.
- **Proof or it didn't happen** — every Critical and High ships with a runnable
  Foundry PoC (command + real output) or a stated waiver; the report generator
  refuses to build without one. Plus a five-question self-review pass that
  downgrades gated findings before delivery, not after.
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

# 3. Audit (in Claude Code) -- no argument works too, it finds the contracts
/audit contracts/Staking.sol

# 4. Report
python $S/report/gen_report.py --validate findings.json   # fix every warning
python $S/report/gen_report.py findings.json report.html
```

## Modes

Asked once, before the scan. Whatever you decline is recorded in the report's
Scope as **not performed**.

| Mode | What it is |
|---|---|
| **Hard** (default) | the audit: every catalog, seven mandatory passes, every file read end to end, a runnable PoC on each Critical/High, `findings.json` → HTML |
| **Quick** | triage, ~⅓ the cost: `scan.py` output plus the lines it flags, terminal list only. May raise an alarm, may never clear one — it is labelled "not an audit" and says so verbatim at the end |
| **Reaudit** | pass a previous `findings.json`: each old finding gets `Fixed` / `Open` / `Acknowledged` at code level, then full Hard passes over the changed code (fixes introduce bugs — see Uranium in `examples.md`). Renders a remediation-status table via `--previous` |

**Parallel execution** is a scheduling detail of Hard, and the skill decides it
itself after recon — parallel above ~600 in-scope lines, >3 files, or ≥3
catalogs; serial below that, and serial for one tightly coupled contract or a
small reaudit. The split is **by pass, not by file**: five subagents (arithmetic
+ liveness / loops + centralization / custody + value accounting / incident
replay / type catalogs), each reading the whole contract, so nothing cross-file
falls between them. Merging, dedup, the cross-cutting pass, PoCs, self-review
and the report all stay in the main context. `parallel` / `serial` as an
argument forces it.

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
| Deposit/withdraw, escrow, wrapped tokens | [`custody.md`](skills/smartcontract-audit/references/custody.md) | operator-cannot-withdraw rule, solvency invariant, the **transfer table** (every value-moving line: `from`, `to`, who authorized it, requested vs moved vs credited), escrow state machine, the no-mint rule for 1:1 wrappers |
| Launchpad, governance, airdrop, marketplace | [`misc.md`](skills/smartcontract-audit/references/misc.md) | refund paths, flash-loan voting, merkle leaves, auction griefing |
| Anything that distributes value | [`economics.md`](skills/smartcontract-audit/references/economics.md) | value map, admin levers, unreachable liquidity, sequenced remediation |
| **Every audit** | [`arithmetic.md`](skills/smartcontract-audit/references/arithmetic.md) | the **breaking point** of every expression — the exact input, the expected value, the actual value — plus overflow, truncation, precision **and contract bricking** |
| **Every audit** | [`gas.md`](skills/smartcontract-audit/references/gas.md) | unbounded loops, gas griefing, optimization, and the **three-option fix pass** — sketch a guard / a restructure / a new mechanism, ship the cheapest that fully removes the bug without looping or over-engineering |
| **Every audit** | [`methodology.md`](skills/smartcontract-audit/references/methodology.md) | severity rubric, general EVM catalog, self-review pass, per-chain notes |
| **Every audit** | [`postmortems.md`](skills/smartcontract-audit/references/postmortems.md) | checks derived from real 2024-2026 exploits: paired-rounding, wrong overflow checks, donation on fresh markets, cross-chain verifier config, uninitialized proxies, EIP-7702 |
| Already deployed | [`onchain.md`](skills/smartcontract-audit/references/onchain.md) | `cast` cookbook: bytecode vs source, real proxy impl/admin, real role holders, configured params, messaging config |
| Reference | [`examples.md`](skills/smartcontract-audit/references/examples.md) | upstreams to diff forks against, libraries, OpenZeppelin advisory versions, security corpora |
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
| `scripts/scan.py` | Regex recon: external surface + modifiers, every loop with its bound, every narrowing cast, every division, 27 risk patterns each pointing at the relevant catalog, the contract type inferred from identifiers (with a name-vs-body check), and the project's own test coverage (unit / fuzz / invariant). |
| `scripts/slither_to_findings.py` | Converts `slither --json` into draft findings, mapped one severity level *below* what Slither claims, every entry `Unverified` until a human confirms it. |
| `scripts/linkcheck.py` | Verifies every reference URL still resolves — a report citing a 404 is a report the reader stops trusting. Exit code = dead links, so it drops into CI. |
| `report/gen_report.py` | `findings.json` → self-contained HTML. `--validate` checks schema, duplicate ids, severity/id-prefix mismatch, leftover `Unverified`, `TODO` recommendations, missing summary or trust assumptions, and **errors** on a Critical/High with no runnable PoC and no waiver. |
| `/audit <path> [quick\|hard\|reaudit <prev.json>]` | `hard` (default) runs the whole workflow end to end and writes the HTML report. `quick` is triage: recon + the catalogs `scan.py` points at, a ranked list in the terminal, labelled as not-an-audit. `reaudit` verifies each previous finding's fix and re-runs the passes over the changed code. |
| `scripts/solc_bugs.py` | The solc team's own bug list, vendored offline. `solc_bugs.py '^0.8.13'` prints what can bite that pragma; `--update` refreshes the data. `scan.py` calls it for every file. |
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

    // Required on every Critical/High: a proof that runs. Without `poc` or a
    // `poc_waiver`, --validate errors and the report will not generate.
    "poc": {
      "file": "test/PoC_C01.t.sol",
      "command": "forge test --mt test_PoC_C01 -vvv",
      "output": "[FAIL] test_PoC_C01()\n  attacker balance: 0 -> 412.5 ETH"
    },
    "poc_waiver": "…only when a PoC is genuinely impossible; say why",

    "review_note": "Outcome of the self-review pass: the surviving precondition.",
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
    arithmetic.md               breaking-point table (expected vs actual at the
                                exact input), overflow, casts, precision, bricking
    gas.md                      loops, gas griefing, optimization, choosing
                                the cheapest fix that still holds
    staking.md  token.md  lending.md  defi.md
    swap.md  liquidity.md  wallet.md  misc.md
    economics.md                value map, admin levers, unreachable liquidity
    custody.md                  deposit/withdraw, the per-transfer-line table,
                                escrow, wrapped receipts
    kub.md                      KAP standards, KUB chain notes
    postmortems.md              checks derived from real 2024-2026 exploits
    onchain.md                  cast cookbook for deployed contracts
    examples.md                 upstreams, libraries, OZ advisory versions
  report/
    gen_report.py               JSON -> HTML, plus --validate
    example.findings.json       filled-in sample, 7 findings
  scripts/
    scan.py                     recon pass
    solc_bugs.py + .json        solc bug list per pragma (vendored, offline)
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
