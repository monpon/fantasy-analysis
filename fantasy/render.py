"""Render analysis results to static HTML pages with inline SVG charts."""

import datetime
import html
import os
import statistics

from .analysis import POSITION_ORDER

esc = html.escape


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def rank_str(rank_tied):
    rank, tied = rank_tied
    return ("T-" if tied else "") + ordinal(rank)


def fmt(x, digits=1):
    return f"{x:,.{digits}f}"


def pct(x, digits=0):
    return "—" if x is None else f"{x * 100:.{digits}f}%"


def record(t):
    r = f"{t['wins']}-{t['losses']}"
    return r + (f"-{t['ties']}" if t["ties"] else "")


def allplay(t):
    r = f"{t['allplay_w']}-{t['allplay_l']}"
    return r + (f"-{t['allplay_t']}" if t["allplay_t"] else "")


def team_link(t, prefix=""):
    return f'<a href="{prefix}teams/{t["id"]}.html">{esc(t["name"])}</a>'


# ---------------------------------------------------------------- charts ----

def _bar_path(x0, x1, y, h, r=4):
    """Horizontal bar: square at the baseline (x0), 4px rounded at the data end (x1)."""
    if abs(x1 - x0) < 0.5:
        return ""
    r = min(r, abs(x1 - x0), h / 2)
    if x1 > x0:
        return (f"M{x0:.1f},{y:.1f}H{x1 - r:.1f}A{r},{r} 0 0 1 {x1:.1f},{y + r:.1f}"
                f"V{y + h - r:.1f}A{r},{r} 0 0 1 {x1 - r:.1f},{y + h:.1f}H{x0:.1f}Z")
    return (f"M{x0:.1f},{y:.1f}H{x1 + r:.1f}A{r},{r} 0 0 0 {x1:.1f},{y + r:.1f}"
            f"V{y + h - r:.1f}A{r},{r} 0 0 0 {x1 + r:.1f},{y + h:.1f}H{x0:.1f}Z")


def _nice_ticks(lo, hi, n=4):
    span = hi - lo or 1
    raw = span / n
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = (lo // step) * step
    ticks = []
    v = start
    while v <= hi + 1e-9:
        ticks.append(round(v, 6))
        v += step
    return ticks


def hbar_chart(rows, title, value_fmt=fmt, diverging=False, label_width=210):
    """rows: list of dicts with label (html), value, tip."""
    band, bar_h = 30, 20
    width, pad_r = 720, 70
    height = band * len(rows) + 30
    vals = [r["value"] for r in rows]
    lo = min(0.0, min(vals))
    hi = max(0.0, max(vals))
    if diverging:
        m = max(abs(lo), abs(hi)) or 1
        lo, hi = -m, m
    ticks = _nice_ticks(lo, hi)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
    plot_w = width - label_width - pad_r

    def xs(v):
        return label_width + (v - lo) / (hi - lo or 1) * plot_w

    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    for tk in ticks:
        x = xs(tk)
        out.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{height - 24}"/>')
        out.append(f'<text class="tick" x="{x:.1f}" y="{height - 8}" text-anchor="middle">{value_fmt(tk)}</text>')
    x0 = xs(0)
    for i, r in enumerate(rows):
        y = i * band + (band - bar_h) / 2
        x1 = xs(r["value"])
        cls = "bar-neg" if diverging and r["value"] < 0 else "bar"
        out.append(f'<g class="hit" data-tip="{esc(r["tip"])}">')
        out.append(f'<rect class="hitbox" x="0" y="{i * band}" width="{width}" height="{band}"/>')
        out.append(f'<text class="label" x="{label_width - 10}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end">{esc(r["label"])}</text>')
        out.append(f'<path class="{cls}" d="{_bar_path(x0, x1, y, bar_h)}"/>')
        tx = x1 + 6 if r["value"] >= 0 else x1 - 6
        anchor = "start" if r["value"] >= 0 else "end"
        out.append(f'<text class="value" x="{tx:.1f}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="{anchor}">{value_fmt(r["value"])}</text>')
        out.append("</g>")
    out.append(f'<line class="axis" x1="{x0:.1f}" x2="{x0:.1f}" y1="0" y2="{height - 24}"/>')
    out.append("</svg>")
    return "".join(out)


def line_chart(series, periods, title):
    """series: list of dicts: name, cls, values (per period)."""
    width, height = 720, 260
    left, right, top, bottom = 48, 110, 16, 32
    all_vals = [v for s in series for v in s["values"]]
    ticks = _nice_ticks(min(all_vals) * 0.9, max(all_vals) * 1.05)
    lo, hi = ticks[0], ticks[-1]
    pw, ph = width - left - right, height - top - bottom

    def xs(i):
        return left + (pw * i / (len(periods) - 1) if len(periods) > 1 else pw / 2)

    def ys(v):
        return top + ph - (v - lo) / (hi - lo or 1) * ph

    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">']
    for tk in ticks:
        out.append(f'<line class="grid" x1="{left}" x2="{width - right}" y1="{ys(tk):.1f}" y2="{ys(tk):.1f}"/>')
        out.append(f'<text class="tick" x="{left - 8}" y="{ys(tk) + 4:.1f}" text-anchor="end">{fmt(tk, 0)}</text>')
    for i, p in enumerate(periods):
        out.append(f'<text class="tick" x="{xs(i):.1f}" y="{height - 10}" text-anchor="middle">Wk {p}</text>')
    for s in series:
        pts = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(s["values"]))
        if len(s["values"]) > 1:
            out.append(f'<polyline class="line {s["cls"]}" points="{pts}"/>')
        last = len(s["values"]) - 1
        out.append(f'<text class="label" x="{xs(last) + 10:.1f}" y="{ys(s["values"][last]) + 4:.1f}">{esc(s["name"])}</text>')
    for s in series:
        for i, v in enumerate(s["values"]):
            out.append(f'<g class="hit" data-tip="{esc(s["name"])} · Week {periods[i]}: {fmt(v)}">'
                       f'<circle class="hitbox" cx="{xs(i):.1f}" cy="{ys(v):.1f}" r="12"/>'
                       f'<circle class="dot {s["cls"]}" cx="{xs(i):.1f}" cy="{ys(v):.1f}" r="4.5"/></g>')
    out.append("</svg>")
    legend = "".join(f'<span class="key"><i class="swatch {s["cls"]}"></i>{esc(s["name"])}</span>' for s in series)
    return f'<div class="legend">{legend}</div>' + "".join(out)


