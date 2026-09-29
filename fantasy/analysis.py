"""Turn raw ESPN responses into league statistics.

Season stats only use matchup periods where every regular-season game has an
official winner. The in-progress week is reported separately as live data.
"""

import random
import statistics
import time

POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "D/ST"]
BENCH_SLOTS = {20, 21}  # bench, IR
INACTIVE_STATUSES = {"OUT", "INJURY_RESERVE", "DOUBTFUL", "SUSPENSION"}
SIMULATIONS = 20000
WEEKLY_SD = 25.0
GAME_WINDOW = 4 * 3600  # treat a game as possibly in progress for 4h after kickoff


class DataMismatch(Exception):
    pass


def player_points(player, scoring_period, source=0):
    """source 0 = actual points, 1 = ESPN projection."""
    for s in player.get("stats", []):
        if (s.get("scoringPeriodId") == scoring_period and s.get("statSourceId") == source
                and s.get("statSplitTypeId") == 1):
            return s.get("appliedTotal", 0.0)
    return 0.0


def optimal_points(entries, lineup_counts):
    """Best possible lineup score in hindsight.

    Fills the most restrictive slots first (fewest eligible players), which is
    optimal for standard ESPN slot sets where FLEX-style slots are supersets.
    """
    slots = []
    for slot_id, count in lineup_counts.items():
        if slot_id in BENCH_SLOTS or count <= 0:
            continue
        slots.extend([slot_id] * count)
    pool = [(e["points"], set(e["eligible"])) for e in entries]
    slots.sort(key=lambda sl: sum(1 for _, el in pool if sl in el))
    used = set()
    total = 0.0
    for sl in slots:
        best = None
        for i, (pts, el) in enumerate(pool):
            if i in used or sl not in el:
                continue
            if best is None or pts > pool[best][0]:
                best = i
        if best is not None:
            used.add(best)
            total += pool[best][0]
    return total


def rank_with_ties(values, higher_is_better=True):
    """Map key -> (rank, tied) using competition ranking."""
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_better)
    out = {}
    for key, val in items:
        rank = 1 + sum(1 for _, v in items if (v > val if higher_is_better else v < val))
        tied = sum(1 for _, v in items if abs(v - val) < 1e-9) > 1
        out[key] = (rank, tied)
    return out


