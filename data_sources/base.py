"""Abstract base class for data source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawMatch:
    """Normalized match data from any source."""
    external_id: str
    league_code: str
    season: str
    matchday: Optional[int] = None
    match_date: datetime = field(default_factory=datetime.utcnow)
    status: str = "SCHEDULED"
    home_team: str = ""
    away_team: str = ""
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_ht_score: Optional[int] = None
    away_ht_score: Optional[int] = None


@dataclass
class RawTeamStats:
    """Normalized team statistics."""
    team_name: str
    league_code: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0


@dataclass
class RawOdds:
    """Normalized odds data."""
    match_external_id: str
    bookmaker: str = "average"
    home_win: Optional[float] = None
    draw: Optional[float] = None
    away_win: Optional[float] = None
    over_25: Optional[float] = None
    under_25: Optional[float] = None
    btts_yes: Optional[float] = None
    btts_no: Optional[float] = None


class DataSourceAdapter(ABC):
    """Abstract adapter interface for football data sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        ...

    @abstractmethod
    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        ...

    @abstractmethod
    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        ...

    @abstractmethod
    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        ...

    async def close(self) -> None:
        """Cleanup resources."""
        pass
