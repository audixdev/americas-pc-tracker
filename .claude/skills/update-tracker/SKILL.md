---
name: update-tracker
description: Check every tracked GTA VI PC port project for news, update data/tracker.json, rebuild index.html, commit and push to main. Use when the user says "update the tracker", "check the status", "what's new", "check the projects", or asks to add, remove, rerank or reword a project or change the forecast.
---

# Update the GTA VI PC Tracker

You are the editor of this page. The user wants it updated end to end, all the way to pushed and live, without being asked anything along the way unless something is genuinely ambiguous. Read `CLAUDE.md` first for the stage bar and the editorial rules. They are binding.

## A. Routine check ("update the tracker")

1. **Sync.** `git pull --ff-only origin main`. If it fails, stop and tell the user why.
2. **Detect and fetch.** `python3 tools/check_sources.py`. Note every CHANGED and PROBLEMS row. Then `python3 tools/read_sources.py`, which writes one file per project to `.sources/` (gitignored): the entry as the page shows it now, the current README, its status docs and the recent commits with full messages. It also writes `.sources/_new.md`, a GitHub search for GTA VI projects the tracker does not list yet.
3. **Re-read every entry against its sources, every run.** Not only the repos that changed: an entry can be out of date because an earlier check missed something. For **every** project in `projects` and `also_watched`, open its `.sources/` file and compare each claim in the entry (`furthest`, `status`, `stage`, `state`, `tagline`, `source`, `tested_on`, the `lanes` of stage-6 projects, every number) with the README and the commit messages. Rewrite whatever no longer matches.
   - **Only write what a source you read in this run says.** Never keep a sentence because it was there before, never fill a gap from memory, and never guess. If you cannot find a claim in the README, a status doc, a commit message or a PR body, remove it.
   - **The README's status section is the baseline.** Commits newer than the README that report a measured result (numbers, "window shown", "draws execute") count too: cite the short sha in `source`, for example "commit 523d947". A plan, a "next" item or a TODO is not a result.
   - **Forks.** A fork's README often keeps the upstream README below its own section. Use only the fork's own section for the fork, and the upstream repo's own README for upstream. Never mix the two.
   - **Drop stale claims** that the source no longer makes, such as "PR not merged" after the merge, or a crash the README now says is fixed.
   - **Date the source.** Put the README's status date, or the commit sha, in `source`.
   - PR bodies: open one (`gh api repos/OWNER/NAME/pulls/N --jq .body`) when a commit or the README points to it for a milestone, such as in-game, lighting, fps, playable or a crash fix.
   - Gone or blocked (404/451): confirm once with `gh api repos/OWNER/NAME`, then set `state` to `gone`. Explain what is known, for example "repository no longer exists". Do not speculate about takedowns unless a source says so.
   - Press-only entries (no repo): check them by search in step 4. If nothing new turns up, leave them as they are and say so in the report.
4. **Scan the wider news**, with 1–2 `WebSearch` calls (standard mode). Example: `GTA 6 PC port news <today's date>`. Look for press reports on private builds, takedowns, new projects and official Rockstar statements. Treat results as leads and prefer first-hand sources. Never link to leak or download sites.
   **Look for new projects** in the same step. Go through `.sources/_new.md` and the search results. For each plausible candidate, read its README and recent commits (`gh api repos/OWNER/NAME/readme -H "Accept: application/vnd.github.raw"`, `gh api "repos/OWNER/NAME/commits?per_page=10"`) before deciding.
   - **Add to `projects`** any runtime, recompilation or emulation effort for GTA VI that makes a first-hand claim of at least stage 1 (from its README, commits or PRs). Rank it like any other entry.
   - **Add to `also_watched`** active efforts with no claim yet that people are following: many stars, or a continuation of a known project.
   - **Skip** asset extractors, archive tools, clippers, companion apps, frame-generation tools, other trackers and lists, plain mirrors without new work, and anything that offers a playable download, asks for game files or looks fake. Never link a releases page.
   - Run `python3 tools/check_sources.py --save` (A.7) after adding a repo, so its baseline is stored.
