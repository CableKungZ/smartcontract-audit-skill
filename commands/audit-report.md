---
description: Regenerate the HTML report from an existing findings.json
argument-hint: [findings.json] [output.html]
allowed-tools: Read, Bash, Edit
effort: medium
---

Regenerate the audit report. Findings file: **${1:-findings.json}**, output:
**${2:-report.html}**.

1. Validate first and fix every warning — a warning means the report is not
   shippable yet (missing summary, missing trust assumptions, an `Unverified`
   entry left over from Slither, a `TODO` recommendation):

   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/report/gen_report.py --validate ${1:-findings.json}
   ```

2. Generate:

   ```
   python ${CLAUDE_PLUGIN_ROOT}/skills/smartcontract-audit/report/gen_report.py ${1:-findings.json} ${2:-report.html}
   ```

3. Report back the counts by severity, and name the one finding to fix first.

Reminders while editing findings:
- `code` renders red (vulnerable), `fix` renders green (recommended). Inside
  either, prefix a line with `-` for red or `+` for green.
- Recommendations must be code-level and specific. "Add checks" is not a
  recommendation.
- Ids follow severity: `C-`, `H-`, `M-`, `L-`, `I-`.
