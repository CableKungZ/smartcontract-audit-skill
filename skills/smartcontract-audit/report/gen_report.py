#!/usr/bin/env python3
"""Render an audit findings JSON into a single self-contained HTML report.

    python report/gen_report.py findings.json report.html

findings.json shape (everything except `findings` is optional):

{
  "project":  "Acme Staking",
  "type":     "Staking",                  # contract category
  "chain":    "KUB Chain (Bitkub)",
  "commit":   "a1b2c3d",
  "date":     "2026-08-31",
  "auditor":  "Claude Code",
  "scope":    ["contracts/Staking.sol", "contracts/Rewards.sol"],
  "summary":  "Two paragraphs of executive summary. Markdown-lite.",
  "trust_assumptions": ["Owner is a 3/5 Gnosis Safe", "Reward token is trusted"],

  // Optional. Free-form analysis sections rendered after the findings:
  // economic analysis, peer benchmarking, parameter appendices, method notes.
  // Each has a title, optional markdown-lite body, and an optional table.
  "sections": [
    {
      "title": "Capital efficiency — stranded value",
      "body": "Prose, **bold**, `code`, - bullets.",
      "table": {
        "headers": ["Dump scenario", "KUB left", "Stranded %"],
        "rows": [["Float only", "881.8", "37.4%"]],
        "highlight": 2            // optional: emphasise this column (0-based)
      }
    }
  ],

  // Optional. Tiered remediation roadmap, rendered last. Tier 0 is the gate.
  "roadmap": [
    {"tier": "0 (gate)", "scope": "Value-extraction levers",
     "fixes": "Burn the residual; snapshot params; cap the fee",
     "closes": ["C-01", "C-02", "H-01"], "outcome": "Safe to operate"}
  ],

  "findings": [
    {
      "id": "C-01",
      "title": "Reentrancy in withdraw() drains the pool",
      "severity": "Critical",            # Critical|High|Medium|Low|Informational
      "status": "Open",                  # Open|Acknowledged|Fixed|Disputed
      "location": "Staking.sol:120-135",
      "description": "The mechanism, in prose.",
      "impact": "What an attacker gains / users lose.",
      "recommendation": "Specific code-level fix.",
      "code": "function withdraw(uint256 a) external {\\n    ...\\n}",
      "fix":  "function withdraw(uint256 a) external nonReentrant {\\n    ...\\n}",

      // REQUIRED on every Critical and High: a runnable proof. A finding you
      // cannot reproduce is an opinion. `output` is the real failing output,
      // pasted, not paraphrased.
      "poc": {
        "file": "test/PoC_C01.t.sol",
        "command": "forge test --mt test_PoC_C01 -vvv",
        "output": "[FAIL] test_PoC_C01()\\n  attacker balance: 0 -> 412.5 ETH"
      },
      // ...or, when a PoC is genuinely impossible (centralization findings, no
      // test harness in the repo, an off-chain precondition), say why:
      "poc_waiver": "Centralization: requires the owner key, not reproducible.",

      // Optional. The outcome of the self-review pass — the precondition that
      // gates this, or what was checked before keeping it at this severity.
      "review_note": "Reachable from any caller; no guard elsewhere in the repo.",
      "references": ["https://..."]
    }
  ]
}

Markdown-lite in text fields: `code`, **bold**, blank-line paragraphs, and
- bullet lists. Nothing else. Stdlib only.

Code blocks — `code` renders as the VULNERABLE block (red), `fix` as the
RECOMMENDED block (green). Inside either block, per-line highlighting uses
unified-diff prefixes on the lines you want to call out:

    "-" at line start  -> red   (the offending line)
    "+" at line start  -> green (the fixed line)
    " " or nothing     -> plain context

So a `code` block with no prefixes is entirely red-tinted; use prefixes when
you want to point at specific lines inside a larger snippet.
"""

import html
import json
import re
import sys
from datetime import date

SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]
SEV_KEY = {s: s.lower()[:4] for s in SEVERITIES}  # crit high medi low  info


def md(text):
    """Escape, then apply markdown-lite: paragraphs, - bullets, `code`, **bold**."""
    if not text:
        return ""
    out = []
    for block in re.split(r"\n\s*\n", str(text).strip()):
        lines = block.split("\n")
        if all(l.lstrip().startswith(("- ", "* ")) for l in lines if l.strip()):
            items = "".join(f"<li>{inline(l.lstrip()[2:])}</li>" for l in lines if l.strip())
            out.append(f"<ul>{items}</ul>")
        else:
            out.append("<p>" + inline(" ".join(lines)) + "</p>")
    return "".join(out)


