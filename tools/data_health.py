"""Data source health check and data quality diagnostics."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from config.settings import Config
from data.database import DatabaseManager
from data.cache import MatchDataOracle
from data_sources.football_data_org import FootballDataOrgAdapter
from data_sources.api_football import APIFootballAdapter
from data_sources.odds_provider import OddsProvider
from brain.persistence import BrainPersistence

console = Console()


async def check_data_health():
    config = Config()

    console.print("[bold cyan]Football Prophet - Data Health Check[/]\n")

    # Database check
    table = Table(title="Data Sources", show_header=True, header_style="bold")
    table.add_column("Source", min_width=20)
    table.add_column("Status")
    table.add_column("Details")

    # DB
    try:
        db = DatabaseManager(config.database_url)
        await db.init_db()
        accuracy = await db.get_model_accuracy(days=30)
        table.add_row("Database", "[green]OK[/]", f"predictions={accuracy['total']}")
        await db.close()
    except Exception as e:
        table.add_row("Database", "[red]ERROR[/]", str(e)[:50])

    # football-data.org
    if config.api_keys.football_data_org:
        try:
            adapter = FootballDataOrgAdapter(config.api_keys.football_data_org)
            matches = await adapter.fetch_upcoming_matches("PL", days_ahead=7)
            table.add_row("football-data.org", "[green]OK[/]", f"PL upcoming={len(matches)}")
            await adapter.close()
        except Exception as e:
            table.add_row("football-data.org", "[red]ERROR[/]", str(e)[:50])
    else:
        table.add_row("football-data.org", "[yellow]NOT CONFIGURED[/]", "Set FOOTBALL_DATA_API_KEY")

    # API-Football
    if config.api_keys.api_football:
        try:
            adapter = APIFootballAdapter(config.api_keys.api_football)
            matches = await adapter.fetch_upcoming_matches("PL", days_ahead=7)
            table.add_row("API-Football", "[green]OK[/]", f"PL upcoming={len(matches)}")
            await adapter.close()
        except Exception as e:
            table.add_row("API-Football", "[red]ERROR[/]", str(e)[:50])
    else:
        table.add_row("API-Football", "[yellow]NOT CONFIGURED[/]", "Set API_FOOTBALL_KEY")

    # Odds API
    if config.api_keys.odds_api:
        try:
            provider = OddsProvider(config.api_keys.odds_api)
            odds = await provider.fetch_odds("PL")
            table.add_row("Odds API", "[green]OK[/]", f"PL events={len(odds)}")
            await provider.close()
        except Exception as e:
            table.add_row("Odds API", "[red]ERROR[/]", str(e)[:50])
    else:
        table.add_row("Odds API", "[yellow]NOT CONFIGURED[/]", "Set ODDS_API_KEY")

    console.print(table)

    # Brain state
    console.print("\n[bold]Brain State:[/]")
    persistence = BrainPersistence(config.brain_state_dir)
    info = persistence.get_state_info()
    if info["exists"]:
        console.print(f"  Size: {info['size_bytes'] / 1024:.1f} KB")
        console.print(f"  Backups: {info['backups']}")
    else:
        console.print("  [yellow]No saved state[/]")

    # Cache
    console.print("\n[bold]Cache:[/]")
    cache = MatchDataOracle(cache_dir=config.brain_state_dir / "cache")
    cache.load_from_disk()
    stats = cache.stats
    console.print(f"  Entries: {stats['total_entries']} (fresh={stats['fresh_entries']}, stale={stats['stale_entries']})")


if __name__ == "__main__":
    asyncio.run(check_data_health())
