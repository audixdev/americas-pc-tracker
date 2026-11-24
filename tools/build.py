#!/usr/bin/env python3
"""Validate data/tracker.json and render index.html from templates/page.html.

    python3 tools/build.py           # validate + write index.html
    python3 tools/build.py --check   # validate + fail if index.html is out of date

Standard library only. Same input always gives byte-identical output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "tracker.json"
LAST_SEEN = ROOT / "data" / "last-seen.json"
TEMPLATE = ROOT / "templates" / "page.html"
OUT = ROOT / "index.html"
ASSETS = [ROOT / "assets" / "site.css", ROOT / "assets" / "site.js"]

RECENT_UPDATES = 5
STATES = {"active", "halted", "gone", "unverified"}
STATE_LABEL = {"halted": "Halted", "gone": "Gone", "unverified": "Unconfirmed"}
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
NUM_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
             "eighteen", "nineteen", "twenty"]


# ---------------------------------------------------------------- validation

class Invalid(Exception):
    pass


def parse_time(value, where: str) -> datetime:
    if not isinstance(value, str) or not ISO_RE.match(value):
        raise Invalid(f"{where}: expected UTC time like 2026-11-24T18:20:00Z, got {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def need(obj: dict, key: str, where: str, kind=str):
    if key not in obj:
        raise Invalid(f"{where}: missing '{key}'")
    val = obj[key]
    if kind is str and (not isinstance(val, str) or not val.strip()):
        raise Invalid(f"{where}.{key}: must be a non-empty string")
    if kind is list and not isinstance(val, list):
        raise Invalid(f"{where}.{key}: must be a list")
    if kind is int and (not isinstance(val, int) or isinstance(val, bool)):
        raise Invalid(f"{where}.{key}: must be a whole number")
    return val


def validate(d: dict) -> None:
    site = d.get("site") or {}
    for k in ("name", "short", "url", "repo", "description"):
        need(site, k, "site")
    checked = parse_time(d.get("checked_at"), "checked_at")

    stages = need(d, "stages", "root", list)
    if len(stages) != 7:
        raise Invalid(f"stages: expected 7 stages, found {len(stages)}")
    for i, s in enumerate(stages):
        need(s, "name", f"stages[{i}]")
        need(s, "bar", f"stages[{i}]")

    projects = need(d, "projects", "root", list)
    if not projects:
        raise Invalid("projects: at least one project is required")
    ids = set()
    for i, p in enumerate(projects):
        where = f"projects[{i}] ({p.get('name', '?')})"
        for k in ("id", "name", "tagline", "status", "source", "state"):
            need(p, k, where)
        if p["id"] in ids:
            raise Invalid(f"{where}: duplicate id '{p['id']}'")
        ids.add(p["id"])
        st = need(p, "stage", where, int)
        if not 1 <= st <= 7:
            raise Invalid(f"{where}.stage: must be 1-7, got {st}")
        if p["state"] not in STATES:
            raise Invalid(f"{where}.state: must be one of {sorted(STATES)}, got {p['state']!r}")
        if p.get("repo") is not None and not REPO_RE.match(str(p["repo"])):
            raise Invalid(f"{where}.repo: must be 'owner/name' or null, got {p['repo']!r}")
        if parse_time(p.get("changed_at"), f"{where}.changed_at") > checked:
            raise Invalid(f"{where}.changed_at is later than checked_at")
        if i == 0 and p.get("tied_with_previous"):
            raise Invalid(f"{where}: the first project cannot be tied_with_previous")
        if i > 0 and p["stage"] > projects[i - 1]["stage"]:
            raise Invalid(f"{where}: stage {p['stage']} ranks below a stage {projects[i-1]['stage']} project; "
                          "reorder projects so stages never increase down the list")
        if p.get("tied_with_previous") and p["stage"] != projects[i - 1]["stage"]:
            raise Invalid(f"{where}: tied_with_previous but its stage differs from the project above")

    for group in ("also_watched", "checked_idle"):
        for i, w in enumerate(d.get(group, [])):
            need(w, "name", f"{group}[{i}]")
            if not REPO_RE.match(str(w.get("repo", ""))):
                raise Invalid(f"{group}[{i}].repo: must be 'owner/name'")
            if group == "also_watched":
                need(w, "note", f"{group}[{i}]")

    fc = d.get("forecast")
    if not isinstance(fc, dict):
        raise Invalid("forecast: missing or not an object")
    parse_time(fc.get("target"), "forecast.target")
    if parse_time(fc.get("revised_at"), "forecast.revised_at") > checked:
        raise Invalid("forecast.revised_at is later than checked_at")
    for k in ("definition", "revision_note"):
        need(fc, k, "forecast")
    for k in ("rests_on", "chances", "milestones"):
        need(fc, k, "forecast", list)
    for k in ("chances", "milestones"):
        for i, row in enumerate(fc[k]):
            need(row, "label", f"forecast.{k}[{i}]")
            need(row, "value", f"forecast.{k}[{i}]")

    updates = need(d, "updates", "root", list)
    prev = None
    for i, u in enumerate(updates):
        where = f"updates[{i}]"
        t = parse_time(u.get("at"), f"{where}.at")
        need(u, "title", where)
        pts = need(u, "points", where, list)
        if not pts:
            raise Invalid(f"{where}.points: at least one point is required")
        if t > checked:
            raise Invalid(f"{where}.at is later than checked_at")
        if prev is not None and t > prev:
            raise Invalid(f"{where}: updates must be newest first ({u['at']} comes after a newer entry)")
        prev = t

    for i, m in enumerate(need(d, "method", "root", list)):
        need(m, "label", f"method[{i}]")
        need(m, "text", f"method[{i}]")


# ---------------------------------------------------------------- formatting

def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def day(dt: datetime) -> str:
    return f"{dt.strftime('%a')} {dt.day} {dt.strftime('%b')}"


def long_time(dt: datetime) -> str:
    return f"{hm(dt)} UTC on {day(dt)}"


def part_of_day(dt: datetime) -> str:
    h = dt.hour
    if 5 <= h < 12:
        return "the morning of"
    if 12 <= h < 17:
        return "the afternoon of"
    if 17 <= h < 22:
        return "the evening of"
    return "the night of"


def rel_until(target: datetime, now: datetime) -> str:
    """Same wording as assets/site.js so the first paint matches the live text."""
    hours = (target - now).total_seconds() / 3600
    if hours < 0:
        return "Any time now"
    if hours < 12:
        return "Within hours"
    if hours < 36:
        return "About a day"
    half_days = round(hours / 12) / 2
    whole = int(half_days)
    num = f"{whole}½" if half_days % 1 else f"{whole}"
    return f"About {num} days"


def num_word(n: int) -> str:
    return NUM_WORDS[n] if 0 <= n < len(NUM_WORDS) else str(n)


def e(s) -> str:
    return escape(str(s), quote=True)


def nb(s: str) -> str:
    """Escape, then keep numbers glued to their units."""
    out = e(s)
    return re.sub(r"(\d) (fps|frames|seconds|minutes|days|hours|GB|of)\b", r"\1&nbsp;\2", out)


def repo_link(name: str, repo: str | None, cls: str = "name") -> str:
    if not repo:
        return f'<span class="{cls}">{e(name)}</span>'
    return f'<a class="{cls}" href="https://github.com/{e(repo)}" rel="noopener">{e(name)}</a>'


def indent(lines: list[str], n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in lines)


# ---------------------------------------------------------------- sections

def rank(projects: list[dict]) -> list[str]:
    labels, pos = [], 0
    for i, p in enumerate(projects):
        if not p.get("tied_with_previous"):
            pos = i + 1
        labels.append(str(pos))
    out = []
    for i, lab in enumerate(labels):
        tied = labels.count(lab) > 1
        out.append(f"{lab}=" if tied else lab)
    return out


def meter(stage: int, cls: str = "meter") -> str:
    segs = "".join(f'<span class="{cls}__seg{" is-on" if i < stage else ""}"></span>' for i in range(7))
    return f'<span class="{cls}" aria-hidden="true">{segs}</span>'


def build_html(d: dict, last_seen: dict) -> str:
    checked = ts(d["checked_at"])
    stages = d["stages"]
    projects = d["projects"]
    site = d["site"]
    leader = projects[0]
    top_stage = max(p["stage"] for p in projects)
    positions = rank(projects)
    fc = d["forecast"]
    target = ts(fc["target"])
    playable = [p for p in projects if p["stage"] == 7]

    # --- hero copy
    at_top = [p for p in projects if p["stage"] == top_stage]
    public_top = [p for p in at_top if p.get("repo")]
    if playable:
        answer = "Yes, by one project's own claim."
        lead = f"{e(playable[0]['name'])} says it meets the playable bar. Check its source line before believing it."
    else:
        answer = "No."
        bits = f"{num_word(len(at_top)).capitalize()} project{'s' if len(at_top) != 1 else ''}"
        if len(public_top) != len(at_top):
            bits = (f"{num_word(len(public_top)).capitalize()} public project{'s' if len(public_top) != 1 else ''}"
                    f" and {num_word(len(at_top) - len(public_top))} private build"
                    f"{'s' if len(at_top) - len(public_top) != 1 else ''}")
        verb = "has" if len(at_top) == 1 else "have"
        lead = (f"{bits} {verb} reached stage&nbsp;{top_stage} of&nbsp;7, "
                f"{e(stages[top_stage - 1]['name'].lower())}.")
        if d.get("headline_note"):
            lead += " " + nb(d["headline_note"])
    active = [p for p in projects if p["state"] != "gone"]
    how = (f"{num_word(len(active)).capitalize()} projects are trying to run the Xbox Series build of GTA&nbsp;VI "
           f"on a PC. This page reads their public repositories and reports how far each says it has got.")

    # --- ladder (hero): stage 7 at the top, every project placed on its rung
    slugs: dict[int, str] = {}
    used: set[str] = set()
    for i, p in enumerate(projects):
        base = "p-" + (re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-") or "project")
        slug, k = base, 2
        while slug in used:
            slug, k = f"{base}-{k}", k + 1
        used.add(slug)
        slugs[i] = slug

    def chip(i: int, p: dict) -> str:
        cls = "chip"
        note = ""
        if p["state"] in ("halted", "gone"):
            cls += " is-out"
            note = f'<span class="vh">, {STATE_LABEL[p["state"]].lower()}</span>'
        elif p["state"] == "unverified":
            cls += " is-unverified"
            note = '<span class="vh">, unconfirmed</span>'
        return f'<li><a class="{cls}" href="#{slugs[i]}">{e(p["name"])}{note}</a></li>'

    ladder = []
    for n in range(7, 0, -1):
        who = [chip(i, p) for i, p in enumerate(projects) if p["stage"] == n]
        cls = [f"rung stage-{n}"]
        if any(p["stage"] >= n for p in projects):
            cls.append("is-reached")
        if n == top_stage:
            cls.append("is-front")
        reached = any(p["stage"] >= n for p in projects)
        names = "".join(who) or (
            '<li class="rung__empty">None at this stage</li>' if reached else '<li class="rung__empty">Nobody yet</li>')
        count = f"{len(who)} project{'s' if len(who) != 1 else ''}" if who else "none"
        ladder.append(
            f'<li class="{" ".join(cls)}"><span class="rung__n">{n}</span>'
            f'<span class="rung__name">{e(stages[n - 1]["name"])}<span class="vh">: {count}</span></span>'
            f'<ul class="rung__who">{names}</ul></li>'
        )
    ladder_rows = indent(ladder, 10)

    # --- standings, grouped by stage
    groups = []
    for n in range(7, 0, -1):
        members = [(i, p, pos) for i, (p, pos) in enumerate(zip(projects, positions)) if p["stage"] == n]
        if not members:
            continue
        gap = top_stage - n
        where = "at the front" if gap == 0 else f"{gap} stage{'s' if gap > 1 else ''} behind the front"
        groups += [
            f'<section class="group stage-{n}" aria-labelledby="g{n}">',
            f'  <h3 id="g{n}" class="group__head"><span class="group__n">{n}</span> '
            f'<span class="group__name">{e(stages[n - 1]["name"])}</span> '
            f'<span class="group__count">{num_word(len(members)).capitalize()} '
            f'project{"s" if len(members) != 1 else ""}, {where}</span></h3>',
            '  <ol class="group__list">',
        ]
        for i, p, pos in members:
            tag = (f' <span class="tag tag--{p["state"]}">{STATE_LABEL[p["state"]]}</span>'
                   if p["state"] in STATE_LABEL else "")
            seen = (last_seen.get("repos", {}).get((p.get("repo") or "").lower()) or {}) if p.get("repo") else {}
            head = (seen.get("head") or {}).get("date")
            commit_txt = ""
            if head:
                hd = ts(head)
                commit_txt = f' Last commit <time datetime="{e(head)}">{hm(hd)} UTC, {day(hd)}</time>.'
            elif p.get("repo") is None and p["state"] != "gone":
                commit_txt = " No public code."
            changed = ts(p["changed_at"])
            row_cls = "entry" + (" is-out" if p["state"] in ("halted", "gone") else "")
            groups += [
                f'    <li class="{row_cls}" id="{slugs[i]}">',
                f'      <p class="entry__pos"><span class="vh">Position </span>{e(pos)}</p>',
                f'      <div class="entry__who">',
                f'        <h4>{repo_link(p["name"], p.get("repo"))}{tag}</h4>',
                f'        <p class="entry__tagline">{nb(p["tagline"])}</p>',
                f'      </div>',
                f'      <div class="entry__status">',
                f'        <p>{nb(p["status"])}</p>',
                f'        <p class="entry__src">Source: {e(p["source"])}. Entry changed '
                f'<time datetime="{e(p["changed_at"])}">{hm(changed)} UTC, {day(changed)}</time>.{commit_txt}</p>',
                f'      </div>',
                f'    </li>',
            ]
        groups += ["  </ol>", "</section>"]
    standings_groups = indent(groups, 6)

    watch_rows = indent([
        f'<li><h4>{repo_link(w["name"], w["repo"])}</h4><p>{nb(w["note"])}</p></li>'
        for w in d.get("also_watched", [])
    ], 10)
    idle = d.get("checked_idle", [])
    if idle:
        links = [repo_link(w["name"], w["repo"]) for w in idle]
        joined = links[0] if len(links) == 1 else ", ".join(links[:-1]) + " and " + links[-1]
        idle_line = f"Also checked, with no GTA&nbsp;VI claim published: {joined}."
    else:
        idle_line = ""

    standings_note = (f"Ranked by stage, then by how far each project's own description goes. "
                      f"{len(projects)} projects.")

    # --- forecast
    fc_reasons = indent([f"<li>{nb(r)}</li>" for r in fc["rests_on"]], 10)
    def pips(value: str) -> str:
        m = re.search(r"(under\s+)?(\d+) in 10\b", value)
        if not m:
            return ""
        n = min(int(m.group(2)), 10)
        full = n - 1 if m.group(1) else n
        dots = "".join(
            '<span class="pip is-on"></span>' if k < full
            else '<span class="pip is-part"></span>' if (m.group(1) and k == full)
            else '<span class="pip"></span>'
            for k in range(10)
        )
        return f'<span class="pips" aria-hidden="true">{dots}</span>'

    fc_chances = indent([
        f'<div><dt>{e(c["label"])}</dt><dd><span class="odds__v">{e(c["value"])}</span>{pips(c["value"])}</dd></div>'
        for c in fc["chances"]
    ], 10)
    fc_miles = indent([
        f'<li class="{"is-done" if m["value"].lower().startswith("reached") else "is-next"}">'
        f'<span class="miles__label">{e(m["label"])}</span> <span class="miles__when">{e(m["value"])}</span></li>'
        for m in fc["milestones"]
    ], 10)
    revised = ts(fc["revised_at"])

    # --- updates
    def update_li(u: dict) -> list[str]:
        t = ts(u["at"])
        pts = "".join(f"<li>{nb(x)}</li>" for x in u["points"])
        return [
            '<li class="feed__item">',
            f'  <p class="feed__when"><time datetime="{e(u["at"])}"><span class="feed__hm">{hm(t)}</span> {day(t)}</time></p>',
            f'  <div class="feed__body"><h3>{nb(u["title"])}</h3><ul>{pts}</ul></div>',
            '</li>',
        ]

    ups = d["updates"]
    recent = [line for u in ups[:RECENT_UPDATES] for line in update_li(u)]
    older_list = ups[RECENT_UPDATES:]
    if older_list:
        older = ["<details class=\"feed__more\">",
                 f"  <summary>Show {len(older_list)} earlier update{'s' if len(older_list) != 1 else ''}</summary>",
                 '  <ol class="feed">']
        older += ["    " + line for u in older_list for line in update_li(u)]
        older += ["  </ol>", "</details>"]
        updates_older = indent(older, 6)
    else:
        updates_older = ""

    method_rows = indent([f'<div><dt>{e(m["label"])}</dt><dd>{nb(m["text"])}</dd></div>' for m in d["method"]], 8)
    stage_defs = indent([
        f'<li class="stage-{i}"><span class="stages__n">{i}</span><span class="stages__name">{e(s["name"])}</span>'
        f'<span class="stages__bar">{nb(s["bar"])}</span></li>'
        for i, s in enumerate(stages, 1)
    ], 8)

    asset_version = hashlib.sha1(b"".join(a.read_bytes() for a in ASSETS if a.exists())).hexdigest()[:10]
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": site["name"],
        "description": site["description"],
        "url": site["url"],
        "dateModified": d["checked_at"],
    }, separators=(",", ":")).replace("</", "<\\/")

    title = f"{site['name']}: is GTA VI playable on PC yet?"
    values = {
        "title": e(title),
        "description": e(site["description"]),
        "site_url": e(site["url"]),
        "site_name": e(site["name"]),
        "site_short": e(site["short"]),
        "site_repo": e(site["repo"]),
        "asset_version": asset_version,
        "jsonld": jsonld,
        "checked_iso": e(d["checked_at"]),
        "checked_short": hm(checked),
        "checked_long": long_time(checked),
        "answer": e(answer),
        "lead": lead,
        "how": how,
        "answer_cls": "hero__answer" + (" is-long" if len(answer) > 4 else ""),
        "ladder_rows": ladder_rows,
        "standings_note": e(standings_note),
        "standings_groups": standings_groups,
        "watch_rows": watch_rows,
        "idle_line": idle_line,
        "fc_target_iso": e(fc["target"]),
        "fc_rel": e(rel_until(target, checked)),
        "fc_rel_lower": e(rel_until(target, checked)[:1].lower() + rel_until(target, checked)[1:]),
        "fc_date": f"{part_of_day(target)} {day(target)}",
        "fc_definition": nb(fc["definition"]),
        "fc_reasons": fc_reasons,
        "fc_chances": fc_chances,
        "fc_milestones": fc_miles,
        "fc_revised_iso": e(fc["revised_at"]),
        "fc_revised": long_time(revised),
        "fc_revision_note": nb(fc["revision_note"]),
        "updates_recent": indent(recent, 8),
        "updates_older": updates_older,
        "method_rows": method_rows,
        "stage_defs": stage_defs,
    }
    html = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(values)
    return re.sub(r"[ \t]+\n", "\n", html)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if index.html is not up to date")
    args = ap.parse_args()
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"data/tracker.json is not valid JSON: {exc}", file=sys.stderr)
        return 1
    try:
        validate(data)
    except Invalid as exc:
        print(f"data/tracker.json: {exc}", file=sys.stderr)
        return 1
    last_seen = json.loads(LAST_SEEN.read_text(encoding="utf-8")) if LAST_SEEN.exists() else {}
    html = build_html(data, last_seen)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != html:
            print("index.html is out of date: run python3 tools/build.py", file=sys.stderr)
            return 1
        print("OK: data valid, index.html up to date")
        return 0
    OUT.write_text(html, encoding="utf-8")
    print(f"Built index.html ({len(html):,} bytes) from {len(data['projects'])} projects, "
          f"{len(data['updates'])} updates; checked_at {data['checked_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