def inline(text):
    t = html.escape(str(text))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


CSS = """
:root{--bg:#f7f7f6;--card:#fff;--ink:#1b1b1a;--muted:#6b6b68;--line:#e2e2df;
--crit:#b3261e;--high:#c2410c;--medi:#a16207;--low:#0e7490;--info:#57534e;
--bad:#b3261e;--bad-bg:#fdeceb;--bad-b:#f2c4c0;
--good:#12693f;--good-bg:#e9f6ee;--good-b:#b8ddc7;
--poc:#0e7490;--poc-bg:#e6f4f7;--poc-b:#b6dbe4;}
@media(prefers-color-scheme:dark){:root{--bg:#141414;--card:#1c1c1b;--ink:#eceae5;
--muted:#9a9a95;--line:#2e2e2c;--crit:#f2705f;--high:#f59e6b;--medi:#e0b355;
--low:#5cc5d8;--info:#a8a29e;
--bad:#f2705f;--bad-bg:#331b19;--bad-b:#5c2b26;
--good:#5fd497;--good-bg:#15291f;--good-b:#26543c;
--poc:#5cc5d8;--poc-bg:#14262b;--poc-b:#25454e;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.65 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:48px 24px 96px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);
margin:44px 0 14px;font-weight:600}
h3{font-size:17px;margin:0;letter-spacing:-.01em}
p{margin:0 0 12px}ul{margin:0 0 12px;padding-left:20px}
code{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;
background:color-mix(in srgb,var(--ink) 8%,transparent);padding:1px 5px;border-radius:4px}
pre{background:color-mix(in srgb,var(--ink) 6%,transparent);border:1px solid var(--line);
border-radius:8px;padding:14px;overflow-x:auto;margin:0 0 14px}
pre code{background:none;padding:0}
.blk{border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:0 0 14px}
.blk>b{display:block;font-size:11px;font-weight:600;text-transform:uppercase;
letter-spacing:.08em;padding:7px 14px;border-bottom:1px solid var(--line)}
.blk pre{border:0;border-radius:0;margin:0;background:none}
.blk.bad{border-color:var(--bad-b)}
.blk.bad>b{background:var(--bad-bg);color:var(--bad);border-bottom-color:var(--bad-b)}
.blk.good{border-color:var(--good-b)}
.blk.good>b{background:var(--good-bg);color:var(--good);border-bottom-color:var(--good-b)}
.blk.poc{border-color:var(--poc-b)}
.blk.poc>b{background:var(--poc-bg);color:var(--poc);border-bottom-color:var(--poc-b)}
.blk.poc .cmd{display:block;padding:10px 14px 0;font:12px ui-monospace,monospace;color:var(--poc)}
.rv{font-size:13px;color:var(--muted);border-left:2px solid var(--line);
padding:2px 0 2px 12px;margin:0 0 14px}
.nopoc{font-size:12px;color:var(--muted);border:1px dashed var(--line);
border-radius:8px;padding:9px 12px;margin:0 0 14px}
.ln{display:block;padding:0 14px;margin:0 -14px}
.ln.d{background:var(--bad-bg);box-shadow:inset 3px 0 var(--bad)}
.ln.a{background:var(--good-bg);box-shadow:inset 3px 0 var(--good)}
.sub{color:var(--muted);margin:0 0 28px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;
background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px}
.meta div span{display:block;font-size:11px;text-transform:uppercase;
letter-spacing:.08em;color:var(--muted);margin-bottom:3px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
tbody tr:last-child td{border-bottom:none}
.tally{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px}
.tally div{flex:1 1 130px;background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--sev);border-radius:8px;padding:12px 14px}
.tally b{display:block;font-size:26px;line-height:1.1}
.tally span{font-size:12px;color:var(--muted)}
.f{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--sev);
border-radius:10px;padding:20px 22px;margin-bottom:16px}
.f header{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:4px}
.pill{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
color:var(--sev);border:1px solid var(--sev);border-radius:99px;padding:2px 9px}
.st{font-size:11px;color:var(--muted);border:1px solid var(--line);
border-radius:99px;padding:2px 9px}
.loc{font:12px ui-monospace,monospace;color:var(--muted);margin:0 0 14px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
color:var(--muted);font-weight:600;margin:14px 0 4px}
.crit{--sev:var(--crit)}.high{--sev:var(--high)}.medi{--sev:var(--medi)}
.low{--sev:var(--low)}.info{--sev:var(--info)}
a{color:inherit}
.tw{overflow-x:auto;margin:0 0 14px}
th.hi,td.hi{color:var(--crit);font-weight:600}
.an{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:20px 22px;margin-bottom:16px}
.an h3{margin:0 0 10px}
.an table{margin-top:4px}
.rm{display:flex;flex-direction:column;gap:12px}
.tier{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);
border-radius:10px;padding:16px 20px}
.tier.gate{border-left-color:var(--crit)}
.th{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:8px}
.th b{font-size:16px}
.th span{color:var(--muted)}
.th em{font-style:normal;font-size:11px;font-weight:700;text-transform:uppercase;
letter-spacing:.06em;color:var(--crit);border:1px solid var(--crit);
border-radius:99px;padding:2px 9px}
.cl{font-size:13px;color:var(--muted)}
.cl a{font:12px ui-monospace,monospace;border:1px solid var(--line);
border-radius:4px;padding:1px 5px;text-decoration:none;margin-right:3px}
.oc{font-size:13px;font-weight:600;margin:0}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
font-size:12px;color:var(--muted)}
@media print{body{background:#fff}.f,.meta,.tally div{break-inside:avoid}}
"""


