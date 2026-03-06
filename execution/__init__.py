__all__ = ["MatchScheduler", "PredictionManager", "BacktestEngine"]


def __getattr__(name: str):
    if name == "MatchScheduler":
        from .scheduler import MatchScheduler
        return MatchScheduler
    if name == "PredictionManager":
        from .prediction_manager import PredictionManager
        return PredictionManager
    if name == "BacktestEngine":
        from .backtest_engine import BacktestEngine
        return BacktestEngine
    raise AttributeError(name)
