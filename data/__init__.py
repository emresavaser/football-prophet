__all__ = [
    "DatabaseManager",
    "MatchDataOracle",
    "Base",
    "Team",
    "Match",
    "Odds",
    "Prediction",
    "BacktestResult",
    "ValueBet",
]


def __getattr__(name: str):
    if name == "DatabaseManager":
        from .database import DatabaseManager
        return DatabaseManager
    if name == "MatchDataOracle":
        from .cache import MatchDataOracle
        return MatchDataOracle
    if name in {"Base", "Team", "Match", "Odds", "Prediction", "BacktestResult", "ValueBet"}:
        from .models import Base, Team, Match, Odds, Prediction, BacktestResult, ValueBet
        return {
            "Base": Base,
            "Team": Team,
            "Match": Match,
            "Odds": Odds,
            "Prediction": Prediction,
            "BacktestResult": BacktestResult,
            "ValueBet": ValueBet,
        }[name]
    raise AttributeError(name)
