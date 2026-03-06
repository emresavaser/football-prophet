"""LZ4-compressed brain state persistence (eclipse_scalper pattern)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import lz4.frame

from .state import ProphetState
from .memory import ProphetMemory
from .learning import AdaptiveLearner


class BrainPersistence:
    """
    Save/load brain components with LZ4 compression.
    Maintains versioned snapshots for recovery.
    """

    def __init__(self, state_dir: Path):
        self._dir = state_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        state: ProphetState,
        memory: ProphetMemory,
        learner: AdaptiveLearner,
    ) -> str:
        """Save all brain components. Returns the filepath."""
        payload = {
            "version": 1,
            "saved_at": time.time(),
            "state": state.to_dict(),
            "memory": memory.to_dict(),
            "learner": learner.to_dict(),
        }
        data = json.dumps(payload, default=str).encode("utf-8")
        compressed = lz4.frame.compress(data)

        # Save current state
        filepath = self._dir / "brain_state.lz4"
        filepath.write_bytes(compressed)

        # Keep a timestamped backup (last 5)
        backup = self._dir / f"brain_state_{int(time.time())}.lz4"
        backup.write_bytes(compressed)
        self._cleanup_backups()

        state.last_save_ts = time.time()
        return str(filepath)

    def load(self) -> Optional[tuple[ProphetState, ProphetMemory, AdaptiveLearner]]:
        """Load brain from disk. Returns None if no state exists."""
        filepath = self._dir / "brain_state.lz4"
        if not filepath.exists():
            return None

        try:
            compressed = filepath.read_bytes()
            data = lz4.frame.decompress(compressed)
            payload = json.loads(data.decode("utf-8"))

            state = ProphetState.from_dict(payload.get("state", {}))
            memory = ProphetMemory.from_dict(payload.get("memory", {}))
            learner = AdaptiveLearner.from_dict(payload.get("learner", {}))

            return state, memory, learner
        except Exception as e:
            # Try loading from latest backup
            return self._load_from_backup()

    def _load_from_backup(self) -> Optional[tuple[ProphetState, ProphetMemory, AdaptiveLearner]]:
        backups = sorted(self._dir.glob("brain_state_*.lz4"), reverse=True)
        for backup in backups:
            try:
                compressed = backup.read_bytes()
                data = lz4.frame.decompress(compressed)
                payload = json.loads(data.decode("utf-8"))

                state = ProphetState.from_dict(payload.get("state", {}))
                memory = ProphetMemory.from_dict(payload.get("memory", {}))
                learner = AdaptiveLearner.from_dict(payload.get("learner", {}))

                return state, memory, learner
            except Exception:
                continue
        return None

    def _cleanup_backups(self, keep: int = 5) -> None:
        backups = sorted(self._dir.glob("brain_state_*.lz4"), reverse=True)
        for old_backup in backups[keep:]:
            old_backup.unlink(missing_ok=True)

    def state_exists(self) -> bool:
        return (self._dir / "brain_state.lz4").exists()

    def get_state_info(self) -> dict:
        filepath = self._dir / "brain_state.lz4"
        if not filepath.exists():
            return {"exists": False}
        stat = filepath.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "backups": len(list(self._dir.glob("brain_state_*.lz4"))),
        }
