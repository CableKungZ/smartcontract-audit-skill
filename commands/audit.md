---
description: Security audit of a Solidity contract or directory. hard (default) = full audit + HTML report; quick = cheap triage list; reaudit <prev.json> = verify fixes and re-run
argument-hint: <path-to-contract-or-dir> [quick|hard|reaudit <prev.json>] [address] [chain]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
model: opus
effort: high
---

Run a smart contract security audit of: **$ARGUMENTS**

The skill lives at `${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/` — call it
**SKILL_DIR**.

**Read `SKILL_DIR/SKILL.md` and follow it exactly.** It is the single
description of this workflow: the modes, the seven mandatory passes, which
catalogs to load, the PoC gate, the self-review pass and the report. Do not skip
steps, and do not write a single finding before the catalog walk is done.

Two things only this file knows:

- **Paths.** `SKILL.md` writes script paths relative to its own directory.
  Prefix each with `${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/`, e.g.
  `python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/scripts/scan.py <path>`.
- **Arguments.** `$ARGUMENTS` carries the target path and, optionally, the mode
  (`quick` / `hard` / `reaudit <previous.findings.json>`), a deployed address
  (→ load `onchain.md`), and the chain. A previous `findings.json` means
  reaudit — do not ask. If no mode was given, ask before starting, per
  SKILL.md's Modes section.

Write `findings.json` and the report next to the audited code unless the user
says otherwise.
