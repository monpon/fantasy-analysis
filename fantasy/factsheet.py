"""Verified facts for each completed week's matchups.

Used as source material when writing recaps by hand: every number here comes
straight from the box scores, so the write-up can be checked against it.
"""

BLOWOUT_MARGIN = 40.0
CLOSE_MARGIN = 5.0
UPSET_PPG_GAP = 10.0
SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def _f(x):
    return f"{x:.1f}"


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _record(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")


def build_facts(data):
    teams = data["teams"]
    pdata = data["period_data"]
    n = data["size"]

    # Running records and PPG before each week.
    rec = {tid: [0, 0, 0] for tid in teams}
    pts_so_far = {tid: 0.0 for tid in teams}
    by_period = {}
    for r in data["results"]:
        by_period.setdefault(r["period"], []).append(r)

    recaps = {}
    for idx, p in enumerate(data["completed"]):
        scores = {tid: pdata[p][tid]["started"] for tid in teams}
        ordered = sorted(scores.values(), reverse=True)
        week_rank = {tid: 1 + sum(1 for v in scores.values() if v > s) for tid, s in scores.items()}
        beats = {tid: sum(1 for o, v in scores.items() if o != tid and s > v) for tid, s in scores.items()}
        before = {tid: tuple(rec[tid]) for tid in teams}
        ppg_before = {tid: (pts_so_far[tid] / idx if idx else None) for tid in teams}

        games = []
        for r in by_period[p]:
            h, a = r["home"], r["away"]
            if r["winner"] == "TIE":
                win, lose = h, a
            else:
                win, lose = (h, a) if r["winner"] == "HOME" else (a, h)
            ws, ls = scores[win], scores[lose]
            margin = ws - ls
            W, L = teams[win]["name"], teams[lose]["name"]
            tie = r["winner"] == "TIE"

            # Headline: the most notable true thing about the game.
            upset = (ppg_before[win] is not None and ppg_before[lose] - ppg_before[win] >= UPSET_PPG_GAP)
            if tie:
                headline = f"{W} and {L} tie at {_f(ws)}"
            elif upset:
                headline = (f"Upset: {W} beats {L} "
                            f"(entered averaging {_f(ppg_before[win])} vs. {_f(ppg_before[lose])})")
            elif week_rank[lose] <= 3:
                headline = f"{L} loses despite the week's {_ordinal(week_rank[lose])}-highest score"
            elif margin < CLOSE_MARGIN:
                headline = f"{W} edges {L} by {_f(margin)}"
            elif margin >= BLOWOUT_MARGIN:
                headline = f"{W} routs {L} by {_f(margin)}"
            else:
                headline = f"{W} beats {L}, {_f(ws)}–{_f(ls)}"

            facts = []
            if not tie:
                facts.append(f"Final: {W} {_f(ws)}, {L} {_f(ls)} (margin {_f(margin)}).")
            facts.append(f"{W}'s score ranked {_ordinal(week_rank[win])} of {n} this week and would have beaten "
                         f"{beats[win]} of {n - 1} teams; {L}'s ranked {_ordinal(week_rank[lose])} "
                         f"and would have beaten {beats[lose]}.")

            sides = []
            for tid in (win, lose):
                d = pdata[p][tid]
                starters = sorted((x for x in d["players"] if x["started"]), key=lambda x: -x["points"])
                bench = sorted((x for x in d["players"] if not x["started"]), key=lambda x: -x["points"])
                skill = [x for x in starters if x["pos"] in SKILL_POSITIONS and x["projection"] > 0]
                over = max(skill, key=lambda x: x["points"] - x["projection"], default=None)
                under = min(skill, key=lambda x: x["points"] - x["projection"], default=None)
                sides.append({
                    "team": tid,
                    "score": scores[tid],
                    "top": starters[:3],
                    "over": over if over and over["points"] - over["projection"] >= 5 else None,
                    "under": under if under and under["points"] - under["projection"] <= -5 else None,
                    "best_bench": bench[0] if bench and bench[0]["points"] > 0 else None,
                    "left_on_bench": d["optimal"] - d["started"],
                    "optimal": d["optimal"],
                    "record_before": before[tid],
                })

            if not tie:
                lose_side = sides[1]
                if lose_side["optimal"] > ws:
                    facts.append(f"{L}'s best possible lineup would have scored {_f(lose_side['optimal'])}, "
                                 f"enough to win. They left {_f(lose_side['left_on_bench'])} points on the bench.")
                else:
                    facts.append(f"Even {L}'s best possible lineup ({_f(lose_side['optimal'])}) "
                                 f"would not have caught {W}.")

            for s in sides:
                t = teams[s["team"]]["name"]
                w, l, tt = s["record_before"]
                if s["team"] == win and not tie:
                    w += 1
                elif s["team"] == lose and not tie:
                    l += 1
                else:
                    tt += 1
                s["record_after"] = _record(w, l, tt)
                s["record_before_str"] = _record(*s["record_before"])
                lines = []
                lines.append("Top starters: " + ", ".join(
                    f"{x['name']} ({x['pos']}) {_f(x['points'])}" for x in s["top"]) + ".")
                if s["over"]:
                    x = s["over"]
                    lines.append(f"Beat projection: {x['name']}, {_f(x['points'])} vs. {_f(x['projection'])} projected.")
                if s["under"]:
                    x = s["under"]
                    lines.append(f"Missed projection: {x['name']}, {_f(x['points'])} vs. {_f(x['projection'])} projected.")
                if s["best_bench"]:
                    x = s["best_bench"]
                    lines.append(f"Best bench score: {x['name']} ({x['pos']}) {_f(x['points'])}. "
                                 f"{_f(s['left_on_bench'])} points left on the bench overall.")
                lines.append(f"Record: {s['record_before_str']} → {s['record_after']}.")
                d = pdata[p][s["team"]]
                lines.append("Full starting lineup (actual / projected): " + "; ".join(
                    f"{x['name']} {x['pos']} {_f(x['points'])}/{_f(x['projection'])}"
                    for x in sorted((x for x in d["players"] if x["started"]), key=lambda x: -x["points"])) + ".")
                lines.append("Bench (actual): " + "; ".join(
                    f"{x['name']} {x['pos']} {_f(x['points'])}"
                    for x in sorted((x for x in d["players"] if not x["started"]), key=lambda x: -x["points"])) + ".")
                nxt = next((g for g in data["schedule"] if g["period"] == p + 1 and s["team"] in (g["home"], g["away"])), None)
                if nxt:
                    opp = nxt["away"] if nxt["home"] == s["team"] else nxt["home"]
                    lines.append(f"Next opponent (Week {p + 1}): {teams[opp]['name']}.")
                s["lines"] = lines
                s["name"] = t

            games.append({"headline": headline, "facts": facts, "sides": sides, "margin": margin,
                          "winner": None if tie else win})

        # Week-level notes.
        top_tid = max(scores, key=scores.get)
        low_tid = min(scores, key=scores.get)
        closest = min(games, key=lambda g: g["margin"])
        biggest = max(games, key=lambda g: g["margin"])
        all_starters = [(tid, x) for tid in teams for x in pdata[p][tid]["players"] if x["started"]]
        star_tid, star = max(all_starters, key=lambda tx: tx[1]["points"])
        notes = [
            f"High score: {teams[top_tid]['name']}, {_f(scores[top_tid])}. "
            f"Low score: {teams[low_tid]['name']}, {_f(scores[low_tid])}.",
            f"League average: {_f(sum(ordered) / n)}.",
            f"Closest game: {_f(closest['margin'])} points. Biggest margin: {_f(biggest['margin'])} points.",
            f"Top starter: {star['name']} ({star['pos']}, {teams[star_tid]['name']}) with {_f(star['points'])}.",
        ]
        recaps[p] = {"period": p, "games": games, "notes": notes}

        for r in by_period[p]:
            h, a = r["home"], r["away"]
            if r["winner"] == "HOME":
                rec[h][0] += 1; rec[a][1] += 1
            elif r["winner"] == "AWAY":
                rec[a][0] += 1; rec[h][1] += 1
            else:
                rec[h][2] += 1; rec[a][2] += 1
        for tid in teams:
            pts_so_far[tid] += scores[tid]

    return recaps


def format_preview_sheet(data, period):
    up = next((x for x in (data.get("upcoming"), data.get("live_projections")) if x and x["period"] == period), None)
    if not up:
        have = [x["period"] for x in (data.get("upcoming"), data.get("live_projections")) if x]
        return f"No preview data for Week {period}. Weeks with projections: {have or 'none'}."
    teams = data["teams"]
    last = data["completed"][-1] if data["completed"] else None
    out = [f"WEEK {period} PREVIEW FACT SHEET (ESPN projections as currently set; lineups may change)", "=" * 60]
    started = sorted({r["pro"] for t in up["teams"].values() for r in t["starters"] + t["bench"] if r["kicked_off"]})
    if started:
        out.append(f"NOTE: this week has already started. NFL teams that have kicked off: {', '.join(started)}. "
                   "Their players are marked [PLAYED]; projections shown are ESPN's pre-game numbers.")
    for h, a in up["games"]:
        out += ["", "-" * 60, f"{teams[h]['name']} vs {teams[a]['name']}"]
        for tid in (h, a):
            t, pt = teams[tid], up["teams"][tid]
            recent = [w["points"] for w in t["weekly"]]
            streak_res = [r for r in data["results"] if tid in (r["home"], r["away"])]
            res = "".join("W" if (r["winner"] == "HOME") == (r["home"] == tid) else "L" for r in streak_res)
            out.append(f"  {t['name']}: {t['wins']}-{t['losses']} ({_ordinal(t['standing'])} place), "
                       f"PPG {_f(t['ppg'])} ({_ordinal(t['ranks']['ppg'][0])}), all-play "
                       f"{t['allplay_w']}-{t['allplay_l']} ({_ordinal(t['ranks']['allplay'][0])}), results {res}, "
                       f"weekly {', '.join(_f(x) for x in recent)}"
                       + (f", last week {_f(recent[-1])}" if last else ""))
            out.append(f"    Projected (current lineup): {_f(pt['projected'])} | best possible projected lineup: "
                       f"{_f(pt['best_projected'])}")
            out.append("    Position ranks: " + ", ".join(f"{p} {_ordinal(t['pos_ranks'][p][0])}" for p in t["pos_ranks"]))
            out.append("    Projected starters: " + "; ".join(
                f"{r['name']} {r['pos']} {_f(r['projection'])}" + (f" [{r['injury']}]" if r["injury"] not in ("", "ACTIVE") else "") + (" [PLAYED]" if r["kicked_off"] else "")
                for r in pt["starters"]))
            out.append("    Bench: " + "; ".join(
                f"{r['name']} {r['pos']} {_f(r['projection'])}" + (f" [{r['injury']}]" if r["injury"] not in ("", "ACTIVE") else "") + (" [PLAYED]" if r["kicked_off"] else "")
                for r in pt["bench"]))
            if pt["flagged"]:
                out.append("    FLAG, starter listed out or projected 0: " + ", ".join(
                    f"{r['name']} ({r['injury'] or 'proj 0'})" for r in pt["flagged"]))
        diff = up["teams"][h]["projected"] - up["teams"][a]["projected"]
        fav = teams[h]["name"] if diff > 0 else teams[a]["name"]
        out.append(f"  ESPN projection favors {fav} by {_f(abs(diff))}.")
    return "\n".join(out)


def format_fact_sheet(data, period):
    facts = build_facts(data)
    if period not in facts:
        done = ", ".join(map(str, data["completed"])) or "none"
        return f"Week {period} is not final yet. Completed weeks: {done}."
    wk = facts[period]
    out = [f"WEEK {period} FACT SHEET", "=" * 40, ""]
    out += [f"- {x}" for x in wk["notes"]]
    for g in wk["games"]:
        out += ["", "-" * 40, f"Suggested angle: {g['headline']}"]
        out += [f"- {x}" for x in g["facts"]]
        for s in g["sides"]:
            out.append(f"  {s['name']} ({s['score']:.1f})")
            out += [f"    - {x}" for x in s["lines"]]
    return "\n".join(out)