# ----------------------------------------------------------------- pages ----

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --neg: #e34948; --ref: #898781; --good: #006300;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --neg: #e66767; --ref: #898781; --good: #0ca30c;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
header.site { border-bottom: 1px solid var(--border); background: var(--surface); }
header.site .wrap { display: flex; gap: 24px; align-items: baseline; flex-wrap: wrap; }
header.site .brand { font-weight: 650; font-size: 18px; color: var(--ink); text-decoration: none; }
header.site nav a { color: var(--ink-2); text-decoration: none; margin-right: 16px; }
header.site nav a:hover { color: var(--ink); }
.wrap { max-width: 1040px; margin: 0 auto; padding: 16px 20px; }
h1 { font-size: 28px; margin: 16px 0 4px; }
h2 { font-size: 19px; margin: 32px 0 8px; }
h3 { font-size: 16px; margin: 20px 0 6px; }
.sub { color: var(--ink-2); margin: 0 0 16px; }
.note { color: var(--ink-2); font-size: 13px; }
a { color: inherit; text-decoration-color: var(--axis); text-underline-offset: 3px; }
a:hover { text-decoration-color: var(--ink); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin: 12px 0; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.tile .k { color: var(--ink-2); font-size: 13px; }
.tile .v { font-size: 22px; font-weight: 600; margin-top: 2px; }
.tile .d { color: var(--ink-2); font-size: 13px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--grid); text-align: left; white-space: nowrap; }
th { color: var(--ink-2); font-weight: 550; font-size: 13px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
tr.cut td { border-bottom: 2px solid var(--axis); }
.muted { color: var(--muted); }
.badge { display: inline-block; font-size: 12px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--border); color: var(--ink-2); }
.games { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.game .row { display: flex; justify-content: space-between; gap: 12px; padding: 3px 0; }
.game .row.win { font-weight: 600; }
.game .row .s { font-variant-numeric: tabular-nums; }
.game .meta { color: var(--ink-2); font-size: 13px; margin-top: 6px; }
ul.facts { margin: 6px 0; padding-left: 20px; }
ul.facts li { margin: 3px 0; }
.kicker { text-transform: uppercase; letter-spacing: 0.06em; font-size: 12px; font-weight: 600; color: var(--ink-2); margin: 20px 0 0; }
.story { padding: 22px 26px; }
.story h2 { font-size: 24px; line-height: 1.25; margin: 0 0 6px; }
.story .dek { font-size: 17px; color: var(--ink-2); margin: 0 0 14px; }
.story .scoreboard { max-width: 420px; border-top: 1px solid var(--grid); border-bottom: 1px solid var(--grid); padding: 6px 0; margin: 0 0 10px; }
.story-body { font-size: 16px; line-height: 1.65; max-width: 70ch; }
.story-body p { margin: 0 0 14px; }
.story-body h3 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); margin: 18px 0 6px; }
details.box { margin: 0 0 14px; font-size: 13px; }
details.box summary { cursor: pointer; color: var(--ink-2); }
.box-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 8px 24px; margin-top: 8px; }
.box-cols td, .box-cols th { padding: 4px 6px; }
table.tape { max-width: 560px; margin: 0 0 12px; }
table.tape td, table.tape th { padding: 5px 10px; }
table.tape th:first-child { text-align: right; }
svg.chart { width: 100%; height: auto; display: block; font: 13px system-ui, -apple-system, "Segoe UI", sans-serif; }
svg .grid { stroke: var(--grid); stroke-width: 1; }
svg .axis { stroke: var(--axis); stroke-width: 1; }
svg .tick { fill: var(--muted); font-variant-numeric: tabular-nums; }
svg .label { fill: var(--ink); }
svg .value { fill: var(--ink-2); font-variant-numeric: tabular-nums; }
svg .bar { fill: var(--series-1); }
svg .bar-neg { fill: var(--neg); }
svg .line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
svg .line.s1 { stroke: var(--series-1); }
svg .line.ref { stroke: var(--ref); }
svg .dot { stroke: var(--surface); stroke-width: 2; }
svg .dot.s1 { fill: var(--series-1); }
svg .dot.ref { fill: var(--ref); }
svg .hitbox { fill: transparent; }
svg .hit:hover .bar, svg .hit:hover .bar-neg { opacity: 0.85; }
.legend { display: flex; gap: 16px; font-size: 13px; color: var(--ink-2); margin-bottom: 4px; }
.legend .swatch { display: inline-block; width: 14px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.legend .swatch.s1 { background: var(--series-1); }
.legend .swatch.ref { background: var(--ref); }
#tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--border);
  box-shadow: 0 4px 14px rgba(0,0,0,0.12); border-radius: 8px; padding: 6px 9px; font-size: 13px; display: none; z-index: 10; max-width: 320px; }
footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--border); margin-top: 40px; }
"""

TOOLTIP_JS = """
<div id="tip" role="tooltip"></div>
<script>
(function () {
  var tip = document.getElementById('tip');
  document.querySelectorAll('[data-tip]').forEach(function (el) {
    el.addEventListener('mousemove', function (e) {
      tip.textContent = el.getAttribute('data-tip');
      tip.style.display = 'block';
      var x = e.clientX + 14, y = e.clientY + 14;
      if (x + tip.offsetWidth > window.innerWidth - 8) x = e.clientX - tip.offsetWidth - 14;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    });
    el.addEventListener('mouseleave', function () { tip.style.display = 'none'; });
  });
})();
</script>
"""


def page(title, body, data, prefix=""):
    gen = datetime.datetime.fromtimestamp(data["generated"], datetime.timezone.utc)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(data['league_name'])}</title>
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="{prefix}index.html">{esc(data['league_name'])} {data['season']}</a>
  <nav><a href="{prefix}index.html">League</a><a href="{prefix}previews.html">Previews</a><a href="{prefix}recaps.html">Recaps</a><a href="{prefix}weeks.html">Weekly results</a><a href="{prefix}about.html">How it works</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">Data from ESPN's public league API. Updated {gen:%b %d, %Y %H:%M} UTC.
Season stats include completed weeks only.</div></footer>
{TOOLTIP_JS}
</body>
</html>
"""


def through_text(data):
    c = data["completed"]
    if not c:
        return "No completed weeks yet."
    unofficial = (f" (Week {', '.join(map(str, data['unofficial']))} scores unofficial until ESPN finalizes)"
                  if data.get("unofficial") else "")
    return (f"Through Week {c[-1]}{unofficial}"
            + (f" · Week {data['live']['period']} in progress" if data["live"] else ""))


def live_section(data, prefix=""):
    live = data["live"]
    if not live:
        return ""
    teams = data["teams"]
    cards = []
    for g in live["games"]:
        h, a = g["home"], g["away"]
        # Decided only when the trailing team has no starters left to play or mid-game.
        decided_for = None
        if h["score"] > a["score"] and not (a["pending"] or a["in_game"]):
            decided_for = "home"
        elif a["score"] > h["score"] and not (h["pending"] or h["in_game"]):
            decided_for = "away"
        rows = []
        for key, s in (("home", h), ("away", a)):
            t = teams[s["team"]]
            cls = "row win" if decided_for == key else "row"
            rows.append(f'<div class="{cls}"><span>{team_link(t, prefix)}</span><span class="s">{fmt(s["score"])}</span></div>')
        meta = []
        for s in (h, a):
            if s["in_game"]:
                names = ", ".join(f'{p["name"]} ({p["pro"]})' for p in s["in_game"])
                meta.append(f'{esc(teams[s["team"]]["name"])} playing now: {esc(names)}')
            if s["pending"]:
                names = ", ".join(f'{p["name"]} ({p["pro"]}, proj {fmt(p["projection"])})' for p in s["pending"])
                meta.append(f'{esc(teams[s["team"]]["name"])} yet to play: {esc(names)}')
        status = ('<span class="badge">Decided</span>' if decided_for
                  else '<span class="badge">In progress</span>')
        meta_html = "".join(f"<div>{m}</div>" for m in meta) or "<div>All starters have finished.</div>"
        cards.append(f'<div class="card game">{status}{"".join(rows)}<div class="meta">{meta_html}</div></div>')
    return (f"<h2>Week {live['period']} live</h2>"
            f'<p class="note">Live scores. "Yet to play" means that player\'s game hasn\'t kicked off. '
            f"These scores are not included in any season stats until ESPN makes the week final.</p>"
            f'<div class="games">{"".join(cards)}</div>')


