"""Build the league website.

Usage:
    python build.py                 # fetch live data, write site/
    python build.py --cache .cache  # reuse saved API responses (for local dev)
    python build.py --facts 3       # print verified numbers for writing Week 3 recaps
"""

import argparse
import datetime
import os
import sys

from fantasy.analysis import DataMismatch, analyze
from fantasy.espn import ESPN
from fantasy.factsheet import format_fact_sheet
from fantasy.render import write_site

DEFAULT_LEAGUE_ID = "148167114"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default=os.environ.get("LEAGUE_ID", DEFAULT_LEAGUE_ID))
    parser.add_argument("--season", type=int,
                        default=int(os.environ.get("SEASON", datetime.date.today().year)))
    parser.add_argument("--out", default="site")
    parser.add_argument("--cache", default=None, help="directory for cached API responses")
    parser.add_argument("--facts", type=int, metavar="WEEK",
                        help="print the verified fact sheet for a completed week instead of building")
    args = parser.parse_args()

    api = ESPN(args.league, args.season, cache_dir=args.cache)
    league = api.league()
    current = league["status"]["currentMatchupPeriod"]
    period_map = {int(k): v for k, v in league["settings"]["scheduleSettings"]["matchupPeriods"].items()}
    scoring_periods = sorted({sp for p in range(1, current + 1) for sp in period_map.get(p, [])})
    weeks = {sp: api.week(sp) for sp in scoring_periods}
    pro = api.pro_schedule()

    try:
        data = analyze(league, weeks, pro)
    except DataMismatch as e:
        sys.exit(f"Build stopped: {e}")

    if args.facts is not None:
        sys.stdout.reconfigure(encoding="utf-8")
        print(format_fact_sheet(data, args.facts))
        return

    write_site(data, args.out)
    print(f"Built {len(data['teams'])} team pages; completed weeks: {data['completed']}; "
          f"live week: {data['live']['period'] if data['live'] else 'none'} -> {args.out}/")


if __name__ == "__main__":
    main()
