"""ProphetMemory - Long-term memory for team profiles, trends, and league averages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WDLRecord:
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def played(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def points(self) -> int:
        return self.wins * 3 + self.draws

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def avg_goals_scored(self) -> float:
        return self.goals_for / self.played if self.played > 0 else 0.0

    @property
    def avg_goals_conceded(self) -> float:
        return self.goals_against / self.played if self.played > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "W": self.wins, "D": self.draws, "L": self.losses,
            "GF": self.goals_for, "GA": self.goals_against,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WDLRecord:
        return cls(
            wins=d.get("W", 0), draws=d.get("D", 0), losses=d.get("L", 0),
            goals_for=d.get("GF", 0), goals_against=d.get("GA", 0),
        )


@dataclass
class TeamProfile:
    team_id: int = 0
    team_name: str = ""
    league_code: str = ""
    elo_rating: float = 1500.0
    attack_strength: float = 1.0
    defense_strength: float = 1.0
    form_score: float = 0.5  # 0.0-1.0
    home_record: WDLRecord = field(default_factory=WDLRecord)
    away_record: WDLRecord = field(default_factory=WDLRecord)
    trend: str = "stable"  # "rising", "stable", "declining"
    last_5_results: list[str] = field(default_factory=list)  # ["W","L","D","W","W"]

    @property
    def total_record(self) -> WDLRecord:
        return WDLRecord(
            wins=self.home_record.wins + self.away_record.wins,
            draws=self.home_record.draws + self.away_record.draws,
            losses=self.home_record.losses + self.away_record.losses,
            goals_for=self.home_record.goals_for + self.away_record.goals_for,
            goals_against=self.home_record.goals_against + self.away_record.goals_against,
        )

    def update_trend(self) -> None:
        if len(self.last_5_results) < 3:
            self.trend = "stable"
            return
        recent = self.last_5_results[-5:]
        points = sum(3 if r == "W" else 1 if r == "D" else 0 for r in recent)
        max_pts = len(recent) * 3
        ratio = points / max_pts if max_pts > 0 else 0.5
        if ratio >= 0.7:
            self.trend = "rising"
        elif ratio <= 0.3:
            self.trend = "declining"
        else:
            self.trend = "stable"

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "league_code": self.league_code,
            "elo_rating": self.elo_rating,
            "attack_strength": self.attack_strength,
            "defense_strength": self.defense_strength,
            "form_score": self.form_score,
            "home_record": self.home_record.to_dict(),
            "away_record": self.away_record.to_dict(),
            "trend": self.trend,
            "last_5_results": self.last_5_results,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TeamProfile:
        return cls(
            team_id=d.get("team_id", 0),
            team_name=d.get("team_name", ""),
            league_code=d.get("league_code", ""),
            elo_rating=d.get("elo_rating", 1500.0),
            attack_strength=d.get("attack_strength", 1.0),
            defense_strength=d.get("defense_strength", 1.0),
            form_score=d.get("form_score", 0.5),
            home_record=WDLRecord.from_dict(d.get("home_record", {})),
            away_record=WDLRecord.from_dict(d.get("away_record", {})),
            trend=d.get("trend", "stable"),
            last_5_results=d.get("last_5_results", []),
        )


@dataclass
class LeagueAverages:
    league_code: str = ""
    avg_goals_per_match: float = 2.5
    home_win_pct: float = 0.45
    draw_pct: float = 0.25
    away_win_pct: float = 0.30
    avg_home_goals: float = 1.5
    avg_away_goals: float = 1.1
    total_matches: int = 0

    def to_dict(self) -> dict:
        return {
            "league_code": self.league_code,
            "avg_goals": self.avg_goals_per_match,
            "home_win_pct": self.home_win_pct,
            "draw_pct": self.draw_pct,
            "away_win_pct": self.away_win_pct,
            "avg_home_goals": self.avg_home_goals,
            "avg_away_goals": self.avg_away_goals,
            "total_matches": self.total_matches,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LeagueAverages:
        return cls(
            league_code=d.get("league_code", ""),
            avg_goals_per_match=d.get("avg_goals", 2.5),
            home_win_pct=d.get("home_win_pct", 0.45),
            draw_pct=d.get("draw_pct", 0.25),
            away_win_pct=d.get("away_win_pct", 0.30),
            avg_home_goals=d.get("avg_home_goals", 1.5),
            avg_away_goals=d.get("avg_away_goals", 1.1),
            total_matches=d.get("total_matches", 0),
        )


@dataclass
class H2HProfile:
    team1_id: int = 0
    team2_id: int = 0
    total_matches: int = 0
    team1_wins: int = 0
    team2_wins: int = 0
    draws: int = 0
    avg_total_goals: float = 2.5
    last_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "team1_id": self.team1_id,
            "team2_id": self.team2_id,
            "total": self.total_matches,
            "t1_wins": self.team1_wins,
            "t2_wins": self.team2_wins,
            "draws": self.draws,
            "avg_goals": self.avg_total_goals,
            "last_results": self.last_results,
        }

    @classmethod
    def from_dict(cls, d: dict) -> H2HProfile:
        return cls(
            team1_id=d.get("team1_id", 0),
            team2_id=d.get("team2_id", 0),
            total_matches=d.get("total", 0),
            team1_wins=d.get("t1_wins", 0),
            team2_wins=d.get("t2_wins", 0),
            draws=d.get("draws", 0),
            avg_total_goals=d.get("avg_goals", 2.5),
            last_results=d.get("last_results", []),
        )


class ProphetMemory:
    """
    Long-term memory storing team profiles, league averages, and H2H data.
    Updated after every match result.
    """

    def __init__(self):
        self.team_profiles: dict[int, TeamProfile] = {}
        self.league_averages: dict[str, LeagueAverages] = {}
        self.h2h_cache: dict[str, H2HProfile] = {}  # key: "id1:id2" (sorted)
        self.season_stats: dict[str, dict] = {}

    def get_team_profile(self, team_id: int) -> TeamProfile:
        if team_id not in self.team_profiles:
            self.team_profiles[team_id] = TeamProfile(team_id=team_id)
        return self.team_profiles[team_id]

    def get_league_avg(self, league_code: str) -> LeagueAverages:
        if league_code not in self.league_averages:
            self.league_averages[league_code] = LeagueAverages(league_code=league_code)
        return self.league_averages[league_code]

    def get_h2h(self, team1_id: int, team2_id: int) -> H2HProfile:
        key = self._h2h_key(team1_id, team2_id)
        if key not in self.h2h_cache:
            self.h2h_cache[key] = H2HProfile(team1_id=min(team1_id, team2_id),
                                               team2_id=max(team1_id, team2_id))
        return self.h2h_cache[key]

    def update_after_match(
        self,
        home_team_id: int,
        away_team_id: int,
        home_score: int,
        away_score: int,
        league_code: str,
    ) -> None:
        """Update memory after a match result."""
        # Determine result
        if home_score > away_score:
            home_result, away_result = "W", "L"
        elif home_score < away_score:
            home_result, away_result = "L", "W"
        else:
            home_result, away_result = "D", "D"

        # Update home team
        hp = self.get_team_profile(home_team_id)
        hp.home_record.goals_for += home_score
        hp.home_record.goals_against += away_score
        if home_result == "W":
            hp.home_record.wins += 1
        elif home_result == "D":
            hp.home_record.draws += 1
        else:
            hp.home_record.losses += 1
        hp.last_5_results.append(home_result)
        hp.last_5_results = hp.last_5_results[-5:]
        hp.update_trend()

        # Update away team
        ap = self.get_team_profile(away_team_id)
        ap.away_record.goals_for += away_score
        ap.away_record.goals_against += home_score
        if away_result == "W":
            ap.away_record.wins += 1
        elif away_result == "D":
            ap.away_record.draws += 1
        else:
            ap.away_record.losses += 1
        ap.last_5_results.append(away_result)
        ap.last_5_results = ap.last_5_results[-5:]
        ap.update_trend()

        # Update H2H
        h2h = self.get_h2h(home_team_id, away_team_id)
        h2h.total_matches += 1
        if home_result == "W":
            if home_team_id == h2h.team1_id:
                h2h.team1_wins += 1
            else:
                h2h.team2_wins += 1
        elif home_result == "L":
            if away_team_id == h2h.team1_id:
                h2h.team1_wins += 1
            else:
                h2h.team2_wins += 1
        else:
            h2h.draws += 1
        total_goals = home_score + away_score
        if h2h.total_matches > 1:
            old_avg = h2h.avg_total_goals
            h2h.avg_total_goals = old_avg + (total_goals - old_avg) / h2h.total_matches
        else:
            h2h.avg_total_goals = float(total_goals)
        h2h.last_results.append({"home": home_score, "away": away_score})
        h2h.last_results = h2h.last_results[-10:]

        # Update league averages
        la = self.get_league_avg(league_code)
        la.total_matches += 1
        n = la.total_matches
        la.avg_goals_per_match += (total_goals - la.avg_goals_per_match) / n
        la.avg_home_goals += (home_score - la.avg_home_goals) / n
        la.avg_away_goals += (away_score - la.avg_away_goals) / n
        # Update win percentages (running)
        is_home_win = 1.0 if home_result == "W" else 0.0
        is_draw = 1.0 if home_result == "D" else 0.0
        is_away_win = 1.0 if away_result == "W" else 0.0
        la.home_win_pct += (is_home_win - la.home_win_pct) / n
        la.draw_pct += (is_draw - la.draw_pct) / n
        la.away_win_pct += (is_away_win - la.away_win_pct) / n

    @staticmethod
    def _h2h_key(t1: int, t2: int) -> str:
        return f"{min(t1, t2)}:{max(t1, t2)}"

    def to_dict(self) -> dict:
        return {
            "team_profiles": {str(k): v.to_dict() for k, v in self.team_profiles.items()},
            "league_averages": {k: v.to_dict() for k, v in self.league_averages.items()},
            "h2h_cache": {k: v.to_dict() for k, v in self.h2h_cache.items()},
            "season_stats": self.season_stats,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProphetMemory:
        mem = cls()
        for k, v in d.get("team_profiles", {}).items():
            mem.team_profiles[int(k)] = TeamProfile.from_dict(v)
        for k, v in d.get("league_averages", {}).items():
            mem.league_averages[k] = LeagueAverages.from_dict(v)
        for k, v in d.get("h2h_cache", {}).items():
            mem.h2h_cache[k] = H2HProfile.from_dict(v)
        mem.season_stats = d.get("season_stats", {})
        return mem