def index_page(data):
    teams = data["teams"]
    st = data["standings"]
    body = [f"<h1>{esc(data['league_name'])} league dashboard</h1>",
            f'<p class="sub">{through_text(data)} · {data["size"]} teams · top {data["playoff_teams"]} make the playoffs</p>']

    if data["completed"]:
        top_ppg = max(st, key=lambda t: t["ppg"])
        luckiest = max(st, key=lambda t: t["luck"])
        unluckiest = min(st, key=lambda t: t["luck"])
        best_week = max(((t, w) for t in st for w in t["weekly"]), key=lambda x: x[1]["points"])
        body.append('<div class="tiles">'
                    f'<div class="tile"><div class="k">Top scoring team</div><div class="v">{fmt(top_ppg["ppg"])}</div><div class="d">{team_link(top_ppg)} · points per game</div></div>'
                    f'<div class="tile"><div class="k">Best single week</div><div class="v">{fmt(best_week[1]["points"])}</div><div class="d">{team_link(best_week[0])} · Week {best_week[1]["period"]}</div></div>'
                    f'<div class="tile"><div class="k">Luckiest record</div><div class="v">{luckiest["luck"]:+.1f} wins</div><div class="d">{team_link(luckiest)} vs. all-play</div></div>'
                    f'<div class="tile"><div class="k">Unluckiest record</div><div class="v">{unluckiest["luck"]:+.1f} wins</div><div class="d">{team_link(unluckiest)} vs. all-play</div></div>'
                    "</div>")

    body.append(live_section(data))

    rows = []
    for t in st:
        cut = ' class="cut"' if t["standing"] == data["playoff_teams"] else ""
        rows.append(f"<tr{cut}><td class='n'>{t['standing']}</td><td>{team_link(t)}</td><td class='n'>{record(t)}</td>"
                    f"<td class='n'>{fmt(t['pf'])}</td><td class='n'>{fmt(t['pa'])}</td><td class='n'>{fmt(t['ppg'])}</td>"
                    f"<td class='n'>{allplay(t)}</td><td class='n'>{t['luck']:+.1f}</td><td class='n'>{pct(t['efficiency'], 1)}</td>"
                    f"<td class='n'>{pct(t['playoff_odds'])}</td></tr>")
    body.append("<h2>Standings</h2>"
                '<p class="note">The line marks the playoff cutoff. Luck = actual wins minus the wins expected from the all-play record. '
                'See <a href="about.html">How it works</a> for definitions.</p>'
                '<div class="card table-wrap"><table><thead><tr><th class="n">#</th><th>Team</th><th class="n">Record</th>'
                '<th class="n">PF</th><th class="n">PA</th><th class="n">PPG</th><th class="n">All-play</th><th class="n">Luck</th>'
                '<th class="n">Lineup eff.</th><th class="n">Playoff odds</th></tr></thead><tbody>'
                + "".join(rows) + "</tbody></table></div>")

    if data["completed"]:
        by_ap = sorted(st, key=lambda t: (-t["allplay_pct"], -t["pf"]))
        body.append("<h2>Power rankings</h2>"
                    '<p class="note">Ranked by all-play win percentage: each team\'s record if it played every other team every week.</p>'
                    '<div class="card">' + hbar_chart(
                        [{"label": t["name"], "value": t["allplay_pct"] * 100,
                          "tip": f'{t["name"]}: {allplay(t)} all-play ({pct(t["allplay_pct"], 1)}), {fmt(t["ppg"])} PPG'}
                         for t in by_ap],
                        "All-play win percentage", value_fmt=lambda v: f"{v:.0f}%") + "</div>")

        by_luck = sorted(st, key=lambda t: -t["luck"])
        body.append("<h2>Luck</h2>"
                    '<p class="note">Actual wins minus expected wins. Positive (blue) means the record is better than the scoring suggests; '
                    "negative (red) means worse.</p>"
                    '<div class="card">' + hbar_chart(
                        [{"label": t["name"], "value": t["luck"],
                          "tip": f'{t["name"]}: {record(t)} actual, {fmt(t["expected_wins"])} expected wins'}
                         for t in by_luck],
                        "Luck: actual minus expected wins", value_fmt=lambda v: f"{v:+.1f}", diverging=True) + "</div>")

        by_odds = sorted(st, key=lambda t: -(t["playoff_odds"] or 0))
        body.append("<h2>Playoff odds</h2>"
                    '<p class="note">Rough estimates from 20,000 simulations of the remaining schedule. '
                    "They ignore injuries, trades and waiver moves.</p>"
                    '<div class="card">' + hbar_chart(
                        [{"label": t["name"], "value": (t["playoff_odds"] or 0) * 100,
                          "tip": f'{t["name"]}: {pct(t["playoff_odds"], 1)} playoffs, {pct(t["first_seed_odds"], 1)} #1 seed'}
                         for t in by_odds],
                        "Playoff odds", value_fmt=lambda v: f"{v:.0f}%") + "</div>")

        head = "".join(f"<th class='n'>{p}</th>" for p in POSITION_ORDER)
        prow = []
        for t in sorted(st, key=lambda t: t["name"].lower()):
            cells = "".join(f"<td class='n'>{fmt(t['by_pos'].get(p, 0), 0)} <span class='muted'>({rank_str(t['pos_ranks'][p])})</span></td>"
                            for p in POSITION_ORDER)
            prow.append(f"<tr><td>{team_link(t)}</td>{cells}</tr>")
        body.append("<h2>Points by position</h2>"
                    '<p class="note">Points from starting lineups only, with league rank in parentheses. '
                    "FLEX points count toward the player's own position.</p>"
                    f'<div class="card table-wrap"><table><thead><tr><th>Team</th>{head}</tr></thead><tbody>{"".join(prow)}</tbody></table></div>')

    return page("League", "\n".join(body), data)


def weeks_page(data, recaps):
    teams = data["teams"]
    body = ["<h1>Weekly results</h1>", f'<p class="sub">{through_text(data)}</p>', live_section(data)]
    by_period = {}
    for r in data["results"]:
        by_period.setdefault(r["period"], []).append(r)
    for p in sorted(by_period, reverse=True):
        scores = sorted((s for r in by_period[p] for s in (r["home_score"], r["away_score"])), reverse=True)
        cards = []
        for r in by_period[p]:
            rows = []
            for key, score in (("home", r["home_score"]), ("away", r["away_score"])):
                t = teams[r[key]]
                won = r["winner"] == key.upper()
                rows.append(f'<div class="row{" win" if won else ""}"><span>{team_link(t)}</span><span class="s">{fmt(score)}</span></div>')
            margin = abs(r["home_score"] - r["away_score"])
            cards.append(f'<div class="card game">{"".join(rows)}<div class="meta">Margin {fmt(margin)}</div></div>')
        recap_link = f"<a href='recaps/week-{p}.html'>Read the Week {p} recaps</a> · " if p in recaps else ""
        body.append(f"<h2>Week {p}</h2><p class='note'>{recap_link}High {fmt(scores[0])} · low {fmt(scores[-1])} · "
                    f"median {fmt(statistics.median(scores))}</p>"
                    f'<div class="games">{"".join(cards)}</div>')
    return page("Weekly results", "\n".join(body), data)


