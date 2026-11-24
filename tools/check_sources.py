#!/usr/bin/env python3
"""Fetch fresh signals for every tracked GitHub repo and report what changed.

Reads the repo list from data/tracker.json (projects, also_watched, checked_idle)
and compares against data/last-seen.json from the previous check.

    python3 tools/check_sources.py            # report only
    python3 tools/check_sources.py --save     # report, then store the new snapshot
    python3 tools/check_sources.py --json     # machine-readable report on stdout
    python3 tools/check_sources.py --only owner/name [--only ...]

Needs the GitHub CLI (`gh`) logged in. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "data" / "tracker.json"
LAST_SEEN = ROOT / "data" / "last-seen.json"


class GhError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def gh(path: str):
    """GET a GitHub API path through `gh api`; return parsed JSON."""
    proc = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        if "HTTP 404" in err or "Not Found" in err:
            raise GhError("gone", err)
        if "HTTP 451" in err or "access blocked" in err.lower():
            raise GhError("blocked", err)
        if "HTTP 409" in err:  # empty repository
            raise GhError("empty", err)
        raise GhError("error", err)
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def repos_from_tracker(data: dict) -> list[dict]:
    out, seen = [], set()
    for group in ("projects", "also_watched", "checked_idle"):
        for item in data.get(group, []):
            repo = item.get("repo")
            if not repo or repo.lower() in seen:
                continue
            seen.add(repo.lower())
            out.append({
                "repo": repo,
                "name": item.get("name", repo),
                "group": group,
                "status_docs": item.get("status_docs", []),
            })
    return out


def snapshot_repo(entry: dict, since: str | None) -> dict:
    repo = entry["repo"]
    snap: dict = {"repo": repo, "name": entry["name"], "group": entry["group"]}
    try:
        meta = gh(f"repos/{repo}")
    except GhError as e:
        snap["state"] = e.status
        snap["error"] = str(e).splitlines()[-1][:200]
        return snap
    snap.update({
        "state": "archived" if meta.get("archived") else "ok",
        "pushed_at": meta.get("pushed_at"),
        "default_branch": meta.get("default_branch"),
        "description": meta.get("description"),
        "stars": meta.get("stargazers_count"),
        "renamed_to": meta.get("full_name") if meta.get("full_name", "").lower() != repo.lower() else None,
    })
    branch = meta.get("default_branch") or "main"
    try:
        commits = gh(f"repos/{repo}/commits?sha={branch}&per_page=1") or []
        if commits:
            c = commits[0]
            snap["head"] = {
                "sha": c["sha"],
                "date": c["commit"]["committer"]["date"],
                "message": c["commit"]["message"].splitlines()[0][:160],
            }
    except GhError as e:
        snap["head_error"] = e.status
    if since:
        try:
            recent = gh(f"repos/{repo}/commits?sha={branch}&since={since}&per_page=30") or []
            snap["new_commits"] = [
                {"sha": c["sha"][:7], "date": c["commit"]["committer"]["date"],
                 "message": c["commit"]["message"].splitlines()[0][:160]}
                for c in recent
            ]
        except GhError:
            pass
    try:
        readme = gh(f"repos/{repo}/readme")
        snap["readme"] = {"path": readme.get("path"), "sha": readme.get("sha")}
    except GhError:
        snap["readme"] = None
    docs = {}
    for doc in entry.get("status_docs") or []:
        try:
            d = gh(f"repos/{repo}/contents/{doc}?ref={branch}")
            docs[doc] = d.get("sha") if isinstance(d, dict) else None
        except GhError:
            docs[doc] = None
    if docs:
        snap["status_docs"] = docs
    try:
        pulls = gh(f"repos/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=15") or []
        snap["pulls"] = [
            {"number": p["number"], "title": p["title"][:160], "state": p["state"],
             "merged": bool(p.get("merged_at")), "updated_at": p["updated_at"]}
            for p in pulls
        ]
    except GhError:
        snap["pulls"] = []
    try:
        rels = gh(f"repos/{repo}/releases?per_page=3") or []
        snap["releases"] = [{"tag": r["tag_name"], "published_at": r.get("published_at")} for r in rels]
    except GhError:
        snap["releases"] = []
    return snap


def diff(old: dict | None, new: dict, since: str | None) -> list[str]:
    """Human-readable list of what changed for one repo."""
    if old is None:
        return ["new to the watch list"]
    notes = []
    if old.get("state") != new.get("state"):
        notes.append(f"state {old.get('state')} -> {new.get('state')}")
    if new.get("renamed_to"):
        notes.append(f"now lives at {new['renamed_to']}")
    oh, nh = (old.get("head") or {}), (new.get("head") or {})
    if nh.get("sha") and oh.get("sha") != nh.get("sha"):
        n = len(new.get("new_commits") or [])
        notes.append(f"default branch moved ({n} commit(s) since last check); head: {nh.get('message')}")
    if (old.get("readme") or {}).get("sha") != (new.get("readme") or {}).get("sha"):
        notes.append("README changed")
    for doc, sha in (new.get("status_docs") or {}).items():
        if (old.get("status_docs") or {}).get(doc) != sha:
            notes.append(f"{doc} changed")
    if since:
        fresh = [p for p in new.get("pulls") or [] if p["updated_at"] > since]
        for p in fresh[:8]:
            tag = "merged" if p["merged"] else p["state"]
            notes.append(f"PR #{p['number']} ({tag}) updated: {p['title']}")
        if len(fresh) > 8:
            notes.append(f"... and {len(fresh) - 8} more PRs updated")
    old_tags = {r["tag"] for r in old.get("releases") or []}
    for r in new.get("releases") or []:
        if r["tag"] not in old_tags:
            notes.append(f"new release {r['tag']}")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", action="store_true", help="write the new snapshot to data/last-seen.json")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--only", action="append", default=[], help="limit to owner/name (repeatable)")
    args = ap.parse_args()

    data = json.loads(TRACKER.read_text(encoding="utf-8"))
    entries = repos_from_tracker(data)
    if args.only:
        wanted = {o.lower() for o in args.only}
        entries = [e for e in entries if e["repo"].lower() in wanted]

    prev = json.loads(LAST_SEEN.read_text(encoding="utf-8")) if LAST_SEEN.exists() else {"repos": {}}
    since = prev.get("checked_at")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    with ThreadPoolExecutor(max_workers=8) as pool:
        snaps = list(pool.map(lambda e: snapshot_repo(e, since), entries))

    report = {"checked_at": now, "previous_check": since, "changed": [], "unchanged": [], "problems": []}
    for s in snaps:
        old = prev["repos"].get(s["repo"].lower())
        notes = diff(old, s, since)
        row = {"repo": s["repo"], "name": s["name"], "group": s["group"], "state": s.get("state"),
               "url": f"https://github.com/{s['repo']}", "notes": notes,
               "head": s.get("head"), "pushed_at": s.get("pushed_at")}
        if s.get("state") in ("gone", "blocked", "error", "empty"):
            report["problems"].append(row)
        if notes:
            report["changed"].append(row)
        else:
            report["unchanged"].append(row)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Checked {len(snaps)} repos at {now} (previous check: {since or 'none'})\n")
        print(f"CHANGED ({len(report['changed'])})")
        for r in report["changed"]:
            print(f"  * {r['name']} [{r['group']}, {r['state']}]  {r['url']}")
            for n in r["notes"]:
                print(f"      - {n}")
        if report["problems"]:
            print(f"\nPROBLEMS ({len(report['problems'])})")
            for r in report["problems"]:
                print(f"  ! {r['name']}: {r['state']}  {r['url']}")
        print(f"\nUNCHANGED ({len(report['unchanged'])}): " + ", ".join(r["name"] for r in report["unchanged"]))

    if args.save:
        merged = dict(prev.get("repos", {}))
        for s in snaps:
            s.pop("new_commits", None)
            merged[s["repo"].lower()] = s
        LAST_SEEN.write_text(json.dumps({"checked_at": now, "repos": merged}, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        if not args.json:
            print(f"\nSaved snapshot to {LAST_SEEN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
