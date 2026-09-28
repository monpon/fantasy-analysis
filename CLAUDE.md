# CCP fantasy league site

Static site for ESPN league 148167114, built by `build.py` and deployed to GitHub Pages by `.github/workflows/deploy.yml` on push to `main`. There are no scheduled builds; the site only changes when the user asks for an update and it gets pushed.

## Weekly update (the user asks on Tuesdays)

1. Fetch fresh data: `rm -rf .cache && python build.py --cache .cache`. Check the output says the week is in `completed weeks`. If it isn't final yet (e.g. Monday night game not done), stop and tell the user.
2. Get the verified numbers: `python build.py --cache .cache --facts N`.
3. Write the recaps by hand in `content/recaps/week-N.md` (format below). Every number and claim must come from the fact sheet or from the built pages. Don't use memory or assumptions about players' teams, byes or injuries. The "Suggested angle" lines are only prompts and can be ignored.
4. Rebuild (`python build.py --cache .cache`), preview (`python -m http.server -d site 8000`), and screenshot or read the recap page to check it renders.
5. Show the user the recaps, and commit and push only when they say so.

## Recap format

```markdown
# Week N recaps: optional subtitle

Short intro about the week as a whole.

## Headline for matchup 1

A paragraph or two. **Bold** and *italic* work, as do - bullet lists and [links](../teams/13.html).

## Headline for matchup 2
...
```

The first `# ` line is the page title. Each `## ` heading is one matchup; those headings also appear on the recaps index page.

## Rules

- Privacy: use team names only, never owners' real names (ESPN's member data includes them).
- Be even-handed across all teams. The user's own team is "The Washington football team" and gets no special treatment.
- Season stats count completed weeks only; don't describe in-progress games as final.
- Distinguish points scored as a starter from points scored on the bench when citing player totals.
