"""Fetch public league data from the ESPN Fantasy API."""

import json
import os
import urllib.request

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"


class ESPN:
    def __init__(self, league_id, season, cache_dir=None):
        self.league_id = league_id
        self.season = season
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _get(self, url, cache_name):
        if self.cache_dir:
            path = os.path.join(self.cache_dir, cache_name)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        req = urllib.request.Request(url, headers={"User-Agent": "fantasy-analysis"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        if self.cache_dir:
            with open(os.path.join(self.cache_dir, cache_name), "w", encoding="utf-8") as f:
                json.dump(data, f)
        return data

    def _league_url(self, query):
        return BASE.format(season=self.season) + f"/segments/0/leagues/{self.league_id}?{query}"

    def league(self):
        return self._get(self._league_url("view=mTeam&view=mSettings&view=mMatchup"), "league.json")

    def week(self, scoring_period):
        q = f"scoringPeriodId={scoring_period}&view=mRoster&view=mMatchupScore"
        return self._get(self._league_url(q), f"week{scoring_period}.json")

    def pro_schedule(self):
        return self._get(BASE.format(season=self.season) + "?view=proTeamSchedules_wl", "pro.json")
