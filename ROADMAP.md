# Roadmap — 7 known gaps

Written 2026-09-01, after the `postmortems.md` / quick-hard / type-inference
work landed in `5fb4361`. Each item is self-contained: a cold session can pick
one, read the named files, and ship it without re-deriving the analysis.

Ordered by value. **Do 1 and 2 first** — they are the two that change report
quality, not just report surface.

Conventions that apply to every item:

- Scripts stay **stdlib-only and offline**. Anything needing the network is a
  separate `--update` flag that writes a vendored file, never a runtime fetch.
- Every script change extends `_selftest()` in the same file.
- Run `python skills/smartcontract-audit/scripts/linkcheck.py .` before
  committing anything that adds a URL.
- Keep `SKILL.md` and `commands/audit.md` in sync — they describe the same
  workflow to two different readers, and drift between them is a real bug.

---

## 1. PoC gate for Critical / High findings

**Why.** The skill asks for "a concrete failure scenario with numbers" but
nothing forces a *runnable* proof. A Critical that cannot be reproduced in a
test is an opinion, and it is how audits ship false positives. This is the
single biggest quality lever left.

**Design.**

- `report/gen_report.py`:
  - Add an optional finding field `poc` — an object
    `{"file": "test/PoCReentrancy.t.sol", "command": "forge test --mt test_PoC_H01 -vvv", "output": "…assertion that fails on the vulnerable code…"}`.
  - Validator: **error** (not warning) when a `Critical` or `High` finding has
    no `poc` *and* no `poc_waiver` string explaining why one is impossible
    (e.g. the finding is centralization, or the repo has no test harness).
  - Render it in the HTML as a third block under the red/green pair —
    a monospace "Proof of concept" panel with the command and the failing output.
- `SKILL.md` step 3/4 and `commands/audit.md` step 4/6: state that a Critical or
  High is not finished until the PoC runs and fails against the unfixed code and
  passes against the fix.
- `references/methodology.md`: one paragraph — "a finding you cannot reproduce
  is Informational until you can", with the waiver categories listed.

**Files.** `report/gen_report.py`, `report/example.findings.json` (add a `poc`
to its Critical entry), `SKILL.md`, `commands/audit.md`,
`references/methodology.md`, `README.md` (the findings-schema block near line 191).

**Done when.** `--validate` fails on a High with no `poc` and no waiver;
`example.findings.json` still validates clean; the HTML shows the PoC block.

---

## 2. solc version bug check

**Why.** We now check the pinned OpenZeppelin version against advisories
(`references/examples.md`) but the compiler gets a free pass — `scan.py` prints
`pragma` and never judges it. Real, exploited-class compiler bugs live in
versions people still pin: optimizer removing memory writes in inline assembly
(0.8.13–0.8.14), storage write removal, ABI encoder head overflow, `verbatim`
issues. Exact parallel to item 2's OZ table, one layer down.

**Design.**

- Vendor `scripts/solc_bugs.json`, generated from the official
  `https://raw.githubusercontent.com/ethereum/solidity/develop/docs/bugs_by_version.json`
  by `python scripts/solc_bugs.py --update` (the only networked code; urllib,
  stdlib). Commit the generated file so the audit path stays offline.
- `scan.py`: parse the pragma range per file, resolve which vendored versions
  satisfy it, and print a new section:

  ```
  === COMPILER (pragma vs known solc bugs) ===
    Vault.sol   pragma ^0.8.13
       floating pragma -- the deployed bytecode may not be what you audited
       0.8.13/0.8.14: InlineAssemblyMemorySideEffects -- optimizer may remove
       memory writes in assembly blocks   [severity: medium]
       -> pin an exact version >= 0.8.17 and state it in the report
  ```

  Flag three separate things: (a) a floating `^`/`>=` pragma, (b) any known bug
  in a satisfying version, (c) a pragma older than 0.8.0 (unchecked arithmetic
  everywhere — every `arithmetic.md` finding gets more severe).
