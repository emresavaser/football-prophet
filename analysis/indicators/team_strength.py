"""Team attack and defense strength metrics."""

from __future__ import annotations

from brain.memory import ProphetMemory


class TeamStrengthCalculator:
    """
    Calculates team attack/defense strength relative to league average.

    attack_strength = team_goals_scored / league_avg_goals_scored
    defense_strength = team_goals_conceded / league_avg_goals_conceded

    Higher attack = better offense, Higher defense = weaker defense.
    """

    def __init__(self, memory: ProphetMemory):
        self._memory = memory

    def update_all(self, league_code: str) -> None:
        """Recalculate attack/defense strength for all teams in a league."""
        league_avg = self._memory.get_league_avg(league_code)

        if league_avg.total_matches == 0:
            return

        avg_home_scored = league_avg.avg_home_goals
        avg_away_scored = league_avg.avg_away_goals

        for team_id, profile in self._memory.team_profiles.items():
            if profile.league_code != league_code:
                continue

            total = profile.total_record
            if total.played == 0:
                continue

            # Attack strength: how many goals team scores relative to average
            team_avg_scored = total.avg_goals_scored
            avg_scored = (avg_home_scored + avg_away_scored) / 2
            if avg_scored > 0:
                profile.attack_strength = team_avg_scored / avg_scored
            else:
                profile.attack_strength = 1.0

            # Defense strength: how many goals team concedes relative to average
            team_avg_conceded = total.avg_goals_conceded
            avg_conceded = (avg_home_scored + avg_away_scored) / 2  # Symmetric
            if avg_conceded > 0:
                profile.defense_strength = team_avg_conceded / avg_conceded
            else:
                profile.defense_strength = 1.0

            # Clamp to reasonable range
            profile.attack_strength = max(0.3, min(3.0, profile.attack_strength))
            profile.defense_strength = max(0.3, min(3.0, profile.defense_strength))

    def get_team_strength(self, team_id: int) -> dict:
        profile = self._memory.get_team_profile(team_id)
        return {
            "attack": round(profile.attack_strength, 3),
            "defense": round(profile.defense_strength, 3),
            "overall": round(profile.attack_strength / profile.defense_strength, 3),
        }