5. **Decide**, against the stage bar in CLAUDE.md:
   - Stage changed, or the project got further within its stage? Update its `furthest` phrase, then re-sort `projects`: by stage, then by furthest point within the stage (rules in CLAUDE.md). Fix `tied_with_previous`.
   - Stage 6: re-read each project's picture, speed and stability from its sources and set `lanes` (rules in CLAUDE.md). A project entering stage 6 needs `lanes`; one leaving it loses them. Then sort stage 6 by its lanes; `build.py` reports any row that is out of order or a tie that is not marked.
   - Status text out of date? Rewrite it in 1–3 plain sentences in your own words. Set `changed_at` to the new `checked_at`, and set `source`.
   - A new GTA VI project with a real claim goes in `projects`. A new project with no claim yet goes in `also_watched` with a one-line note.
   - **Forecast: review it every run; move it only on evidence.**
     - `rests_on`: keep every reason current with this check's figures and project names, and drop reasons that no longer hold. Keep at least one reason that is this page's own analysis.
     - `chances`: drop rows whose date has passed and add the next one. Change the odds only when this check's evidence supports it.
     - `milestones`: mark what was reached, with the date and "self-reported" where it is.
     - `target`: move it only on evidence from this check: frame rate or session length moving, where the projects say their frame time goes, takedowns. A day that passes with no speed gain is evidence for a later date.
     - When the date, odds or a milestone date moves, set `revised_at` to `checked_at`, write `revision_note` saying why, and say so in the update entry. If it holds, leave `revised_at` and `revision_note` alone and say in the report why it holds.
   - **Other trackers, posts and press are leads, never the basis.** Before using any claim from them (in `rests_on`, a status or the forecast), check it against a first-hand source yourself: the project's README or status file, commit messages and dates (`gh api "repos/OWNER/NAME/commits?..."`), PR bodies, or the primary document (for example GitHub's `github/dmca` repo for takedowns). Recompute their numbers rather than repeating them. Drop what you cannot confirm, or mark it unconfirmed. Make your own forecast call from the evidence, with at least one reason of your own, and don't simply adopt another site's date.
   - Also update `headline_note` if it is no longer true.
6. **Edit `data/tracker.json`.**
   - Always set `checked_at` to now: `date -u +%Y-%m-%dT%H:%M:00Z`.
   - If anything meaningful changed, insert one entry at the **top** of `updates`. Its `at` equals `checked_at`. Give it a headline-style title, such as "Palmwave lights the world", and 1–4 points. Each point is a complete sentence that names the project.
   - If nothing meaningful changed, add no update entry. Bump `checked_at` only. A forecast move counts as a change.
7. **Save the snapshot.** `python3 tools/check_sources.py --save`. This reruns the queries, which takes about 10 seconds, so the next check diffs from now. It must come **before** the build, because the page reads "last commit" times from `data/last-seen.json`.
8. **Build and validate.** Run `python3 tools/build.py`, then `python3 tools/build.py --check`. Fix any validation error in the JSON. Never hand-edit `index.html`.
9. **Commit and push.** The user has given standing approval for this step.
   ```bash
   git add data/ index.html
   git commit -m "Update tracker: check at <checked_at>"
   git push origin main
   ```
10. **Confirm it is live.** Run `gh api repos/audixdev/americas-pc-tracker/pages/builds/latest --jq '.status'`. The status should go to `built` within about a minute. If it is still `building`, it is fine to report it as deploying.
11. **Report** to the user in 3–6 short lines: what moved (or "no changes, check time bumped"), whether the forecast moved and why, or why it holds, and the link https://audixdev.github.io/americas-pc-tracker/.

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
- **The same source rules apply.** Re-read every entry against its README and commits (A.3) and look for new projects (A.4). If the turn budget runs short, finish comparing the ranked projects first, and say in the report which ones you could not re-read.
- **Do everything else**, A.2 to A.8, or B.2 to B.4 when the prompt contains a request from the user. Treat that request like a chat message from the user.
- **Never stop to ask.** If something is ambiguous, take the cautious option: the lower stage, no forecast move, or no change. Still review the forecast (A.5). Explain it in the report.
- **No WebSearch?** If the tool is unavailable or fails, skip A.4 and say so in the report.
- **Report to a file.** Write the A.11 report to `tracker-report.md` in the repo root, in Markdown, 3 to 8 short lines. The workflow shows it on the run's summary page. The report is never committed.
- **Only touch** `data/`, `index.html` and `tracker-report.md`. Any other changed file fails the run.

## Writing checklist (before committing)

- [ ] Every entry was compared with its README and recent commits in this run, and every sentence can be traced to one of them.
- [ ] Nothing stale is left: merged PRs, fixed crashes and old frame rates were updated or removed.
- [ ] `_new.md` and the news search were checked for new projects.
- [ ] Every status names its source (with a date or commit sha), and second-hand claims are marked.
- [ ] No links to leaks, downloads or how-to guides.
- [ ] The text is in my own words, with nothing copied from other trackers.
- [ ] Numbers are specific (fps, seconds, stage), with no hype.
- [ ] The update title says what happened, not how exciting it is.
- [ ] The forecast was reviewed: reasons, chance rows and milestones reflect this check, and any move has a `revision_note` with `revised_at` set.