def analyze(league, weeks, pro, now=None):
    now = now if now is not None else time.time()
    settings = league["settings"]
    sched_settings = settings["scheduleSettings"]
    regular_periods = sched_settings["matchupPeriodCount"]
    playoff_teams = sched_settings["playoffTeamCount"]
    period_map = {int(k): v for k, v in sched_settings["matchupPeriods"].items()}
    lineup_counts = {int(k): v for k, v in settings["rosterSettings"]["lineupSlotCounts"].items()}
    current_period = league["status"]["currentMatchupPeriod"]

    teams = {t["id"]: {"id": t["id"], "name": t["name"].strip(), "abbrev": t.get("abbrev", "")}
             for t in league["teams"]}

    pro_abbrev = {t["id"]: t["abbrev"] for t in pro["settings"]["proTeams"]}
    kickoff = {}  # (proTeamId, scoringPeriod) -> epoch seconds
    for t in pro["settings"]["proTeams"]:
        for sp, games in t.get("proGamesByScoringPeriod", {}).items():
            for g in games:
                kickoff[(t["id"], int(sp))] = g["date"] / 1000

    matchups = {}
    for m in league["schedule"]:
        if "away" not in m:
            continue  # bye
        matchups.setdefault(m["matchupPeriodId"], []).append(m)

    def regular(p):
        return p <= regular_periods

    def official(p):
        return all(m.get("winner") not in (None, "UNDECIDED") for m in matchups[p])

    def all_games_over(p):
        """Every NFL game in the period has kicked off and ESPN projects no
        remaining points for any team (projected live total == live total)."""
        times = [ts for (_, sp), ts in kickoff.items() if sp in period_map.get(p, [])]
        if not times or max(times) > now:
            return False
        sides = [m[s] for m in weeks.get(period_map[p][-1], {}).get("schedule", [])
                 if m.get("matchupPeriodId") == p and "away" in m for s in ("home", "away")]
        return bool(sides) and all(
            s.get("totalProjectedPointsLive") is not None
            and abs(s["totalProjectedPointsLive"] - s.get("totalPointsLive", 0.0)) < 0.01
            for s in sides)

    # A week ESPN hasn't finalized yet counts as complete (unofficially) once
    # all its games are over. Winners come from the live totals.
    unofficial = []
    for p in sorted(matchups):
        if regular(p) and p <= current_period and not official(p) and all_games_over(p):
            live_week = weeks.get(period_map[p][-1], {})
            live = {m["id"]: m for m in live_week.get("schedule", []) if m.get("matchupPeriodId") == p}
            final = []
            for m in matchups[p]:
                lm = live.get(m["id"], m)
                m = {**m, "home": dict(m["home"]), "away": dict(m["away"])}
                for side in ("home", "away"):
                    m[side]["totalPoints"] = lm[side].get("totalPointsLive", lm[side].get("totalPoints", 0.0))
                hs, as_ = m["home"]["totalPoints"], m["away"]["totalPoints"]
                m["winner"] = "HOME" if hs > as_ else "AWAY" if as_ > hs else "TIE"
                final.append(m)
            matchups[p] = final
            unofficial.append(p)

    completed = [p for p in sorted(matchups)
                 if regular(p) and p <= current_period and (official(p) or p in unofficial)]
    live_period = current_period if current_period not in completed and regular(current_period) else None

    # ---- per-team, per-period lineup data ----
    def lineup_data(period):
        out = {}
        for sp in period_map[period]:
            wk = weeks[sp]
            for t in wk["teams"]:
                d = out.setdefault(t["id"], {"started": 0.0, "optimal": 0.0, "bench": 0.0,
                                             "by_pos": {}, "players": [], "pending": [], "in_game": [],
                                             "remaining_proj": 0.0})
                entries = []
                for e in t["roster"]["entries"]:
                    p = e["playerPoolEntry"]["player"]
                    pts = player_points(p, sp)
                    pos = POSITIONS.get(p["defaultPositionId"], "?")
                    started = e["lineupSlotId"] not in BENCH_SLOTS
                    start_time = kickoff.get((p.get("proTeamId"), sp))
                    not_started = start_time is not None and start_time > now
                    in_game = start_time is not None and start_time <= now < start_time + GAME_WINDOW
                    entries.append({"points": pts, "eligible": p.get("eligibleSlots", [])})
                    d["players"].append({
                        "id": p["id"], "name": p["fullName"], "pos": pos,
                        "pro": pro_abbrev.get(p.get("proTeamId"), "FA"),
                        "points": pts, "projection": player_points(p, sp, source=1),
                        "started": started, "pending": not_started,
                        "injury": p.get("injuryStatus") or "",
                    })
                    if started:
                        d["started"] += pts
                        d["by_pos"][pos] = d["by_pos"].get(pos, 0.0) + pts
                        if not_started:
                            proj = player_points(p, sp, source=1)
                            d["pending"].append({"name": p["fullName"], "pro": pro_abbrev.get(p.get("proTeamId"), "FA"),
                                                 "projection": proj})
                            d["remaining_proj"] += proj
                        elif in_game:
                            d["in_game"].append({"name": p["fullName"], "pro": pro_abbrev.get(p.get("proTeamId"), "FA")})
                    else:
                        d["bench"] += pts
                d["optimal"] += optimal_points(entries, lineup_counts)
        return out

    period_data = {p: lineup_data(p) for p in completed}
    live_data = lineup_data(live_period) if live_period else None

    # ---- sanity check: our lineup totals must match ESPN's official scores ----
    for p in completed:
        for m in matchups[p]:
            for side in ("home", "away"):
                tid = m[side]["teamId"]
                official = m[side].get("totalPoints", 0.0)
                ours = period_data[p][tid]["started"]
                if abs(official - ours) > 0.05:
                    raise DataMismatch(
                        f"Period {p}, {teams[tid]['name']}: computed {ours:.2f} but ESPN shows {official:.2f}")

    # ---- results ----
    for t in teams.values():
        t.update(wins=0, losses=0, ties=0, pf=0.0, pa=0.0, allplay_w=0, allplay_l=0, allplay_t=0,
                 weekly=[], started=0.0, optimal=0.0, bench=0.0, by_pos={})

    results = []
    for p in completed:
        scores = {tid: period_data[p][tid]["started"] for tid in teams}
        for m in matchups[p]:
            h, a = m["home"]["teamId"], m["away"]["teamId"]
            hs, as_ = scores[h], scores[a]
            teams[h]["pf"] += hs; teams[h]["pa"] += as_
            teams[a]["pf"] += as_; teams[a]["pa"] += hs
            if m["winner"] == "HOME":
                teams[h]["wins"] += 1; teams[a]["losses"] += 1
            elif m["winner"] == "AWAY":
                teams[a]["wins"] += 1; teams[h]["losses"] += 1
            else:
                teams[h]["ties"] += 1; teams[a]["ties"] += 1
            results.append({"period": p, "home": h, "away": a, "home_score": hs, "away_score": as_,
                             "winner": m["winner"]})
        for tid, s in scores.items():
            t = teams[tid]
            for oid, os_ in scores.items():
                if oid == tid:
                    continue
                if s > os_:
                    t["allplay_w"] += 1
                elif s < os_:
                    t["allplay_l"] += 1
                else:
                    t["allplay_t"] += 1
            d = period_data[p][tid]
            t["weekly"].append({"period": p, "points": s})
            t["started"] += d["started"]
            t["optimal"] += d["optimal"]
            t["bench"] += d["bench"]
            for pos, v in d["by_pos"].items():
                t["by_pos"][pos] = t["by_pos"].get(pos, 0.0) + v

    games = len(completed)
    for t in teams.values():
        t["games"] = games
        t["ppg"] = t["pf"] / games if games else 0.0
        ap_games = t["allplay_w"] + t["allplay_l"] + t["allplay_t"]
        t["allplay_pct"] = (t["allplay_w"] + 0.5 * t["allplay_t"]) / ap_games if ap_games else 0.0
        t["expected_wins"] = t["allplay_pct"] * games
        t["luck"] = t["wins"] + 0.5 * t["ties"] - t["expected_wins"]
        t["efficiency"] = t["started"] / t["optimal"] if t["optimal"] else 0.0
        t["high"] = max((w["points"] for w in t["weekly"]), default=0.0)
        t["low"] = min((w["points"] for w in t["weekly"]), default=0.0)
        t["stdev"] = statistics.pstdev([w["points"] for w in t["weekly"]]) if games > 1 else 0.0

    # ---- player splits per team (completed periods only) ----
    for tid, t in teams.items():
        rows = {}
        for p in completed:
            for pl in period_data[p][tid]["players"]:
                r = rows.setdefault(pl["id"], {"name": pl["name"], "pos": pl["pos"], "pro": pl["pro"],
                                               "start_pts": 0.0, "starts": 0, "bench_pts": 0.0,
                                               "bench_weeks": 0, "injury": pl["injury"]})
                if pl["started"]:
                    r["start_pts"] += pl["points"]; r["starts"] += 1
                else:
                    r["bench_pts"] += pl["points"]; r["bench_weeks"] += 1
        current_ids = set()
        latest = weeks[max(weeks)]
        for lt in latest["teams"]:
            if lt["id"] == tid:
                for e in lt["roster"]["entries"]:
                    pl = e["playerPoolEntry"]["player"]
                    current_ids.add(pl["id"])
                    if pl["id"] in rows:
                        rows[pl["id"]]["injury"] = pl.get("injuryStatus") or ""
                    else:
                        rows[pl["id"]] = {"name": pl["fullName"], "pos": POSITIONS.get(pl["defaultPositionId"], "?"),
                                          "pro": pro_abbrev.get(pl.get("proTeamId"), "FA"), "start_pts": 0.0,
                                          "starts": 0, "bench_pts": 0.0, "bench_weeks": 0,
                                          "injury": pl.get("injuryStatus") or ""}
        for pid, r in rows.items():
            r["on_roster"] = pid in current_ids
            r["per_start"] = r["start_pts"] / r["starts"] if r["starts"] else None
        t["players"] = sorted(rows.values(), key=lambda r: -(r["start_pts"] + r["bench_pts"]))

    # ---- ranks ----
    ranks = {
        "ppg": rank_with_ties({tid: t["ppg"] for tid, t in teams.items()}),
        "allplay": rank_with_ties({tid: t["allplay_pct"] for tid, t in teams.items()}),
        "efficiency": rank_with_ties({tid: t["efficiency"] for tid, t in teams.items()}),
    }
    pos_ranks = {pos: rank_with_ties({tid: t["by_pos"].get(pos, 0.0) for tid, t in teams.items()})
                 for pos in POSITION_ORDER}
    for tid, t in teams.items():
        t["ranks"] = {k: v[tid] for k, v in ranks.items()}
        t["pos_ranks"] = {pos: pos_ranks[pos][tid] for pos in POSITION_ORDER}

    # ---- live week ----
    live = None
    if live_period:
        # The league endpoint doesn't carry live totals; the week endpoint does.
        live_week = weeks[period_map[live_period][-1]]
        live_matchups = [m for m in live_week.get("schedule", [])
                         if m.get("matchupPeriodId") == live_period and "away" in m] or matchups[live_period]
        games_live = []
        for m in live_matchups:
            side = {}
            for key in ("home", "away"):
                tid = m[key]["teamId"]
                d = live_data[tid]
                official_live = m[key].get("totalPointsLive")
                proj_live = m[key].get("totalProjectedPointsLive")
                score = official_live if official_live is not None else d["started"]
                remaining = (proj_live - score) if proj_live is not None else d["remaining_proj"]
                side[key] = {"team": tid, "score": score, "remaining": max(0.0, remaining),
                             "pending": d["pending"], "in_game": d["in_game"]}
            games_live.append(side)
        live = {"period": live_period, "games": games_live}

    # ---- playoff odds ----
    league_ppg = statistics.mean(t["ppg"] for t in teams.values()) if games else 0.0
    est = {tid: 0.5 * t["ppg"] + 0.5 * league_ppg for tid, t in teams.items()}
    future = [(m["home"]["teamId"], m["away"]["teamId"]) for p in sorted(matchups)
              if regular(p) and p not in completed and p != live_period for m in matchups[p]]
    for tid, t in teams.items():
        opps = [a if h == tid else h for h, a in future if tid in (h, a)]
        t["remaining_sos"] = statistics.mean(teams[o]["ppg"] for o in opps) if opps else None

    odds = {tid: {"playoffs": 0, "first": 0} for tid in teams}
    rng = random.Random(2026)
    if games:
        for _ in range(SIMULATIONS):
            w = {tid: t["wins"] + 0.5 * t["ties"] for tid, t in teams.items()}
            pts = {tid: t["pf"] for tid, t in teams.items()}
            if live:
                for g in live["games"]:
                    h, a = g["home"], g["away"]
                    hs = h["score"] + h["remaining"] + (rng.gauss(0, 0.5 * h["remaining"]) if h["remaining"] else 0)
                    as_ = a["score"] + a["remaining"] + (rng.gauss(0, 0.5 * a["remaining"]) if a["remaining"] else 0)
                    pts[h["team"]] += hs; pts[a["team"]] += as_
                    w[h["team"] if hs > as_ else a["team"]] += 1
            for h, a in future:
                hs, as_ = rng.gauss(est[h], WEEKLY_SD), rng.gauss(est[a], WEEKLY_SD)
                pts[h] += hs; pts[a] += as_
                w[h if hs > as_ else a] += 1
            order = sorted(teams, key=lambda tid: (-w[tid], -pts[tid]))
            for tid in order[:playoff_teams]:
                odds[tid]["playoffs"] += 1
            odds[order[0]]["first"] += 1
    for tid, t in teams.items():
        t["playoff_odds"] = odds[tid]["playoffs"] / SIMULATIONS if games else None
        t["first_seed_odds"] = odds[tid]["first"] / SIMULATIONS if games else None

    standings = sorted(teams.values(), key=lambda t: (-(t["wins"] + 0.5 * t["ties"]), -t["pf"]))
    for i, t in enumerate(standings, 1):
        t["standing"] = i

    return {
        "league_name": settings["name"],
        "season": league["seasonId"],
        "size": len(teams),
        "regular_periods": regular_periods,
        "playoff_teams": playoff_teams,
        "completed": completed,
        "unofficial": unofficial,
        "teams": teams,
        "standings": standings,
        "results": results,
        "period_data": period_data,
        "schedule": [{"period": p, "home": m["home"]["teamId"], "away": m["away"]["teamId"]}
                     for p in sorted(matchups) if regular(p) for m in matchups[p]],
        "live": live,
        "league_ppg": league_ppg,
        "generated": now,
    }
