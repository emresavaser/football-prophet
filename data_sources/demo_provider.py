"""Demo data provider for testing the full pipeline without API keys."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from .base import DataSourceAdapter, RawMatch, RawTeamStats, RawOdds

# Premier League 2024-25 teams
PL_TEAMS = [
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Chelsea", "Crystal Palace", "Everton", "Fulham", "Ipswich Town",
    "Leicester City", "Liverpool", "Manchester City", "Manchester United",
    "Newcastle United", "Nottingham Forest", "Southampton", "Tottenham",
    "West Ham United", "Wolverhampton",
]

# Approximate strength tiers for realistic data
TEAM_STRENGTH = {
    "Manchester City": 0.90, "Arsenal": 0.88, "Liverpool": 0.87,
    "Chelsea": 0.78, "Tottenham": 0.76, "Newcastle United": 0.75,
    "Manchester United": 0.73, "Aston Villa": 0.72, "Brighton": 0.70,
    "West Ham United": 0.65, "Brentford": 0.63, "Crystal Palace": 0.62,
    "Fulham": 0.61, "Bournemouth": 0.60, "Nottingham Forest": 0.58,
    "Wolverhampton": 0.55, "Everton": 0.53, "Leicester City": 0.50,
    "Ipswich Town": 0.45, "Southampton": 0.42,
}


def _simulate_score(home_strength: float, away_strength: float) -> tuple[int, int]:
    """Simulate a realistic match score based on team strengths."""
    home_lambda = 1.2 + home_strength * 1.2
    away_lambda = 0.6 + away_strength * 1.0
    home_goals = min(6, max(0, int(random.expovariate(1 / home_lambda))))
    away_goals = min(5, max(0, int(random.expovariate(1 / away_lambda))))
    return home_goals, away_goals


def _generate_odds(home_strength: float, away_strength: float) -> dict:
    """Generate realistic odds from strengths."""
    diff = home_strength - away_strength
    home_prob = 0.44 + diff * 0.4
    home_prob = max(0.15, min(0.80, home_prob))
    draw_prob = max(0.15, 0.28 - abs(diff) * 0.2)
    away_prob = 1.0 - home_prob - draw_prob

    margin = 1.05  # 5% bookmaker margin
    return {
        "home_win": round(margin / home_prob, 2),
        "draw": round(margin / draw_prob, 2),
        "away_win": round(margin / away_prob, 2),
        "over_25": round(random.uniform(1.7, 2.1), 2),
        "under_25": round(random.uniform(1.75, 2.2), 2),
    }


class DemoDataProvider(DataSourceAdapter):
    """
    Generates realistic demo data for testing.
    Produces past matches (for brain warmup) and upcoming fixtures.
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self._past_matches: list[RawMatch] = []
        self._upcoming_matches: list[RawMatch] = []
        self._odds_cache: dict[str, dict] = {}
        self._generate_season()

    @property
    def name(self) -> str:
        return "demo"

    def _generate_season(self) -> None:
        """Generate a full season of PL fixtures with results + upcoming."""
        match_id = 1000
        now = datetime.utcnow()
        season_start = now - timedelta(days=180)

        teams = list(PL_TEAMS)
        # Generate round-robin past matches (each team plays each other once at home)
        for i, home in enumerate(teams):
            for j, away in enumerate(teams):
                if i == j:
                    continue

                # Spread over 195 days so ~15 days worth fall after "now"
                match_date = season_start + timedelta(days=random.randint(0, 195))
                hs = TEAM_STRENGTH.get(home, 0.5)
                aws = TEAM_STRENGTH.get(away, 0.5)

                if match_date < now - timedelta(days=2):
                    # Past match - with scores
                    h_score, a_score = _simulate_score(hs, aws)
                    self._past_matches.append(RawMatch(
                        external_id=f"demo_{match_id}",
                        league_code="PL",
                        season="2024",
                        matchday=(match_id - 1000) // 10 + 1,
                        match_date=match_date,
                        status="FINISHED",
                        home_team=home,
                        away_team=away,
                        home_score=h_score,
                        away_score=a_score,
                    ))
                    # Store odds
                    self._odds_cache[f"demo_{match_id}"] = _generate_odds(hs, aws)
                else:
                    # Future match
                    future_date = now + timedelta(days=random.randint(1, 14))
                    self._upcoming_matches.append(RawMatch(
                        external_id=f"demo_{match_id}",
                        league_code="PL",
                        season="2024",
                        matchday=(match_id - 1000) // 10 + 1,
                        match_date=future_date,
                        status="SCHEDULED",
                        home_team=home,
                        away_team=away,
                    ))
                    self._odds_cache[f"demo_{match_id}"] = _generate_odds(hs, aws)

                match_id += 1

        # Sort
        self._past_matches.sort(key=lambda m: m.match_date)
        self._upcoming_matches.sort(key=lambda m: m.match_date)

        # Limit upcoming to ~20 matches
        self._upcoming_matches = self._upcoming_matches[:20]

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        return list(self._past_matches)

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        return list(self._upcoming_matches[:10])

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        stats = {}
        for m in self._past_matches:
            for team, is_home in [(m.home_team, True), (m.away_team, False)]:
                if team not in stats:
                    stats[team] = RawTeamStats(team_name=team, league_code="PL")
                s = stats[team]
                s.played += 1

                if is_home:
                    gf, ga = m.home_score or 0, m.away_score or 0
                else:
                    gf, ga = m.away_score or 0, m.home_score or 0

                s.goals_for += gf
                s.goals_against += ga

                if gf > ga:
                    s.wins += 1
                    if is_home:
                        s.home_wins += 1
                    else:
                        s.away_wins += 1
                elif gf == ga:
                    s.draws += 1
                    if is_home:
                        s.home_draws += 1
                    else:
                        s.away_draws += 1
                else:
                    s.losses += 1
                    if is_home:
                        s.home_losses += 1
                    else:
                        s.away_losses += 1

        return list(stats.values())

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        h2h = [
            m for m in self._past_matches
            if {m.home_team, m.away_team} == {team1_name, team2_name}
        ]
        return h2h[-limit:]

    def get_odds(self, external_id: str) -> Optional[dict]:
        return self._odds_cache.get(external_id)

    async def close(self) -> None:
        pass