def team_facts(t, data):
    """Short, factual observations generated from the numbers."""
    n = data["size"]
    facts = []
    r = t["ranks"]
    facts.append(f"Ranks {rank_str(r['ppg'])} of {n} in points per game ({fmt(t['ppg'])}) and "
                 f"{rank_str(r['allplay'])} in all-play record ({allplay(t)}).")
    if abs(t["luck"]) >= 0.5:
        direction = "more" if t["luck"] > 0 else "fewer"
        facts.append(f"Has {abs(t['luck']):.1f} {direction} wins than its all-play record would predict "
                     f"({record(t)} actual vs. {fmt(t['expected_wins'])} expected).")
    else:
        facts.append(f"Record ({record(t)}) is in line with its all-play results.")
    strong = [p for p in POSITION_ORDER if t["pos_ranks"][p][0] <= 3]
    weak = [p for p in POSITION_ORDER if t["pos_ranks"][p][0] >= n - 2]
    if strong:
        facts.append("Top-3 production at: " + ", ".join(f"{p} ({rank_str(t['pos_ranks'][p])})" for p in strong) + ".")
    if weak:
        facts.append("Bottom-3 production at: " + ", ".join(f"{p} ({rank_str(t['pos_ranks'][p])})" for p in weak) + ".")
    facts.append(f"Lineup efficiency is {pct(t['efficiency'], 1)} ({rank_str(r['efficiency'])}), "
                 f"with {fmt(t['bench'])} points scored on the bench.")
    starters = [p for p in t["players"] if p["starts"] >= 2]
    if starters:
        best = max(starters, key=lambda p: p["per_start"])
        facts.append(f"Best starter per game: {esc(best['name'])}, {fmt(best['per_start'])} per start over {best['starts']} starts.")
    benchers = [p for p in t["players"] if p["bench_pts"] > 0]
    if benchers:
        b = max(benchers, key=lambda p: p["bench_pts"])
        facts.append(f"Most bench points: {esc(b['name'])}, {fmt(b['bench_pts'])} over {b['bench_weeks']} "
                     f"bench week{'s' if b['bench_weeks'] != 1 else ''}"
                     + (f" ({fmt(b['start_pts'])} in {b['starts']} start{'s' if b['starts'] != 1 else ''})" if b["starts"] else "") + ".")
    hurt = [p for p in t["players"] if p["on_roster"] and p["injury"] in ("OUT", "INJURY_RESERVE", "DOUBTFUL", "SUSPENSION")]
    if hurt:
        facts.append("Currently unavailable or on IR: " + ", ".join(f"{esc(p['name'])} ({p['injury'].replace('_', ' ').lower()})" for p in hurt) + ".")
    if t["remaining_sos"] is not None:
        sos = sorted(x["remaining_sos"] for x in data["teams"].values() if x["remaining_sos"] is not None)
        hardness = sos.index(t["remaining_sos"]) + 1
        facts.append(f"Remaining opponents average {fmt(t['remaining_sos'])} PPG "
                     f"({ordinal(n - hardness + 1)} hardest remaining schedule of {n}).")
    return facts


