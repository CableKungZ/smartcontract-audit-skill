# Working on this repo

This repo is a Claude Code plugin: prompt files, not an application. A
"requirement" here is a paragraph in `SKILL.md` or a catalog, and prose sprawls
far more easily than code does.

## Plan first, always

**Enter plan mode before adding or changing any requirement**, however small it
sounds. Ask for the plan even when the request looks like a one-line edit —
"also check X" has a way of becoming a new section, a new pass, and a new
argument. The plan states, in this order:

1. **Which single file** the change lands in. The workflow is described **once**,
   in `SKILL.md`; catalogs hold the checks; `commands/audit.md` holds nothing but
   path resolution and argument handling. A change touching three files is
   usually the wrong shape.
2. **What it replaces.** New guidance that overlaps existing guidance must say
   which paragraph it supersedes. Two rules on the same subject means the audit
   follows whichever it reads last.
3. **The cost per run.** Every added requirement is paid on every audit, in
   tokens and in time. Say what it costs and what it catches. If it cannot name
   a finding class it would have caught, it does not go in.
4. **Where it is enforced.** A requirement nobody checks is a comment. Name the
   step in `SKILL.md`, the validator warning in `gen_report.py`, or the section
   of the report it must appear in.

Then wait for approval. Do not batch unrelated requirements into one plan.

## The rest

Conventions for scripts, links and the single-source rule are in `ROADMAP.md`.