def table_html(t):
    """Render {headers, rows, highlight?} as a scrollable table."""
    hi = t.get("highlight")
    head = "".join(
        f'<th{" class=hi" if hi == i else ""}>{inline(h)}</th>'
        for i, h in enumerate(t.get("headers") or []))
    body = "".join(
        "<tr>" + "".join(
            f'<td{" class=hi" if hi == i else ""}>{inline(c)}</td>'
            for i, c in enumerate(row)) + "</tr>"
        for row in t.get("rows") or [])
    return (f'<div class="tw"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def sections_html(sections):
    out = []
    for s in sections:
        out.append('<section class="an">')
        if s.get("title"):
            out.append(f'<h3>{inline(s["title"])}</h3>')
        if s.get("body"):
            out.append(md(s["body"]))
        if s.get("table"):
            out.append(table_html(s["table"]))
        out.append("</section>")
    return "".join(out)


def roadmap_html(rows):
    """Tiered remediation roadmap. The first tier is rendered as the gate."""
    out = ['<div class="rm">']
    for i, r in enumerate(rows):
        gate = i == 0
        out.append(f'<div class="tier{" gate" if gate else ""}">')
        out.append('<div class="th">'
                   f'<b>Tier {inline(r.get("tier", i))}</b>'
                   f'<span>{inline(r.get("scope", ""))}</span>'
                   + ('<em>hard gate</em>' if gate else "") + "</div>")
        if r.get("fixes"):
            out.append(md(r["fixes"]))
        closes = r.get("closes") or []
        if closes:
            out.append('<p class="cl">Closes: ' + " ".join(
                f'<a href="#{html.escape(str(c))}">{html.escape(str(c))}</a>'
                for c in closes) + "</p>")
        if r.get("outcome"):
            out.append(f'<p class="oc">→ {inline(r["outcome"])}</p>')
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def code_block(src, kind):
    """Render a snippet. kind='bad' (red) or 'good' (green).

    Lines prefixed '-' render red, '+' green, anything else plain."""
    label = "Vulnerable code" if kind == "bad" else "Recommended fix"
    lines = []
    for raw in str(src).rstrip("\n").split("\n"):
        cls = {"-": " d", "+": " a"}.get(raw[:1], "")
        body = raw[1:] if raw[:1] in "-+ " else raw
        lines.append(f'<span class="ln{cls}">{html.escape(body) or "&nbsp;"}</span>')
    # joined with "" — each line is display:block, so a literal \n inside the
    # <pre> would render as a second blank line.
    return (f'<div class="blk {kind}"><b>{label}</b><pre><code>'
            + "".join(lines) + "</code></pre></div>")


def poc_block(p):
    """Render a proof of concept: the command, then its real output."""
    cmd = str(p.get("command") or "").strip()
    out = str(p.get("output") or "").rstrip("\n")
    where = str(p.get("file") or "").strip()
    label = "Proof of concept" + (f" &middot; {html.escape(where)}" if where else "")
    body = ""
    if cmd:
        body += f'<span class="cmd">$ {html.escape(cmd)}</span>'
    if out:
        lines = "".join(f'<span class="ln">{html.escape(l) or "&nbsp;"}</span>'
                        for l in out.split("\n"))
        body += f"<pre><code>{lines}</code></pre>"
    return f'<div class="blk poc"><b>{label}</b>{body}</div>'


def finding_html(f):
    sev = f.get("severity", "Informational")
    k = SEV_KEY.get(sev, "info")
    parts = [f'<article class="f {k}" id="{html.escape(str(f.get("id","")))}">']
    parts.append("<header>")
    parts.append(f'<span class="pill">{html.escape(sev)}</span>')
    parts.append(f'<h3>{html.escape(str(f.get("id","")))} &middot; {inline(f.get("title",""))}</h3>')
    parts.append(f'<span class="st">{html.escape(str(f.get("status","Open")))}</span>')
    parts.append("</header>")
    if f.get("location"):
        parts.append(f'<p class="loc">{html.escape(str(f["location"]))}</p>')
    parts.append('<div class="lbl">Description</div>' + md(f.get("description")))
    if f.get("code"):
        parts.append(code_block(f["code"], "bad"))
    if f.get("impact"):
        parts.append('<div class="lbl">Impact</div>' + md(f["impact"]))
    if f.get("recommendation"):
        parts.append('<div class="lbl">Recommendation</div>' + md(f["recommendation"]))
    if f.get("fix"):
        parts.append(code_block(f["fix"], "good"))
    if f.get("poc"):
        parts.append(poc_block(f["poc"]))
    elif f.get("poc_waiver"):
        parts.append(f'<p class="nopoc">No proof of concept: '
                     f'{inline(f["poc_waiver"])}</p>')
    if f.get("review_note"):
        parts.append(f'<p class="rv">{inline(f["review_note"])}</p>')
    refs = f.get("references") or []
    if refs:
        links = "".join(f'<li><a href="{html.escape(r)}">{html.escape(r)}</a></li>' for r in refs)
        parts.append(f'<div class="lbl">References</div><ul>{links}</ul>')
    parts.append("</article>")
    return "".join(parts)


def build(d):
    findings = sorted(
        d.get("findings", []),
        key=lambda f: (SEVERITIES.index(f.get("severity", "Informational"))
                       if f.get("severity") in SEVERITIES else 99, str(f.get("id", ""))),
    )
    counts = {s: sum(1 for f in findings if f.get("severity") == s) for s in SEVERITIES}
    title = f'{d.get("project", "Smart Contract")} — Security Audit'

    meta = [("Contract type", d.get("type")), ("Chain", d.get("chain")),
            ("Commit", d.get("commit")), ("Date", d.get("date") or date.today().isoformat()),
            ("Auditor", d.get("auditor")), ("Findings", str(len(findings)))]
    meta_html = "".join(f"<div><span>{html.escape(k)}</span>{html.escape(str(v))}</div>"
                        for k, v in meta if v)

    tally = "".join(
        f'<div class="{SEV_KEY[s]}"><b>{counts[s]}</b><span>{s}</span></div>' for s in SEVERITIES)

    rows = "".join(
        f'<tr><td><a href="#{html.escape(str(f.get("id","")))}">{html.escape(str(f.get("id","")))}</a></td>'
        f'<td>{inline(f.get("title",""))}</td>'
        f'<td class="{SEV_KEY.get(f.get("severity"),"info")}">'
        f'<span class="pill">{html.escape(str(f.get("severity","")))}</span></td>'
        f'<td>{html.escape(str(f.get("status","Open")))}</td></tr>' for f in findings)

    head = f"<title>{html.escape(title)}</title><style>{CSS}</style>"
    s = ['<div class="wrap">']
    s.append(f"<h1>{html.escape(title)}</h1>")
    s.append(f'<p class="sub">Severity-classified findings with impact analysis and remediation.</p>')
    if meta_html:
        s.append(f'<div class="meta">{meta_html}</div>')
    if d.get("scope"):
        s.append("<h2>Scope</h2><ul>" +
                 "".join(f"<li><code>{html.escape(str(x))}</code></li>" for x in d["scope"]) + "</ul>")
    if d.get("summary"):
        s.append("<h2>Executive summary</h2>" + md(d["summary"]))
    s.append(f'<h2>Findings by severity</h2><div class="tally">{tally}</div>')
    if rows:
        s.append("<h2>Summary of findings</h2><table><thead><tr><th>ID</th><th>Title</th>"
                 f"<th>Severity</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>")
    if d.get("trust_assumptions"):
        s.append("<h2>Trust assumptions &amp; out of scope</h2><ul>" +
                 "".join(f"<li>{inline(x)}</li>" for x in d["trust_assumptions"]) + "</ul>")
    s.append("<h2>Detailed findings</h2>")
    s.append("".join(finding_html(f) for f in findings) or "<p>No findings reported.</p>")
    if d.get("sections"):
        s.append("<h2>Analysis</h2>" + sections_html(d["sections"]))
    if d.get("roadmap"):
        s.append("<h2>Remediation roadmap</h2>" + roadmap_html(d["roadmap"]))
    s.append("<footer>This report covers only the code and commit listed in Scope. "
             "It is not a guarantee that the code is free of vulnerabilities.</footer></div>")
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + head + "</head><body>" + "".join(s) + "</body></html>")


