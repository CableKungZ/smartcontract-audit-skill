# Roadmap

All seven gaps identified on 2026-09-01 are closed — the PoC gate, the
self-review pass, the test survey, the solc bug check, the on-chain state pass,
the Vyper claim correction, and reaudit mode. What each one does now lives in
the code and in `SKILL.md`; the design notes that got them built are in the
history (`git log`, commits `54d2821` and `6eb1785`).

## Open

- **Full Vyper tooling** — `.vy` parsing in `scan.py` plus a `references/vyper.md`
  catalog. Deliberately not built: the skill states plainly that its catalogs
  apply to Vyper and its tooling does not, which is honest and costs nothing.
  Build it when someone actually audits a Vyper contract with this.

## Conventions for anything added here

- Scripts stay **stdlib-only and offline**. Networked code goes behind an
  explicit `--update` flag that writes a vendored file (see `solc_bugs.py`).
- Every script change extends `_selftest()` in the same file.
- Run `python skills/smartcontract-audit/scripts/linkcheck.py .` before shipping
  anything that adds a URL.
- Plan mode before any new requirement — see `CLAUDE.md`.
- The workflow is described **once**, in `SKILL.md`. `commands/audit.md` points
  at it and adds nothing but path resolution and argument handling.