- `references/methodology.md`: short subsection "Compiler version" saying the
  audit must record the exact `solc` used for the deployed bytecode, and that a
  floating pragma is a finding on its own (Low, or Medium if the range spans a
  buggy version).

**Files.** `scripts/solc_bugs.py` (new), `scripts/solc_bugs.json` (generated),
`scripts/scan.py`, `references/methodology.md`, `README.md` (tools table),
`SKILL.md` step 0.

**Done when.** `scan.py` on a file pinned to `^0.8.13` prints the
`InlineAssemblyMemorySideEffects` line; `--selftest` covers it; the check works
with no network.

---

## 3. On-chain state verification for deployed contracts

**Why.** The audit reads source; the risk lives on-chain. Who *actually* holds
`owner` today, what the proxy admin is, whether the deployed bytecode matches
the audited source, what the immutable args are, what the bridge's verifier
config is set to (`postmortems.md` §5 asks for this and gives no procedure).

**Design.**

- New `references/onchain.md`, loaded whenever the contract is already deployed:
  a `cast` cookbook, one line per question —
  `cast code`, `cast storage` for the ERC-1967 implementation/admin slots
  (`0x360894...bbc` / `0xb53127...103`), `cast call owner()`, `cast call
  paused()`, role holders via `hasRole`, `getRoleMemberCount`, timelock
  `getMinDelay`, LayerZero `getConfig`, plus block explorer verification
  ("is the source verified, and does it match the repo commit?").
- A checklist ending in a table the report must contain: *role → address →
  EOA/multisig/timelock → threshold → delay → loss on compromise today*. The
  centralization pass currently asks for this from source; here it gets the real
  addresses.
- `SKILL.md` step 2 and `commands/audit.md` step 3: if an address was given,
  run this pass and put the table in the report; if not, say in Scope that the
  audit covers source only and on-chain state was not verified.

**Files.** `references/onchain.md` (new), `SKILL.md`, `commands/audit.md`,
`README.md` layout block.

**Done when.** An audit given a deployed address produces the role/address
table, and one given only source explicitly says on-chain state was unverified.

---

## 4. Self-review pass before the report ships

**Why.** Nothing currently challenges a finding after it is written — the
validator checks schema, not substance. Ship-time is when a gated exploit
should get downgraded, not after the client's dev team finds the gate.

**Design.** A new step between "Classify" and "Write findings.json" in both
`SKILL.md` and `commands/audit.md`. For every finding, answer in one line each:

1. What precondition makes this **not** exploitable? Name it or state there is
   none.
2. Does another modifier, guard, or caller in this repo already block it?
   (grep the callers — the same reflex as a root-cause bug fix.)
3. Does the PoC (item 1) actually fail on the unfixed code?
4. Would the recommended fix break any other caller of the same function?
5. Is the severity still right after 1–4?

Findings that fail 1 or 2 get downgraded or dropped with the mitigating factor
named — never silently deleted, since a dropped-then-rediscovered finding is
worse than an Informational. Add a `review_note` field to the schema for the
kept ones, rendered small under the impact block.

**Files.** `SKILL.md`, `commands/audit.md`, `report/gen_report.py` (optional
`review_note` field + render), `references/methodology.md`.

**Done when.** The workflow has the five questions verbatim and the report
renders `review_note` when present.

---

## 5. Vyper: support it or stop claiming it

**Why.** `SKILL.md`'s description says "Solidity/Vyper" but `scan.py` is
Solidity-only regex, no `.vy` is ever collected, and no catalog covers Vyper
idioms. Claiming a language the tooling ignores is exactly the name-vs-body
mismatch the skill now tells auditors to file against other people's code.

**Design — pick one, do not half-do it.**

- **Cheap (recommended):** drop "Vyper" from the frontmatter description and
  README, and add one line to `methodology.md`: Vyper contracts are out of
  scope for the tooling; audit them manually against the same catalogs, noting
  the differences that matter (no `unchecked`, different reentrancy-lock
  semantics — the Curve 2023 incident is already cited in `swap.md`).
