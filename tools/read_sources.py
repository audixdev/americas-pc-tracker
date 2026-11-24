#!/usr/bin/env python3
"""Download the first-hand sources behind every entry, for re-reading each check.

For every repo in projects and also_watched (data/tracker.json) it writes one
file to .sources/<owner>_<name>.md holding:
  - the entry as the page shows it now (to compare claim by claim),
  - the current README, raw,
  - every status doc listed in the entry,
  - recent commits on the default branch with their FULL messages
    (since the last check in data/last-seen.json, minus a day, at least 10).

It also searches GitHub for GTA VI port projects created in the last 14 days
that the tracker does not list yet, and writes them to .sources/_new.md.

    python3 tools/read_sources.py                 # everything
    python3 tools/read_sources.py --only owner/name [--only ...]
    python3 tools/read_sources.py --no-discover   # skip the GitHub search

.sources/ is gitignored and never committed. Standard library only; needs `gh`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sources import GhError, gh  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "data" / "tracker.json"
LAST_SEEN = ROOT / "data" / "last-seen.json"
OUT = ROOT / ".sources"

SEARCHES = [
    '"gta vi" in:name,description,readme',
    '"gta 6" in:name,description,readme',
    'gta6 in:name,description',
    '"grand theft auto vi" in:name,description,readme',
    '"7952987A"',
    '"xbox series" emulator in:name,description',
    'scarlett xbox in:name,description',
]


def raw(path: str) -> str:
    proc = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github.raw", path],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return f"(could not fetch: {(proc.stderr or proc.stdout).strip()[:300]})"
    return proc.stdout


def since_iso() -> str:
    try:
        seen = json.loads(LAST_SEEN.read_text())["checked_at"]
        t = datetime.fromisoformat(seen.replace("Z", "+00:00")) - timedelta(days=1)
    except Exception:
        t = datetime.now(timezone.utc) - timedelta(days=2)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(entry: dict, group: str, since: str) -> tuple[str, str]:
    repo = entry["repo"]
    parts = [f"# {entry.get('name', repo)} ({repo}) [{group}]", ""]
    parts += ["## Entry on the page now", "```json", json.dumps(entry, indent=1, ensure_ascii=False), "```", ""]
    try:
        meta = gh(f"repos/{repo}")
        branch = meta.get("default_branch", "main")
        parts.append(f"Repo: pushed_at {meta.get('pushed_at')}, archived {meta.get('archived')}, "
                     f"stars {meta.get('stargazers_count')}, fork of "
                     f"{(meta.get('parent') or {}).get('full_name')}")
    except GhError as e:
        parts.append(f"REPO PROBLEM ({e.status}): {e}")
        return repo, "\n".join(parts)

    parts += ["", "## README (raw)", "", raw(f"repos/{repo}/readme"), ""]
    for doc in entry.get("status_docs") or []:
        parts += [f"## Status doc {doc}", "", raw(f"repos/{repo}/contents/{doc}?ref={branch}"), ""]

    commits = []
    try:
        commits = gh(f"repos/{repo}/commits?sha={branch}&since={since}&per_page=40") or []
        if len(commits) < 10:
            commits = gh(f"repos/{repo}/commits?sha={branch}&per_page=10") or []
    except GhError as e:
        parts.append(f"(commits: {e.status})")
    parts += [f"## Commits on {branch} (newest first, full messages)", ""]
    for c in commits:
        msg = c["commit"]["message"].strip()
        parts += [f"### {c['sha'][:7]} {c['commit']['committer']['date']}", "", msg, ""]
    return repo, "\n".join(parts)


def discover(tracked: set[str]) -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    found: dict[str, dict] = {}
    for q in SEARCHES:
        query = f"{q} created:>={cutoff}"
        try:
            res = gh(f"search/repositories?q={_enc(query)}&sort=stars&order=desc&per_page=30") or {}
        except GhError as e:
            found[f"_error_{q}"] = {"full_name": f"(search failed: {e.status})", "description": q}
            continue
        for r in res.get("items", []):
            name = r["full_name"]
            if name.lower() in tracked or r.get("fork"):
                continue
            found.setdefault(name, r)
    rows = sorted(found.values(), key=lambda r: -(r.get("stargazers_count") or 0))
    lines = ["# Untracked candidates from GitHub search", "",
             f"Created since {cutoff}, forks excluded, most stars first. Leads only: read a",
             "candidate's README and commits before adding it, and skip forks of tracked",
             "projects, mirrors, download/leak repos, fakes and empty repos.", ""]
    for r in rows:
        lines.append(f"- {r.get('full_name')} | stars {r.get('stargazers_count')} | created "
                     f"{r.get('created_at')} | pushed {r.get('pushed_at')} | {r.get('description') or ''}")
    return "\n".join(lines) + "\n"


def _enc(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", default=[], help="owner/name to fetch (repeatable)")
    ap.add_argument("--no-discover", action="store_true", help="skip the GitHub search for new projects")
    args = ap.parse_args()

    data = json.loads(TRACKER.read_text())
    jobs, tracked = [], set()
    for group in ("projects", "also_watched", "checked_idle"):
        for item in data.get(group, []):
            if item.get("repo"):
                tracked.add(item["repo"].lower())
            if group == "checked_idle" or not item.get("repo"):
                continue
            if args.only and item["repo"].lower() not in {o.lower() for o in args.only}:
                continue
            jobs.append((item, group))

    OUT.mkdir(exist_ok=True)
    since = since_iso()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda j: fetch(j[0], j[1], since), jobs))
    for repo, text in results:
        path = OUT / (repo.replace("/", "_") + ".md")
        path.write_text(text)
        print(f"{path.relative_to(ROOT)}  ({len(text):,} chars)")

    if not args.no_discover and not args.only:
        path = OUT / "_new.md"
        path.write_text(discover(tracked))
        print(f"{path.relative_to(ROOT)}")
    print(f"\nCommits since {since}. Entries without a repo (press-only) are not covered: check them by search.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