STATUSES = {"Open", "Acknowledged", "Fixed", "Disputed", "Unverified"}
REQUIRED = ("id", "title", "severity", "location",
            "description", "impact", "recommendation")


def validate(d):
    """Return (errors, warnings). Errors block generation, warnings don't."""
    errs, warns = [], []
    findings = d.get("findings")
    if not isinstance(findings, list):
        return ["`findings` must be a list"], []
    if not d.get("project"):
        warns.append("no `project` name")
    if not d.get("summary"):
        warns.append("no `summary` — a report without an executive summary is unfinished")
    if not d.get("trust_assumptions"):
        warns.append("no `trust_assumptions` — state what you did NOT audit")

    seen = {}
    for i, f in enumerate(findings):
        who = f.get("id") or f"findings[{i}]"
        for k in REQUIRED:
            if not f.get(k):
                (errs if k in ("id", "title", "severity") else warns).append(
                    f"{who}: missing `{k}`")
        sev = f.get("severity")
        if sev and sev not in SEVERITIES:
            errs.append(f"{who}: severity {sev!r} not one of {SEVERITIES}")
        st = f.get("status", "Open")
        if st not in STATUSES:
            warns.append(f"{who}: unknown status {st!r} (expected one of {sorted(STATUSES)})")
        if st == "Unverified":
            warns.append(f"{who}: still marked Unverified — confirm or drop it before shipping")
        fid = f.get("id")
        if fid in seen:
            errs.append(f"duplicate id {fid!r} (also at findings[{seen[fid]}])")
        elif fid:
            seen[fid] = i
            want = SEV_PREFIX.get(sev)
            if want and not str(fid).upper().startswith(want + "-"):
                warns.append(f"{who}: id should start with {want}- for a {sev} finding")
        rec = str(f.get("recommendation", "")).strip().lower()
        if rec.startswith("todo") or rec in ("add checks", "add validation"):
            warns.append(f"{who}: recommendation is not specific enough")
        if f.get("fix") and not f.get("code"):
            warns.append(f"{who}: has `fix` but no `code` — show what is being fixed")
        poc = f.get("poc")
        if poc and not (poc.get("command") or poc.get("output")):
            errs.append(f"{who}: `poc` needs at least a `command` or its `output`")
        if sev in ("Critical", "High") and not poc:
            if f.get("poc_waiver"):
                warns.append(f"{who}: {sev} with no PoC — waiver accepted, "
                             f"state it in the report")
            else:
                errs.append(
                    f"{who}: {sev} findings need a runnable `poc` "
                    f"(file/command/output) or a `poc_waiver` saying why one is "
                    f"impossible. A finding you cannot reproduce is an opinion.")
    return errs, warns