- **Full:** teach `scan.py` `.vy` — `def name(...)` instead of `function`,
  `@external`/`@internal`/`@payable` decorators, `# pragma version`,
  `@nonreentrant` locks, `raw_call`, `send`, `selfdestruct`. Then a
  `references/vyper.md` covering the reentrancy-lock class, `raw_call` gas
  forwarding, and version-specific compiler bugs (the 0.2.15/0.2.16/0.3.0 lock
  bug that cost Curve ~$70M — the direct Vyper analogue of item 2).

**Files.** cheap: `SKILL.md`, `README.md`, `references/methodology.md`.
Full: adds `scripts/scan.py`, `references/vyper.md`.

**Done when.** The claim and the capability agree, whichever direction it went.

---

## 6. Re-audit mode

**Why.** `findings.json` already has `status: Fixed | Acknowledged | Disputed`
and nothing in the workflow ever produces it. Clients re-audit after
remediation almost every time, and today that means re-running a full audit and
hand-editing statuses.

**Design.**

- `/audit <path> reaudit <previous.findings.json>` — a third mode alongside
  `quick` / `hard` (`SKILL.md`'s Modes section, `commands/audit.md` step 0).
- Procedure: `git diff <audited-commit>..HEAD` for the scope; for each previous
  finding, verify the fix at the code level and set `Fixed` (with the commit
  and a line reference), `Open` (with why the fix is incomplete — the most
  valuable output of a re-audit), or `Acknowledged`. Then run the **full** hard
  passes over the *changed* code only, because fixes introduce findings —
  Uranium is in `examples.md` for exactly this.
- `gen_report.py`: `--previous prev.findings.json` renders a remediation-status
  table at the top (id, title, severity, then → now) and marks new findings
  introduced by the fix.

**Files.** `SKILL.md`, `commands/audit.md`, `report/gen_report.py`,
`report/example.findings.json` (a `Fixed` entry), `README.md`.

**Done when.** A re-audit run produces a report whose first table is the
previous findings with their new status, and new findings are visibly marked.

---

## 7. Assess the repo's own tests

**Why.** Whether a project has fuzz/invariant tests predicts its bug density
better than almost anything else in the repo, and the report never mentions it.
It is also the cheapest recommendation to make concrete.

**Design.**

- `scan.py`: detect the harness (`foundry.toml`, `hardhat.config.*`,
  `test/**/*.t.sol`, `*.test.ts`), count test files, and count
  `invariant_` / `testFuzz_` / `function test` occurrences. Print:

  ```
  === TESTS ===
    foundry.toml found, 14 test files, 92 unit tests, 0 invariant, 3 fuzz
    -> no invariant tests: the arithmetic and custody passes have no safety net
  ```

- The report gains a short "Test coverage" paragraph in the method section, and
  where invariants are missing, the recommendation names the specific ones this
  contract needs (solvency, principal-always-withdrawable, supply-vs-custody —
  `custody.md` and `arithmetic.md` already state them).

**Files.** `scripts/scan.py`, `SKILL.md` step 0 and step 5,
`references/methodology.md`.

**Done when.** `scan.py` reports the harness and invariant count, and the
report template asks for the paragraph.

---

## Suggested sequencing

| Order | Item | Rough size |
|---|---|---|
| 1 | **1. PoC gate** | medium — validator + schema + docs |
| 2 | **2. solc bug check** | medium — one new script + a vendored json |
| 3 | **7. Test assessment** | small — it is one more `scan.py` section |
| 4 | **4. Self-review pass** | small — mostly prose in two files |
| 5 | **5. Vyper decision** | small if cheap path, large if full |
| 6 | **3. On-chain verification** | medium — a new catalog |
| 7 | **6. Re-audit mode** | large — touches the report generator |

Items 1, 4 and 7 together are what turns the output from "a list of suspicions"
into "a report someone can act on and check". Do them as one arc if there is
time for only one arc.
