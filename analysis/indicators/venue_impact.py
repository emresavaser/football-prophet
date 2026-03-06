"""Home venue advantage calculation."""

from __future__ import annotations

from brain.memory import ProphetMemory


class VenueImpactCalculator:
    """
    Calculates the home/away impact for each team.
    Some teams have a stronger home advantage than others.
    """

    def __init__(self, memory: ProphetMemory):
        self._memory = memory

    def get_home_advantage(self, team_id: int, league_code: str) -> dict:
        """
        Returns home advantage factor.
        1.0 = neutral, >1.0 = strong home, <1.0 = weak home.
        """
        profile = self._memory.get_team_profile(team_id)
        league_avg = self._memory.get_league_avg(league_code)

        home = profile.home_record
        away = profile.away_record

        # Home vs away points per game comparison
        home_ppg = home.points / home.played if home.played > 0 else 1.0
        away_ppg = away.points / away.played if away.played > 0 else 1.0

        if away_ppg > 0:
            raw_advantage = home_ppg / away_ppg
        elif home_ppg > 0:
            raw_advantage = 1.5
        else:
            raw_advantage = 1.0

        # Compare to league average home win rate
        league_home_factor = league_avg.home_win_pct / (1 - league_avg.home_win_pct) if league_avg.home_win_pct < 1 else 1.5

        # Blend team-specific with league average
        if home.played >= 5:
            advantage = raw_advantage
        elif home.played >= 2:
            blend = home.played / 5.0
            advantage = raw_advantage * blend + league_home_factor * (1 - blend)
        else:
            advantage = league_home_factor

        advantage = max(0.7, min(2.0, advantage))

        return {
            "advantage_factor": round(advantage, 3),
            "home_ppg": round(home_ppg, 2),
            "away_ppg": round(away_ppg, 2),
            "home_scoring_avg": round(home.avg_goals_scored, 2),
            "home_conceding_avg": round(home.avg_goals_conceded, 2),
        }

    def get_venue_adjusted_strength(
        self, home_team_id: int, away_team_id: int, league_code: str
    ) -> dict:
        """Returns venue-adjusted strength for both teams."""
        home_adv = self.get_home_advantage(home_team_id, league_code)
        home_profile = self._memory.get_team_profile(home_team_id)
        away_profile = self._memory.get_team_profile(away_team_id)

        return {
            "home_adjusted_attack": home_profile.attack_strength * home_adv["advantage_factor"],
            "home_adjusted_defense": home_profile.defense_strength / home_adv["advantage_factor"],
            "away_attack": away_profile.attack_strength,
            "away_defense": away_profile.defense_strength,
            "home_advantage_factor": home_adv["advantage_factor"],
        }
