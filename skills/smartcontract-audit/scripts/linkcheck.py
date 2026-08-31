#!/usr/bin/env python3
"""Check every http(s) URL in the skill's .md / .json files still resolves.

    python scripts/linkcheck.py .

Reference implementations move and repos get archived — a report that cites a
404 is a report the reader stops trusting. Run this before shipping a report
that quotes reference links, and after editing references/examples.md.

Exit code is the number of dead links (0 = all good), so it works in CI.
A 401/403/429 usually means bot protection, not a dead link — those are
reported separately and do not count as failures. Stdlib only.
"""

import concurrent.futures as cf
import pathlib
import re
import sys
import urllib.request

URL = re.compile(r"""https?://[^\s)\]|>"'\\]+""")
SUFFIXES = (".md", ".json")
SKIP_DIRS = {".git", "Training", "node_modules", "__pycache__"}
# bot protection, not a broken link
SOFT = {401, 403, 405, 429, 503}


def collect(root):
    urls = {}
    for p in root.rglob("*"):
        if p.suffix not in SUFFIXES or SKIP_DIRS & set(p.parts):
            continue
        for u in URL.findall(p.read_text(encoding="utf-8", errors="replace")):
            u = u.rstrip(".,;`*_")   # markdown punctuation, not part of the url
            if len(u) > len("https://"):
                urls.setdefault(u, set()).add(str(p.relative_to(root)))
    return urls


def check(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return url, r.status
    except Exception as e:  # HTTPError carries .code; everything else is a name
        return url, getattr(e, "code", type(e).__name__)


def main(root):
    urls = collect(pathlib.Path(root))
    print(f"checking {len(urls)} urls in {root}\n")
    dead, soft = [], []
    with cf.ThreadPoolExecutor(12) as ex:
        for url, status in sorted(ex.map(check, urls)):
            if status == 200:
                continue
            (soft if status in SOFT else dead).append((status, url))

    for status, url in soft:
        print(f"  {status} (bot protection, probably fine)  {url}")
    for status, url in dead:
        print(f"  DEAD {status}  {url}")
        for where in sorted(urls[url]):
            print(f"        in: {where}")
    print(f"\n{len(dead)} dead, {len(soft)} soft, {len(urls)} total")
    return len(dead)


def _selftest():
    urls = collect(pathlib.Path(__file__).resolve().parents[1])
    assert urls, "found no urls in the skill"
    assert all(u.startswith("http") for u in urls)
    assert check("https://example.com")[1] == 200
    assert URL.findall("see `https://example.com/a.json` now")[0].rstrip("`")         == "https://example.com/a.json"
    print(f"selftest ok ({len(urls)} urls collected, not fetched)")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        _selftest()
    elif not sys.argv[1:]:
        sys.exit(__doc__)
    else:
        sys.exit(main(sys.argv[1]))
