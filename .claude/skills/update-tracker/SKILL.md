---
name: update-tracker
description: Check every tracked GTA VI PC port project for news, update data/tracker.json, rebuild index.html, commit and push to main. Use when the user says "update the tracker", "check the status", "what's new", "check the projects", or asks to add, remove, rerank or reword a project or change the forecast.
---

# Update the GTA VI PC Tracker

You are the editor of this page. The user wants it updated end to end, all the way to pushed and live, without being asked anything along the way unless something is genuinely ambiguous. Read `CLAUDE.md` first for the stage bar and the editorial rules. They are binding.

## A. Routine check ("update the tracker")

1. **Sync.** `git pull --ff-only origin main`. If it fails, stop and tell the user why.
2. **Detect.** `python3 tools/check_sources.py`. Note every CHANGED and PROBLEMS row.
3. **Read what changed**, and only that. For each changed repo:
   - README changed: `gh api repos/OWNER/NAME/readme -H "Accept: application/vnd.github.raw"`, then find the status section.
   - status doc changed: `gh api "repos/OWNER/NAME/contents/PATH" -H "Accept: application/vnd.github.raw"`.
   - commits or PRs moved: look at the titles in the report. Open a PR body (`gh api repos/OWNER/NAME/pulls/N --jq .body`) only when its title suggests a new milestone, such as in-game, lighting, fps, playable or a crash fix.
   - gone or blocked (404/451): confirm once with `gh api repos/OWNER/NAME`, then set `state` to `gone`. Explain what is known, for example "repository no longer exists"; do not speculate about takedowns unless a source says so.
4. **Scan the wider news**, with 1–2 `WebSearch` calls (standard mode). Example: `GTA 6 PC port news <today's date>`. Look for press reports on private builds, takedowns, new projects and official Rockstar statements. Treat results as leads and prefer first-hand sources. Never link to leak or download sites.
5. **Decide**, against the stage bar in CLAUDE.md:
   - Stage changed, or the project got further within its stage? Update its `furthest` phrase, then re-sort `projects`: by stage, then by furthest point within the stage (rules in CLAUDE.md). Fix `tied_with_previous`.
   - Status text out of date? Rewrite it in 1–3 plain sentences in your own words. Set `changed_at` to the new `checked_at`, and set `source`.
   - A new GTA VI project with a real claim goes in `projects`. A new project with no claim yet goes in `also_watched` with a one-line note.
   - Forecast: change `target`, `chances` or `milestones` only on real evidence. Then set `revised_at` and write `revision_note` saying what moved it and why.
   - Also update `headline_note` if it is no longer true.
6. **Edit `data/tracker.json`.**
   - Always set `checked_at` to now: `date -u +%Y-%m-%dT%H:%M:00Z`.
   - If anything meaningful changed, insert one entry at the **top** of `updates`. Its `at` equals `checked_at`. Give it a headline-style title, such as "Palmwave lights the world", and 1–4 points. Each point is a complete sentence that names the project.
   - If nothing meaningful changed, add no update entry. Bump `checked_at` only.
7. **Save the snapshot.** `python3 tools/check_sources.py --save`. This reruns the queries, which takes about 10 seconds, so the next check diffs from now. It must come **before** the build, because the page reads "last commit" times from `data/last-seen.json`.
8. **Build and validate.** Run `python3 tools/build.py`, then `python3 tools/build.py --check`. Fix any validation error in the JSON. Never hand-edit `index.html`.
9. **Commit and push.** The user has given standing approval for this step.
   ```bash
   git add data/ index.html
   git commit -m "Update tracker: check at <checked_at>"
   git push origin main
   ```
10. **Confirm it is live.** Run `gh api repos/audixdev/americas-pc-tracker/pages/builds/latest --jq '.status'`. The status should go to `built` within about a minute. If it is still `building`, it is fine to report it as deploying.
11. **Report** to the user in 3–6 short lines: what moved (or "no changes, check time bumped"), any forecast change, and the link https://audixdev.github.io/americas-pc-tracker/.

## B. Direct edit requests

Examples: "add project X", "drop Y", "Y is halted", "move the forecast to Friday", "reword Z", "rename the site".

1. `git pull --ff-only origin main`
2. Edit `data/tracker.json`. To add a project, read its README first and write a real status line; never add a placeholder.
3. If the change is user-visible news, such as a new project or a forecast change, add an `updates` entry. Bump `checked_at` only if you actually checked sources.
4. If a repo was added or renamed, run A.7 first so its baseline is stored. Then run A.8, A.9, A.10 and A.11.

Changes to the design or the template go in `templates/page.html` or `assets/`. Rebuild, preview with the `tracker` launch config (desktop and mobile, light and dark), then commit with a descriptive message.

## C. Running in GitHub Actions

The `Update tracker` workflow (`.github/workflows/update-tracker.yml`) runs this skill on a GitHub runner when the user starts it from their phone. There is no chat, so nobody can answer questions. Where this section differs from A and B, it wins.

- **Skip the git steps.** The checkout is already current, so skip A.1 and B.1. Never commit or push, and skip A.9 and A.10. The workflow's publish job re-runs `build.py --check`, keeps only `data/` and `index.html`, and then commits and pushes.
- **Do everything else**, A.2 to A.8, or B.2 to B.4 when the prompt contains a request from the user. Treat that request like a chat message from the user.
- **Never stop to ask.** If something is ambiguous, take the cautious option: the lower stage, no forecast move, or no change. Explain it in the report.
- **No WebSearch?** If the tool is unavailable or fails, skip A.4 and say so in the report.
- **Report to a file.** Write the A.11 report to `tracker-report.md` in the repo root, in Markdown, 3 to 8 short lines. The workflow shows it on the run's summary page. The report is never committed.
- **Only touch** `data/`, `index.html` and `tracker-report.md`. Any other changed file fails the run.

## Writing checklist (before committing)

- [ ] Every status names its source, and second-hand claims are marked.
- [ ] No links to leaks, downloads or how-to guides.
- [ ] The text is in my own words, with nothing copied from other trackers.
- [ ] Numbers are specific (fps, seconds, stage), with no hype.
- [ ] The update title says what happened, not how exciting it is.
