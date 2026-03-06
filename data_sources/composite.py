"""Composite adapter - routes leagues to appropriate data sources."""

from __future__ import annotations

from typing import Optional

from .base import DataSourceAdapter, RawMatch, RawTeamStats


class CompositeAdapter(DataSourceAdapter):
    """Routes API calls to different adapters based on league code."""

    def __init__(
        self,
        default: DataSourceAdapter,
        overrides: dict[str, DataSourceAdapter],
    ):
        self._default = default
        self._overrides = overrides  # league_code -> adapter

    @property
    def name(self) -> str:
        return f"Composite({self._default.name})"

    def _get_adapter(self, league_code: str) -> DataSourceAdapter:
        return self._overrides.get(league_code, self._default)

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        return await self._get_adapter(league_code).fetch_matches(league_code, season, matchday)

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        return await self._get_adapter(league_code).fetch_upcoming_matches(league_code, days_ahead)

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        return await self._get_adapter(league_code).fetch_team_stats(league_code, season)

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        return await self._default.fetch_h2h(team1_name, team2_name, limit)

    async def close(self) -> None:
        await self._default.close()
        for adapter in set(self._overrides.values()):
            await adapter.close()
