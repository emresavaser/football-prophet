"""Historical data collector using TheSportsDB."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from config.leagues import LEAGUES, get_league, get_all_league_codes
from data_sources.thesportsdb import TheSportsDBAdapter
from cli.formatter import console

if TYPE_CHECKING:
    from data.database import DatabaseManager

DEFAULT_SEASONS = ["2023-2024", "2024-2025", "2025-2026"]


class HistoricalDataCollector:
    """Collects historical match data from TheSportsDB into the local DB."""

    def __init__(
        self,
        db: "DatabaseManager",
        adapter: Optional[TheSportsDBAdapter] = None,
    ):
        self.db = db
        self.adapter = adapter or TheSportsDBAdapter()
        self._owns_adapter = adapter is None

    async def collect(
        self,
        league_codes: list[str],
        seasons: Optional[list[str]] = None,
    ) -> dict:
        """Collect historical data for given leagues and seasons.

        Returns summary dict with total/new/finished counts.
        """
        seasons = seasons or DEFAULT_SEASONS
        summary = {
            "total_fetched": 0,
            "total_new": 0,
            "total_finished": 0,
            "leagues": {},
        }

        for lc in league_codes:
            league = get_league(lc)
            if not league:
                console.print(f"[yellow]Unknown league: {lc}, skipping[/]")
                continue
            if not league.thesportsdb_id:
                console.print(f"[yellow]{lc} has no TheSportsDB ID, skipping[/]")
                continue

            league_summary = {"seasons": {}, "total": 0, "new": 0, "finished": 0}

            for season in seasons:
                console.print(f"[cyan]Fetching {lc} {season}...[/]", end=" ")

                try:
                    matches = await self.adapter.fetch_season_matches(lc, season)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/]")
                    continue

                finished = [m for m in matches if m.status == "FINISHED" and m.home_score is not None]
                new_count = 0

                for rm in matches:
                    home_team = await self.db.upsert_team(name=rm.home_team, league_code=lc)
                    away_team = await self.db.upsert_team(name=rm.away_team, league_code=lc)
                    existing = await self.db.get_match_by_external_id(rm.external_id)

                    match = await self.db.upsert_match(
                        external_id=rm.external_id,
                        league_code=lc,
                        season=rm.season,
                        matchday=rm.matchday,
                        match_date=rm.match_date,
                        status=rm.status,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        home_score=rm.home_score,
                        away_score=rm.away_score,
                    )
                    if existing is None:
                        new_count += 1

                console.print(
                    f"[green]{len(matches)} mac cekildi, "
                    f"{len(finished)} bitmis[/]"
                )

                league_summary["seasons"][season] = {
                    "fetched": len(matches),
                    "finished": len(finished),
                }
                league_summary["total"] += len(matches)
                league_summary["new"] += new_count
                league_summary["finished"] += len(finished)

            summary["leagues"][lc] = league_summary
            summary["total_fetched"] += league_summary["total"]
            summary["total_new"] += league_summary["new"]
            summary["total_finished"] += league_summary["finished"]

        console.print(
            f"\n[bold green]Toplam: {summary['total_fetched']} mac cekildi, "
            f"{summary['total_finished']} bitmis mac DB'ye yazildi[/]"
        )

        return summary

    async def close(self) -> None:
        if self._owns_adapter:
            await self.adapter.close()
