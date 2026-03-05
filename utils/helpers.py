"""General helper utilities."""

from __future__ import annotations

import time
from datetime import datetime


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Safe division avoiding ZeroDivisionError."""
    return a / b if b != 0 else default


def timestamp_now() -> float:
    """Current UNIX timestamp."""
    return time.time()


def format_odds(decimal_odds: float) -> str:
    """Format decimal odds for display."""
    if decimal_odds is None:
        return "-"
    return f"{decimal_odds:.2f}"


def format_probability(prob: float) -> str:
    """Format probability as percentage."""
    return f"{prob:.1%}"


def format_ev(ev: float) -> str:
    """Format expected value."""
    sign = "+" if ev > 0 else ""
    return f"{sign}{ev:.3f}"


def result_emoji(result: str) -> str:
    """Convert result to display character."""
    return {"W": "W", "D": "D", "L": "L"}.get(result, "?")


def match_result_str(home_score: int, away_score: int) -> str:
    """Return result string from scores."""
    if home_score > away_score:
        return "HOME"
    elif home_score < away_score:
        return "AWAY"
    return "DRAW"


def seconds_to_human(seconds: float) -> str:
    """Convert seconds to human readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"