def team_page(t, data, report=None):
    body = [f"<h1>{esc(t['name'])}</h1>",
            f'<p class="sub">{record(t)} · {ordinal(t["standing"])} place · {through_text(data)}</p>']
    body.append('<div class="tiles">'
                f'<div class="tile"><div class="k">Points per game</div><div class="v">{fmt(t["ppg"])}</div><div class="d">{rank_str(t["ranks"]["ppg"])} in league</div></div>'
                f'<div class="tile"><div class="k">All-play record</div><div class="v">{allplay(t)}</div><div class="d">{rank_str(t["ranks"]["allplay"])} in league</div></div>'
                f'<div class="tile"><div class="k">Lineup efficiency</div><div class="v">{pct(t["efficiency"], 1)}</div><div class="d">{rank_str(t["ranks"]["efficiency"])} in league</div></div>'
                f'<div class="tile"><div class="k">Playoff odds</div><div class="v">{pct(t["playoff_odds"])}</div><div class="d">{pct(t["first_seed_odds"])} for the #1 seed</div></div>'
                "</div>")

    live = data["live"]
    if live:
        for g in live["games"]:
            for me, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
                if me["team"] == t["id"]:
                    o = data["teams"][opp["team"]]
                    pend = ", ".join(f'{p["name"]} ({p["pro"]})' for p in me["pending"]) or "none"
                    body.append(f'<div class="card"><strong>Week {live["period"]} (in progress):</strong> '
                                f'{fmt(me["score"])} vs {team_link(o, "../")} {fmt(opp["score"])}. '
                                f'<span class="note">Starters yet to play: {esc(pend)}.</span></div>')

    if report:
        kicker = f'<p class="kicker" style="margin-top:0">{esc(report["kicker"])} · Team report</p>' if report["kicker"] else ""
        dek = f'<p class="dek">{esc(report["dek"])}</p>' if report["dek"] else ""
        body.append(f'<article class="card story">{kicker}<h2>{esc(report["headline"])}</h2>{dek}'
                    f'<div class="story-body">{report["body"]}</div></article>')

    body.append("<h2>Summary</h2><div class='card'><ul class='facts'>"
                + "".join(f"<li>{f}</li>" for f in team_facts(t, data)) + "</ul></div>")

    if t["weekly"]:
        periods = [w["period"] for w in t["weekly"]]
        league_avg = [sum(x["weekly"][i]["points"] for x in data["teams"].values()) / data["size"] for i in range(len(periods))]
        body.append("<h2>Weekly scoring</h2><div class='card'>" + line_chart(
            [{"name": "This team", "cls": "s1", "values": [w["points"] for w in t["weekly"]]},
             {"name": "League average", "cls": "ref", "values": league_avg}],
            periods, "Weekly points vs league average") + "</div>")

    head = "".join(f"<th class='n'>{p}</th>" for p in POSITION_ORDER)
    cells = "".join(f"<td class='n'>{fmt(t['by_pos'].get(p, 0), 0)}</td>" for p in POSITION_ORDER)
    rcells = "".join(f"<td class='n'>{rank_str(t['pos_ranks'][p])}</td>" for p in POSITION_ORDER)
    body.append("<h2>Points by position</h2>"
                f"<div class='card table-wrap'><table><thead><tr><th></th>{head}</tr></thead><tbody>"
                f"<tr><td>Starter points</td>{cells}</tr><tr><td>League rank</td>{rcells}</tr></tbody></table></div>")

    prow = []
    for p in t["players"]:
        status = "" if p["on_roster"] else " <span class='badge'>no longer on roster</span>"
        inj = f" <span class='badge'>{esc(p['injury'].replace('_', ' ').title())}</span>" if p["injury"] and p["injury"] != "ACTIVE" and p["on_roster"] else ""
        prow.append(f"<tr><td>{esc(p['name'])}{inj}{status}</td><td>{p['pos']}</td><td>{p['pro']}</td>"
                    f"<td class='n'>{p['starts']}</td><td class='n'>{fmt(p['start_pts'])}</td>"
                    f"<td class='n'>{fmt(p['per_start']) if p['per_start'] is not None else '—'}</td>"
                    f"<td class='n'>{p['bench_weeks']}</td><td class='n'>{fmt(p['bench_pts'])}</td></tr>")
    body.append("<h2>Players</h2>"
                '<p class="note">Points while on this team in completed weeks, split into points scored as a starter and on the bench.</p>'
                '<div class="card table-wrap"><table><thead><tr><th>Player</th><th>Pos</th><th>NFL</th>'
                '<th class="n">Starts</th><th class="n">Start pts</th><th class="n">Per start</th>'
                '<th class="n">Bench wks</th><th class="n">Bench pts</th></tr></thead><tbody>'
                + "".join(prow) + "</tbody></table></div>")

    return page(t["name"], "\n".join(body), data, prefix="../")


