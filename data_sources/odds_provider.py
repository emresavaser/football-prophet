"""Odds API provider for betting odds data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from config.leagues import LEAGUES
from .base import RawOdds

BASE_URL = "https://api.the-odds-api.com/v4"

# The Odds API sport keys
LEAGUE_SPORT_KEYS = {
    "PL": "soccer_epl",
    "PD": "soccer_spain_la_liga",
    "SA": "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
    "TSL": "soccer_turkey_super_league",
    "ELC": "soccer_efl_champ",
}


class OddsProvider:
    """Fetches betting odds from The Odds API."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_odds(
        self, league_code: str, markets: str = "h2h,totals"
    ) -> list[RawOdds]:
        sport_key = LEAGUE_SPORT_KEYS.get(league_code)
        if not sport_key:
            return []

        params = {
            "apiKey": self._api_key,
            "regions": "eu",
            "markets": markets,
            "oddsFormat": "decimal",
        }

        resp = await self._client.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for event in data:
            odds = self._parse_event_odds(event)
            if odds:
                results.append(odds)
        return results

    def _parse_event_odds(self, event: dict) -> Optional[RawOdds]:
        """Parse event into averaged odds across bookmakers."""
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        event_id = event.get("id", "")

        h2h_odds: list[dict] = []
        totals_odds: list[dict] = []

        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") == "h2h":
                    outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                    h2h_odds.append(outcomes)
                elif market.get("key") == "totals":
                    outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                    totals_odds.append(outcomes)

        if not h2h_odds:
            return None

        # Average across bookmakers
        home_wins = [o.get(home_team, 0) for o in h2h_odds if o.get(home_team)]
        draws = [o.get("Draw", 0) for o in h2h_odds if o.get("Draw")]
        away_wins = [o.get(away_team, 0) for o in h2h_odds if o.get(away_team)]

        overs = [o.get("Over", 0) for o in totals_odds if o.get("Over")]
        unders = [o.get("Under", 0) for o in totals_odds if o.get("Under")]

        def avg(vals: list[float]) -> Optional[float]:
            return sum(vals) / len(vals) if vals else None

        return RawOdds(
            match_external_id=event_id,
            bookmaker="average",
            home_win=avg(home_wins),
            draw=avg(draws),
            away_win=avg(away_wins),
            over_25=avg(overs),
            under_25=avg(unders),
        )

    async def close(self) -> None:
        await self._client.aclose()
