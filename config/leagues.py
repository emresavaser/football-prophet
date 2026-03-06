"""League definitions and ID mappings across data sources."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeagueInfo:
    code: str               # Internal short code
    name: str               # Display name
    country: str
    fd_code: str            # football-data.org competition code
    api_football_id: int    # API-Football league ID
    flashscore_slug: str    # Flashscore URL slug
    thesportsdb_id: int = 0 # TheSportsDB league ID
    season_start_month: int = 8  # Typical season start month


LEAGUES: dict[str, LeagueInfo] = {
    "PL": LeagueInfo(
        code="PL",
        name="Premier League",
        country="England",
        fd_code="PL",
        api_football_id=39,
        flashscore_slug="england/premier-league",
        thesportsdb_id=4328,
    ),
    "PD": LeagueInfo(
        code="PD",
        name="La Liga",
        country="Spain",
        fd_code="PD",
        api_football_id=140,
        flashscore_slug="spain/laliga",
        thesportsdb_id=4335,
    ),
    "SA": LeagueInfo(
        code="SA",
        name="Serie A",
        country="Italy",
        fd_code="SA",
        api_football_id=135,
        flashscore_slug="italy/serie-a",
        thesportsdb_id=4332,
    ),
    "BL1": LeagueInfo(
        code="BL1",
        name="Bundesliga",
        country="Germany",
        fd_code="BL1",
        api_football_id=78,
        flashscore_slug="germany/bundesliga",
        thesportsdb_id=4331,
    ),
    "FL1": LeagueInfo(
        code="FL1",
        name="Ligue 1",
        country="France",
        fd_code="FL1",
        api_football_id=61,
        flashscore_slug="france/ligue-1",
        thesportsdb_id=4334,
    ),
    "TSL": LeagueInfo(
        code="TSL",
        name="Süper Lig",
        country="Turkey",
        fd_code="TSL",
        api_football_id=203,
        flashscore_slug="turkey/super-lig",
        thesportsdb_id=4339,
    ),
    "ELC": LeagueInfo(
        code="ELC",
        name="Championship",
        country="England",
        fd_code="ELC",
        api_football_id=40,
        flashscore_slug="england/championship",
        thesportsdb_id=4329,
    ),
}


def get_league(code: str) -> LeagueInfo | None:
    return LEAGUES.get(code.upper())


def get_all_league_codes() -> list[str]:
    return list(LEAGUES.keys())
