"""Flashscore web scraper for match data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import DataSourceAdapter, RawMatch, RawTeamStats

FLASHSCORE_BASE = "https://www.flashscore.com"


class FlashscoreScraper(DataSourceAdapter):
    """Web scraper for Flashscore (backup data source)."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            timeout=30.0,
            follow_redirects=True,
        )

    @property
    def name(self) -> str:
        return "Flashscore"

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        # Flashscore uses JS-rendered pages; basic scraping has limited data
        # This is a fallback / supplementary source
        return []

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        return []

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        return []

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        return []

    async def close(self) -> None:
        await self._client.aclose()
