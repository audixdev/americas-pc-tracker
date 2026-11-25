# GTA VI PC Tracker

Static status page that tracks the unofficial projects trying to run the Xbox Series build of GTA VI on a PC.
Live at https://audixdev.github.io/americas-pc-tracker/, published from `main` by GitHub Pages (branch root, no Actions deploy).

## How it fits together

- `data/tracker.json` is the **single source of truth**. Every fact and every sentence on the page lives there.
- `tools/build.py` validates the JSON and renders `templates/page.html` into `index.html`. **Never hand-edit `index.html`**. Edit the JSON or the template, then rebuild.
- `tools/check_sources.py` queries every tracked repo through `gh api` and diffs against `data/last-seen.json` to show what changed since the last check. `--save` stores the new snapshot, which is committed. Always run `--save` **before** `build.py`, because the page shows last-commit times from that snapshot.
- `tools/read_sources.py` downloads, for every project, its current README, status docs and recent commits with full messages into `.sources/` (gitignored), and searches GitHub for untracked GTA VI projects (`.sources/_new.md`). Every update re-reads every entry against these files.
- `assets/site.css` holds the design tokens and layout. `assets/site.js` updates "checked N min ago" and the countdown in the browser, using the same wording as `rel_until()` in build.py.
- Updates are run with the `/update-tracker` skill (`.claude/skills/update-tracker/SKILL.md`). Follow it whenever the user says "update the tracker", "check the status", "what's new", "check the projects" or similar.
- The same skill can run without a PC through the `Update tracker` workflow (`.github/workflows/update-tracker.yml`), started by hand from the GitHub app. Claude runs with a read-only token and writes its report to `tracker-report.md`. A second job validates, then commits and pushes only `data/` and `index.html`. It needs the `CLAUDE_CODE_OAUTH_TOKEN` repo secret, created with `claude setup-token`.

## Commands

```bash
python3 tools/check_sources.py            # what changed since last check
python3 tools/check_sources.py --save     # same, and store the snapshot
python3 tools/read_sources.py            # fetch every README + recent commits, and new-project candidates
python3 tools/build.py                    # validate + render index.html
python3 tools/build.py --check            # validate + confirm index.html is current (CI runs this)
```

Local preview uses `.claude/launch.json` (`tracker`, port 8765).

## Data rules (build.py enforces most of them)

- All times are UTC in the form `2026-11-24T18:20:00Z`. Nothing can be later than `checked_at`.
- `projects` array order **is the ranking**. Stages must never increase down the list. Below stage 6, order within a stage by the furthest point reached in the game's own sequence of screens, furthest first; break near-ties by measured frame rate, then unmodified over modified builds, then public first-hand sources over unconfirmed ones. Set `tied_with_previous: true` (shown as "3=") only when none of these separates two projects.
- **Stage 6 is ordered by its lanes and nothing else** (build.py enforces the order and the ties). Every project at stage 6 or 7 has `lanes` with `picture` (`step` 1–5), `speed` (`fps`) and `stability` (`minutes`), each with a short `note`, or `null` when the source gives no figure (an empty meter). The lane steps are defined in the top-level `lanes` array.
  - Picture: what the source says is on screen in the world (1 dark or unlit, 2 lit where the sun falls, 3 lit in light and shade with visible faults, 4 lit and whole, 5 the console's picture with ray tracing).
  - Speed: the middle of the frame rates it reports in play (the midpoint of the range it gives). Steps from 2, 5, 10, 20 and 30 fps; 20 and up meet the bar.
  - Stability: the longest session it reports without a crash; a session that ended in a crash counts up to the crash, and the note says how it ended. Steps from 10, 30 and 60 minutes; 30 and up meet the bar. Unmeasured or second-hand sessions don't count, but the note can mention them.
  - Order: fewest steps short of the bar on speed and stability together, then picture step, then fps, then minutes. Exact equality is a tie. When a reading is ambiguous, take the lower step.
- Every project has a `furthest` field: one short phrase naming the furthest point it has reached. It is shown above the status and must justify the project's position (below stage 6) or describe it (at stage 6).
- Optional `tested_on`: the OS and graphics card the source tested on, like `Windows 11 · AMD RX 9070 XT`.
- `state` is one of `active`, `halted`, `gone` or `unverified`. Use `unverified` for builds with no public code that are known only from press.
- `changed_at` is when **this page's entry** for the project last changed, not the repo's last push. The page reads the last commit time from `last-seen.json`.
- `updates` are newest first, each with a title and 1–4 points. The first 5 are shown and the rest collapse.
- Add a repo that has a dedicated status file (for example `STATUS.md`) to `status_docs`, so changes to it are detected.

## The seven stages (the bar a claim must meet)

1. **Loads**: the executable loads with its imports resolved.
2. **Starts up**: the game's own start-up code runs (memory, threads, archives).
3. **Graphics device**: the game creates its D3D12 device and queues on the PC.
4. **First frames**: frames are presented to a window, even black ones.
5. **Recognisable picture**: the game's own screens are visible (logos, menus, video, setup pages).
6. **In-game**: the game world is loaded and running, with or without a usable picture.
7. **Playable**: 30+ minutes in the world under player control, at 20+ fps, without a crash.

When a claim is ambiguous, use the lower stage and explain why in the status text. A modified or diagnostic build counts, but say so.

## Editorial rules (non-negotiable)

- **Status only.** No game files, no links to the leak, no download, decryption or "how to run" instructions, and no links to anything that hosts them. Any "playable download" is fake or malware, and the page says so.
- **Facts come only from first-hand sources read in this check.** Every sentence about a project must match its README, status file, commit messages or PR bodies as they are now. Never carry a claim over from an earlier entry without re-checking it, never fill gaps from memory, and never mix a fork's status with its upstream's.
- **Attribute every claim.** The `source` field says where the claim comes from: project README, status file, PR, chat or press. Mark second-hand and unconfirmed claims as such.
- **Own words.** Paraphrase. Never copy text from vuyp/gta6-pc-race or other trackers. Short factual names, numbers and repo links are fine.
- **Plain and neutral.** Short sentences in sentence case. No hype words, no emoji, no "insane" or "huge". Use numbers instead of adjectives.
- **Never invent change.** If nothing meaningful moved, bump `checked_at` only and add no update entry. A forecast move counts as a change.
- **Forecast moves only on evidence.** Review it on every update (chat or workflow): keep `rests_on` current with this check's figures, drop chance rows whose date has passed, and mark milestones reached. Move `target`, the odds or a milestone date only when this check's evidence supports it; a day with no speed gain is evidence too. When it moves, set `revised_at` to `checked_at` and write a `revision_note` saying why. The call is this page's own, never another site's.
- Use the Rockstar/Take-Two names only to state non-affiliation or report their actions. No logos, art or trade dress.

## Git

- The user has given standing approval for tracker updates: commit straight to `main` and push without asking.
- Commit message: `Update tracker: check at <checked_at>`. For non-routine changes (design, tooling), use a normal descriptive message.
- Stage only tracker files (`data/`, `index.html` and whatever else the change touched). Never commit secrets.
