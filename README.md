# GTA VI PC Tracker

An unofficial status page that follows the open-source projects trying to run the Xbox Series build of GTA VI on a PC.

**Live page:** https://audixdev.github.io/americas-pc-tracker/

- **Status only.** Nothing here is playable. The repository holds no game files, downloads or instructions, and links to none.
- Each project's stage is its own claim, taken from its public repository unless the page says otherwise.
- The page is written and updated by an AI assistant (Claude) on request. It can be wrong; every entry names its source.
- It is not affiliated with Rockstar Games, Take-Two Interactive, Microsoft or any project listed.

## How it works

| Path | What it is |
|---|---|
| `data/tracker.json` | All content: projects, stages, forecast, updates log |
| `tools/build.py` | Validates the data and renders `index.html` (Python 3, standard library only) |
| `tools/check_sources.py` | Asks GitHub (via the `gh` CLI) what changed in each tracked repo since the last check |
| `templates/page.html`, `assets/` | Page template, styles and a small script |

```bash
python3 tools/check_sources.py   # what changed
python3 tools/build.py           # rebuild index.html
```

GitHub Pages serves `index.html` from the root of `main`. CI checks that `index.html` matches the data.

## Credits

Typefaces: [Big Shoulders Display](https://fonts.google.com/specimen/Big+Shoulders+Display) and [Barlow](https://fonts.google.com/specimen/Barlow), both under the SIL Open Font License and served by Google Fonts.