def markdown(text):
    """Minimal Markdown: #/##/### headings, paragraphs, - lists, **bold**, *italic*, [links](url)."""
    import re

    def inline(t):
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
        t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
        return t

    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
        if items:
            out.append("<ul class='facts'>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"(#{1,3}) (.*)", stripped)
        if not stripped:
            flush()
        elif m:
            flush()
            level = max(2, len(m.group(1)))  # page already has an h1
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
        elif stripped.startswith(("- ", "* ")):
            if para:
                flush()
            items.append(stripped[2:])
        else:
            if items:
                flush()
            para.append(stripped)
    flush()
    return "\n".join(out)


def load_recaps(content_dir, folder_name="recaps"):
    """Hand-written recaps: content/recaps/week-N.md.

    Format: '# Title', an optional intro, then one '## Headline' section per
    matchup. Inside a section, an '*italic*' first paragraph is the subheadline
    and an '@matchup A B' line (ESPN team ids) inserts the scoreboard and box score.
    """
    import re
    recaps = {}
    folder = os.path.join(content_dir, folder_name)
    if not os.path.isdir(folder):
        return recaps
    for fn in os.listdir(folder):
        m = re.fullmatch(r"week-(\d+)\.md", fn)
        if not m:
            continue
        with open(os.path.join(folder, fn), encoding="utf-8") as f:
            lines = f.read().splitlines()
        title = f"Week {m.group(1)} recaps"
        if lines and lines[0].startswith("# "):
            title = lines.pop(0)[2:].strip()
        intro, articles = [], []
        for ln in lines:
            if ln.startswith("## "):
                articles.append({"headline": ln[3:].strip(), "lines": [], "matchup": None})
            elif articles:
                mm = re.fullmatch(r"@matchup (\d+) (\d+)", ln.strip())
                if mm:
                    articles[-1]["matchup"] = (int(mm.group(1)), int(mm.group(2)))
                else:
                    articles[-1]["lines"].append(ln)
            else:
                intro.append(ln)
        for a in articles:
            body = "\n".join(a["lines"]).strip()
            first, _, rest = body.partition("\n\n")
            if first.startswith("*") and first.endswith("*") and not first.startswith("**"):
                a["dek"] = first.strip("*").strip()
                body = rest
            else:
                a["dek"] = None
            a["body"] = markdown(body)
        recaps[int(m.group(1))] = {"title": title, "intro": markdown("\n".join(intro)), "articles": articles}
    return recaps


def load_team_reports(content_dir):
    """Hand-written team reports: content/teams/<team id>.md.

    Format: '# Headline', optional '*subheadline*' paragraph, then the article.
    An optional 'Through Week N' line right after the headline sets the kicker.
    """
    import re
    reports = {}
    folder = os.path.join(content_dir, "teams")
    if not os.path.isdir(folder):
        return reports
    for fn in os.listdir(folder):
        m = re.fullmatch(r"(\d+)\.md", fn)
        if not m:
            continue
        with open(os.path.join(folder, fn), encoding="utf-8") as f:
            lines = f.read().splitlines()
        headline = lines.pop(0)[2:].strip() if lines and lines[0].startswith("# ") else ""
        kicker = None
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and re.fullmatch(r"Through Week \d+", lines[0].strip()):
            kicker = lines.pop(0).strip()
        body = "\n".join(lines).strip()
        first, _, rest = body.partition("\n\n")
        dek = None
        if first.startswith("*") and first.endswith("*") and not first.startswith("**"):
            dek, body = first.strip("*").strip(), rest
        reports[int(m.group(1))] = {"headline": headline, "kicker": kicker, "dek": dek, "body": markdown(body)}
    return reports


def _box_score(p, matchup, data):
    teams = data["teams"]
    result = next((r for r in data["results"] if r["period"] == p and {r["home"], r["away"]} == set(matchup)), None)
    if result is None:
        raise ValueError(f"Week {p} recap references teams {matchup}, which did not play each other that week")
    pd = data["period_data"][p]
    sides = [(result["home"], result["home_score"]), (result["away"], result["away_score"])]
    sides.sort(key=lambda s: -s[1])
    board = "".join(
        f'<div class="row{" win" if s == max(result["home_score"], result["away_score"]) and result["winner"] != "TIE" else ""}">'
        f'<span>{team_link(teams[tid], "../")}</span><span class="s">{fmt(s)}</span></div>'
        for tid, s in sides)
    cols = []
    for tid, _ in sides:
        starters = sorted((x for x in pd[tid]["players"] if x["started"]), key=lambda x: -x["points"])
        rows = "".join(f"<tr><td>{esc(x['name'])}</td><td>{x['pos']}</td><td class='n'>{fmt(x['points'])}</td>"
                       f"<td class='n muted'>{fmt(x['projection'])}</td></tr>" for x in starters)
        cols.append(f"<div><table><thead><tr><th>{esc(teams[tid]['name'])}</th><th>Pos</th><th class='n'>Pts</th>"
                    f"<th class='n'>Proj</th></tr></thead><tbody>{rows}</tbody></table></div>")
    return (f'<div class="scoreboard game">{board}</div>'
            f'<details class="box"><summary>Box score (starters)</summary><div class="box-cols">{"".join(cols)}</div></details>')


def _preview_box(p, matchup, data):
    teams = data["teams"]
    if p in data["completed"]:
        # The week has been played: show how it actually went.
        return (_box_score(p, matchup, data).split("<details")[0]
                + '<p class="note">Final result. This preview was written before the games.</p>')
    up = data.get("upcoming")
    if not up or up["period"] != p:
        return ""
    game = next((g for g in up["games"] if set(g) == set(matchup)), None)
    if game is None:
        raise ValueError(f"Week {p} preview references teams {matchup}, which don't play each other that week")
    a, b = (teams[x] for x in game)
    pa, pb = (up["teams"][x] for x in game)

    def last(t):
        return fmt(t["weekly"][-1]["points"]) if t["weekly"] else "—"

    rows = [
        ("Record", record(a), record(b)),
        ("Standing", ordinal(a["standing"]), ordinal(b["standing"])),
        ("Points per game", f"{fmt(a['ppg'])} ({rank_str(a['ranks']['ppg'])})", f"{fmt(b['ppg'])} ({rank_str(b['ranks']['ppg'])})"),
        ("All-play", f"{allplay(a)} ({rank_str(a['ranks']['allplay'])})", f"{allplay(b)} ({rank_str(b['ranks']['allplay'])})"),
        ("Last week", last(a), last(b)),
        ("ESPN projection", fmt(pa["projected"]), fmt(pb["projected"])),
    ] + [(f"{pos} rank", rank_str(a["pos_ranks"][pos]), rank_str(b["pos_ranks"][pos])) for pos in POSITION_ORDER]
    tape = "".join(f"<tr><td class='n'>{x}</td><td class='muted' style='text-align:center'>{k}</td><td>{y}</td></tr>"
                   for k, x, y in rows)
    cols = []
    for t, pt in ((a, pa), (b, pb)):
        body = "".join(
            f"<tr><td>{esc(r['name'])}"
            + (f" <span class='badge'>{esc(r['injury'].replace('_', ' ').title())}</span>" if r["injury"] not in ("", "ACTIVE") else "")
            + f"</td><td>{r['pos']}</td><td class='n'>{fmt(r['projection'])}</td></tr>" for r in pt["starters"])
        cols.append(f"<div><table><thead><tr><th>{esc(t['name'])}</th><th>Pos</th><th class='n'>Proj</th></tr></thead>"
                    f"<tbody>{body}</tbody></table></div>")
    gen = datetime.datetime.fromtimestamp(up["fetched"], datetime.timezone.utc)
    return (f'<div class="table-wrap"><table class="tape"><thead><tr><th class="n">{team_link(a, "../")}</th><th></th>'
            f'<th>{team_link(b, "../")}</th></tr></thead><tbody>{tape}</tbody></table></div>'
            f'<details class="box"><summary>Projected starting lineups (as of {gen:%b %d})</summary>'
            f'<div class="box-cols">{"".join(cols)}</div></details>')


def recap_week_page(p, recap, recaps, data, kind="recaps"):
    nav = []
    if p - 1 in recaps:
        nav.append(f'<a href="week-{p - 1}.html">← Week {p - 1}</a>')
    if p + 1 in recaps:
        nav.append(f'<a href="week-{p + 1}.html">Week {p + 1} →</a>')
    label = "Matchup previews" if kind == "previews" else "Matchup recaps"
    parts = [f'<p class="kicker">Week {p} · {label}</p><h1>{esc(recap["title"])}</h1>',
             f'<p class="sub">{" · ".join(nav) if nav else "&nbsp;"}</p>']
    if recap["intro"].strip():
        parts.append(f'<div class="card recap-intro">{recap["intro"]}</div>')
    boxer = _preview_box if kind == "previews" else _box_score
    for i, a in enumerate(recap["articles"], 1):
        dek = f'<p class="dek">{esc(a["dek"])}</p>' if a["dek"] else ""
        box = boxer(p, a["matchup"], data) if a["matchup"] else ""
        parts.append(f'<article class="card story" id="game-{i}"><h2>{esc(a["headline"])}</h2>{dek}{box}'
                     f'<div class="story-body">{a["body"]}</div></article>')
    return page(recap["title"], "\n".join(parts), data, prefix="../")


def recaps_index_page(recaps, data, kind="recaps"):
    if kind == "previews":
        title, sub, empty = "Matchup previews", "A look ahead at each week's matchups.", "No previews yet."
    else:
        title, sub, empty = "Matchup recaps", "Weekly write-ups of every matchup.", "No recaps yet."
    body = [f"<h1>{title}</h1>", f'<p class="sub">{sub}</p>']
    if not recaps:
        body.append(f'<div class="card">{empty}</div>')
    for p in sorted(recaps, reverse=True):
        r = recaps[p]
        items = "".join(f'<li><a href="{kind}/week-{p}.html#game-{i}">{esc(a["headline"])}</a></li>'
                        for i, a in enumerate(r["articles"], 1))
        body.append(f'<div class="card"><h2><a href="{kind}/week-{p}.html">{esc(r["title"])}</a></h2>'
                    f'<ul class="facts">{items}</ul></div>')
    return page(title.split()[-1].title(), "\n".join(body), data)


def about_page(data):
    body = """
<h1>How it works</h1>
<div class="card">
<h3>Data</h3>
<p>Everything comes from ESPN's public fantasy API. The site is rebuilt each week, when the recaps, team reports and previews are published. Only team names are shown.</p>
<h3>Completed weeks only</h3>
<p>Season stats (records, points, all-play, efficiency, player splits) only include finished weeks: ones ESPN has finalized, or ones where every game is over and ESPN projects no remaining points.
The second kind is marked "unofficial" until ESPN finalizes it.
The in-progress week appears in the live section and doesn't affect any season number. As a check, every build recomputes each team's score from its starting lineup
and stops if it doesn't match ESPN's official total.</p>
<h3>All-play record</h3>
<p>The record a team would have if it played every other team every week. It removes schedule luck and is the basis for the power rankings.</p>
<h3>Luck</h3>
<p>Actual wins minus expected wins, where expected wins = all-play win percentage × games played.</p>
<h3>Lineup efficiency</h3>
<p>Points started ÷ the best possible lineup from the same roster that week, known only in hindsight.</p>
<h3>Per-start and bench points</h3>
<p>Player points are split by whether the player was in the starting lineup (including FLEX) or on the bench/IR that week. "Per start" divides starting points by starts only.</p>
<h3>Playoff odds</h3>
<p>20,000 simulations of the remaining regular season. Each team's weekly score is drawn from a normal distribution centered halfway between its own PPG and the league average
(because early-season samples are small), with a standard deviation of 25 points. Live games start from the current score plus ESPN's projection for players yet to play.
Ties in the standings are broken by points scored. These are rough estimates that ignore injuries and roster moves.</p>
</div>
"""
    return page("How it works", body, data)


def write_site(data, out_dir, content_dir="content"):
    os.makedirs(os.path.join(out_dir, "teams"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "recaps"), exist_ok=True)
    recaps = load_recaps(content_dir)
    team_reports = load_team_reports(content_dir)

    def write(path, content):
        with open(os.path.join(out_dir, path), "w", encoding="utf-8") as f:
            f.write(content)

    write("index.html", index_page(data))
    write("weeks.html", weeks_page(data, recaps))
    write("about.html", about_page(data))
    write("recaps.html", recaps_index_page(recaps, data))
    os.makedirs(os.path.join(out_dir, "previews"), exist_ok=True)
    previews = load_recaps(content_dir, "previews")
    write("previews.html", recaps_index_page(previews, data, kind="previews"))
    for p, prev in previews.items():
        write(f"previews/week-{p}.html", recap_week_page(p, prev, previews, data, kind="previews"))
    for p, recap in recaps.items():
        write(f"recaps/week-{p}.html", recap_week_page(p, recap, recaps, data))
    for t in data["teams"].values():
        write(f"teams/{t['id']}.html", team_page(t, data, team_reports.get(t["id"])))
    write(".nojekyll", "")
