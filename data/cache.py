"""In-memory cache with staleness tracking and LZ4 disk persistence."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import lz4.frame


class MatchDataOracle:
    """
    In-memory data cache with disk persistence (LZ4 compressed).
    Tracks data freshness and provides fast lookups for hot data.
    """

    def __init__(self, cache_dir: Optional[Path] = None, max_age_seconds: int = 3600):
        self._store: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}
        self._max_age = max_age_seconds
        self._cache_dir = cache_dir
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        if self.is_stale(key):
            return None
        return self._store[key]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._timestamps[key] = time.time()

    def is_stale(self, key: str) -> bool:
        ts = self._timestamps.get(key)
        if ts is None:
            return True
        return (time.time() - ts) > self._max_age

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
        self._timestamps.clear()

    @property
    def stats(self) -> dict:
        total = len(self._store)
        stale = sum(1 for k in self._store if self.is_stale(k))
        return {
            "total_entries": total,
            "fresh_entries": total - stale,
            "stale_entries": stale,
        }

    # ── Convenience methods for common data ────────────────────

    def cache_team_matches(self, team_id: int, matches: list) -> None:
        self.set(f"team_matches:{team_id}", matches)

    def get_team_matches(self, team_id: int) -> Optional[list]:
        return self.get(f"team_matches:{team_id}")

    def cache_h2h(self, team1_id: int, team2_id: int, data: list) -> None:
        key = f"h2h:{min(team1_id, team2_id)}:{max(team1_id, team2_id)}"
        self.set(key, data)

    def get_h2h(self, team1_id: int, team2_id: int) -> Optional[list]:
        key = f"h2h:{min(team1_id, team2_id)}:{max(team1_id, team2_id)}"
        return self.get(key)

    def cache_league_standings(self, league_code: str, standings: dict) -> None:
        self.set(f"standings:{league_code}", standings)

    def get_league_standings(self, league_code: str) -> Optional[dict]:
        return self.get(f"standings:{league_code}")

    def cache_odds(self, match_id: int | str, odds: dict) -> None:
        self.set(f"odds:{match_id}", odds)

    def get_odds(self, match_id: int | str) -> Optional[dict]:
        return self.get(f"odds:{match_id}")

    # ── Disk persistence (LZ4) ─────────────────────────────────

    def save_to_disk(self, filename: str = "cache_state.lz4") -> None:
        if not self._cache_dir:
            return
        filepath = self._cache_dir / filename
        payload = {
            "store": _serialize(self._store),
            "timestamps": self._timestamps,
        }
        data = json.dumps(payload, default=str).encode("utf-8")
        compressed = lz4.frame.compress(data)
        filepath.write_bytes(compressed)

    def load_from_disk(self, filename: str = "cache_state.lz4") -> bool:
        if not self._cache_dir:
            return False
        filepath = self._cache_dir / filename
        if not filepath.exists():
            return False
        try:
            compressed = filepath.read_bytes()
            data = lz4.frame.decompress(compressed)
            payload = json.loads(data.decode("utf-8"))
            self._store = payload.get("store", {})
            self._timestamps = {k: float(v) for k, v in payload.get("timestamps", {}).items()}
            return True
        except Exception:
            return False


def _serialize(obj: Any) -> Any:
    """Make objects JSON-serializable."""
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj
