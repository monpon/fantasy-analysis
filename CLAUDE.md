# CCP fantasy league site

Static site for ESPN league 148167114, built by `build.py` and deployed to GitHub Pages by `.github/workflows/deploy.yml` on push to `main`. There are no scheduled builds; the site only changes when the user asks for an update and it gets pushed.

## Weekly update (the user asks on Tuesdays)

1. Fetch fresh data: `rm -rf .cache && python build.py --cache .cache`. Check the output says the week is in `completed weeks`. A week counts once ESPN finalizes it, or unofficially once every NFL game in it has kicked off and ESPN projects no remaining points for any team; the site then labels it "unofficial" until ESPN catches up. The user chose this over waiting for ESPN, since ESPN can take until Tuesday morning. If the week still isn't counted, games are still going, so stop and tell the user.
2. Get the verified numbers: `python build.py --cache .cache --facts N`.
3. Write the recaps by hand in `content/recaps/week-N.md` (format below). Every number and claim must come from the fact sheet or from the built pages. Don't use memory or assumptions about players' teams, byes or injuries. The "Suggested angle" lines are only prompts and can be ignored.
4. Rebuild (`python build.py --cache .cache`), preview (`python -m http.server -d site 8000`), and screenshot or read the recap page to check it renders.
5. Show the user the recaps, and commit and push only when they say so.

## Recap format

Each matchup is its own sports-style article: a headline, an italic subheadline, then a lede and story, ending with a **Next up** line.

```markdown
# Week N: page headline for the whole week

Short intro paragraph about the week as a whole.

## Headline for matchup 1

*One-sentence subheadline.*

@matchup 1 6

Lede paragraph, then the story. **Bold** and *italic* work, as do - bullet lists and [links](../teams/13.html).

**Next up:** Team A face Team B; Team C face Team D.

## Headline for matchup 2
...
```

- The first `# ` line is the page title. Each `## ` heading starts one article; its headline is also listed on the recaps index page.
- `@matchup A B` uses ESPN team ids (1 Fraudulent Failures, 4 GDID, 5 Cleveland Browns, 6 master(rage)baiters, 7 Tennessee Top G's, 8 Barcelona Backshotters, 9 THAT'S MY FAVORITE SAYING, 10 The Washington football team, 11 The Bagel Busters, 13 poverty). It inserts the scoreboard and a starters box score from the data. The build fails if those teams didn't play each other that week.
- Don't invent quotes, and don't cite NFL facts (touchdowns, yards, injuries, trades) that aren't in the data. Stick to fantasy points, projections, lineup decisions and records.
- Before publishing, re-check every "most / highest / only / all" claim against all ten teams in the fact sheet.

## Previews

Each week also gets `content/previews/week-N.md` for the *next* week's matchups, in the same article format as recaps (`@matchup A B` inserts a tale-of-the-tape box: records, PPG, all-play, ESPN projection, position ranks and projected lineups). Get the numbers from `python build.py --cache .cache --preview N`.

- Projections come from lineups as currently set. Always say "as of" the date, and call out starters listed OUT or projected 0 (the sheet flags them). Also compare with the "best possible projected lineup", which excludes OUT/IR players.
- Don't predict winners beyond what ESPN's projection says. Frame it as what to watch.
- Once the week is played, the preview page automatically shows the final score instead of projections. While it's being played, it shows the live score.
- If the week has already started when writing (e.g. Thursday night), `--preview N` still works for the live week. It marks players who already played [PLAYED] and keeps ESPN's pre-game projections. Say so in the intro, and don't report those players' results in a preview.
- Check the NFL bye list for the week (`proGamesByScoringPeriod` has no entry for that team). Projections of 0.0 for healthy players usually mean a bye.
- Team names can change (e.g. THAT'S MY FAVORITE SAYING became Net Worth: 1.4b in Week 4). Generated boxes always use the current name; hand-written text from earlier weeks keeps the old one.

## Team reports

Each team has a hand-written report in `content/teams/<team id>.md`, shown at the top of its team page. Update all ten each week along with the recaps. Get the data from `team_facts()` and the players table (starter vs bench splits), and use the same structure for every team:

```markdown
# Headline

Through Week N

*One-sentence subheadline.*

Opening paragraph: record, PPG rank, all-play rank, how the season has gone.

### What's working
### What isn't
### Outlook
```

"Bench points" means points scored on the bench. "Points left on the bench" means optimal minus actual. Don't mix them up.

## Rules

- Privacy: use team names only, never owners' real names (ESPN's member data includes them).
- Be even-handed across all teams. The user's own team is "The Washington football team" and gets no special treatment.
- Season stats count completed weeks only; don't describe in-progress games as final.
- Distinguish points scored as a starter from points scored on the bench when citing player totals.