SEV_PREFIX = {"Critical": "C", "High": "H", "Medium": "M",
              "Low": "L", "Informational": "I"}


def main(argv):
    check_only = "--validate" in argv
    argv = [a for a in argv if a != "--validate"]
    if len(argv) != (2 if check_only else 3):
        sys.exit(__doc__)
    with open(argv[1], encoding="utf-8") as fh:
        data = json.load(fh)

    errs, warns = validate(data)
    for w in warns:
        print(f"  warn: {w}", file=sys.stderr)
    for e in errs:
        print(f"  ERROR: {e}", file=sys.stderr)
    if errs:
        sys.exit(f"{len(errs)} error(s) — not generating")
    if check_only:
        print(f"ok: {len(data.get('findings', []))} findings, "
              f"{len(warns)} warning(s)")
        return

    with open(argv[2], "w", encoding="utf-8") as fh:
        fh.write(build(data))
    print(f"wrote {argv[2]} ({len(data.get('findings', []))} findings, "
          f"{len(warns)} warning(s))")


def _selftest():
    doc = build({
        "project": "T", "findings": [
            {"id": "C-01", "severity": "Critical", "title": "a <b> & `c`",
             "description": "one\n\n- x\n- y", "impact": "**bad**",
             "recommendation": "fix", "code": "-a<b\n ok", "fix": "+safe()",
             "references": ["http://x"]},
            {"id": "L-01", "severity": "Low", "title": "z"},
        ]})
    assert "a &lt;b&gt; &amp; <code>c</code>" in doc  # user input escaped, `code` kept
    assert '<div class="blk bad"><b>Vulnerable code</b>' in doc
    assert '<span class="ln d">a&lt;b</span>' in doc      # '-' line -> red
    assert '<span class="ln">ok</span>' in doc            # ' ' line -> plain
    assert '<div class="blk good"><b>Recommended fix</b>' in doc
    assert '<span class="ln a">safe()</span>' in doc      # '+' line -> green
    assert "<strong>bad</strong>" in doc
    assert "<ul><li>x</li><li>y</li></ul>" in doc
    assert doc.index("C-01") < doc.index("L-01")  # severity ordering
    assert '<b>1</b><span>Critical</span>' in doc and '<b>0</b><span>High</span>' in doc
    assert doc.index('<div class="wrap">') > doc.index("<body>")  # wrap not stranded in <head>
    assert doc.count("<style>") == 1
    # PoC gate: a High with neither poc nor waiver is an error, a waiver is a warning
    e, _ = validate({"findings": [{"id": "H-9", "title": "t", "severity": "High"}]})
    assert any("poc" in x for x in e), e
    e2, w2 = validate({"findings": [{"id": "H-9", "title": "t", "severity": "High",
                                     "poc_waiver": "needs the owner key"}]})
    assert not e2 and any("waiver" in x for x in w2), (e2, w2)
    e3, _ = validate({"findings": [{"id": "H-9", "title": "t", "severity": "High",
                                    "poc": {"command": "forge test"}}]})
    assert not e3, e3
    pd = poc_block({"file": "test/P.t.sol", "command": "forge test --mt x",
                    "output": "line1\nline2"})
    assert "forge test --mt x" in pd and pd.count("class=\"ln\"") == 2, pd

    doc2 = build({"project": "p", "findings": [],
                  "sections": [{"title": "Stranded <x>", "body": "**b**",
                                "table": {"headers": ["A", "B"],
                                          "rows": [["1", "2"]], "highlight": 1}}],
                  "roadmap": [{"tier": "0", "scope": "levers", "fixes": "burn it",
                               "closes": ["C-01"], "outcome": "safe"},
                              {"tier": "1", "scope": "gov"}]})
    assert "Stranded &lt;x&gt;" in doc2
    assert '<th class=hi>B</th>' in doc2 and '<td class=hi>2</td>' in doc2
    assert doc2.count('<div class="tier') == 2
    assert '<div class="tier gate">' in doc2 and doc2.count("hard gate") == 1
    assert '<a href="#C-01">C-01</a>' in doc2
    e, w = validate({"findings": [
        {"id": "C-01", "title": "t", "severity": "Nope"},
        {"id": "C-01", "title": "t", "severity": "Critical"},
        {"id": "X-01", "title": "t", "severity": "Low", "status": "Unverified"},
    ]})
    assert any("not one of" in x for x in e), e
    assert any("duplicate id" in x for x in e), e
    assert any("Unverified" in x for x in w), w
    assert any("should start with L-" in x for x in w), w
    assert not validate({"project": "p", "summary": "s", "trust_assumptions": ["a"],
                         "findings": [{"id": "H-01", "title": "t", "severity": "High",
                                       "location": "A.sol:1", "description": "d",
                                       "impact": "i", "recommendation": "r"}]})[1]
    print("selftest ok")


if __name__ == "__main__":
    _selftest() if sys.argv[1:2] == ["--selftest"] else main(sys.argv)
