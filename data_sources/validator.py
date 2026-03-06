"""Data validation and cleaning utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .base import RawMatch, RawOdds, RawTeamStats


class DataValidator:
    """Validates and cleans incoming data from various sources."""

    @staticmethod
    def validate_match(match: RawMatch) -> tuple[bool, list[str]]:
        errors = []
        if not match.external_id:
            errors.append("Missing external_id")
        if not match.league_code:
            errors.append("Missing league_code")
        if not match.home_team:
            errors.append("Missing home_team")
        if not match.away_team:
            errors.append("Missing away_team")
        if match.home_team == match.away_team:
            errors.append("Home and away teams are the same")
        if match.status == "FINISHED":
            if match.home_score is None or match.away_score is None:
                errors.append("Finished match missing scores")
            elif match.home_score < 0 or match.away_score < 0:
                errors.append("Negative score values")
        return len(errors) == 0, errors

    @staticmethod
    def validate_odds(odds: RawOdds) -> tuple[bool, list[str]]:
        errors = []
        if not odds.match_external_id:
            errors.append("Missing match_external_id")

        for field_name, value in [
            ("home_win", odds.home_win),
            ("draw", odds.draw),
            ("away_win", odds.away_win),
        ]:
            if value is not None:
                if value < 1.0:
                    errors.append(f"{field_name} odds below 1.0: {value}")
                if value > 100.0:
                    errors.append(f"{field_name} odds suspiciously high: {value}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_team_stats(stats: RawTeamStats) -> tuple[bool, list[str]]:
        errors = []
        if not stats.team_name:
            errors.append("Missing team_name")
        if stats.played < 0:
            errors.append("Negative games played")
        if stats.wins + stats.draws + stats.losses != stats.played and stats.played > 0:
            errors.append("W+D+L does not match played")
        if stats.goals_for < 0 or stats.goals_against < 0:
            errors.append("Negative goals")
        return len(errors) == 0, errors

    @staticmethod
    def deduplicate_matches(matches: list[RawMatch]) -> list[RawMatch]:
        seen = set()
        unique = []
        for m in matches:
            key = m.external_id
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    @staticmethod
    def clean_team_name(name: str) -> str:
        """Normalize team name for matching across sources."""
        replacements = {
            "FC ": "", " FC": "", "CF ": "", " CF": "",
            "AFC ": "", " AFC": "",
            "SSC ": "", " SSC": "",
        }
        cleaned = name.strip()
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        return cleaned.strip()
