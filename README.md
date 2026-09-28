# CCP fantasy league site

A static website with standings, power rankings, luck, playoff odds and team pages for an ESPN fantasy football league. It's built from ESPN's public API and hosted on GitHub Pages.

## Run locally

Requires Python 3.12+ and nothing else (standard library only).

```sh
python build.py --cache .cache   # --cache saves API responses; delete .cache/ to refetch
python -m http.server -d site 8000
```

Then open http://localhost:8000.

## Deploy

The workflow in `.github/workflows/deploy.yml` rebuilds and publishes the site whenever something is pushed to `main`. There are no scheduled builds. To enable it, go to **Settings → Pages** and set **Source** to **GitHub Actions**.

## Weekly recaps

Recaps are written by hand in `content/recaps/week-N.md` (see `CLAUDE.md` for the format). `python build.py --facts N` prints verified numbers for a completed week to write from.

To point it at a different league or season, change `LEAGUE_ID` in the workflow, or pass `--league` / `--season` to `build.py`. The league must be public.

## Accuracy rules

- Season stats only count weeks where ESPN has declared every matchup final. The in-progress week appears only in the "live" section.
- Every build recomputes each team's weekly score from its starting lineup and **fails** if it doesn't match ESPN's official total.
- Player points are split into points scored as a starter and on the bench.
- Only team names are published; owner names are never written to the site.

## Layout

- `build.py`: entry point
- `fantasy/espn.py`: API client
- `fantasy/analysis.py`: standings, all-play, luck, efficiency, player splits, playoff simulation
- `fantasy/render.py`: HTML pages, SVG charts and recap pages
- `fantasy/factsheet.py`: per-week matchup facts for writing recaps
- `content/recaps/`: hand-written recaps
