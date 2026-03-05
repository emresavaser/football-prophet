"""Configuration dataclasses with environment variable overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class APIKeys:
    football_data_org: str = ""
    api_football: str = ""
    odds_api: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    def __post_init__(self):
        self.football_data_org = os.getenv("FOOTBALL_DATA_API_KEY", self.football_data_org)
        self.api_football = os.getenv("API_FOOTBALL_KEY", self.api_football)
        self.odds_api = os.getenv("ODDS_API_KEY", self.odds_api)
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.telegram_bot_token)
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.telegram_chat_id)


@dataclass
class ModelWeights:
    """Default ensemble model weights (brain can override).

    Tuned from 7-league backtest: ELO consistently top model (0.26-0.31),
    H2H consistently lowest (0.08-0.15), Poisson drops from initial high.
    """
    poisson: float = 0.15
    elo: float = 0.30
    form: float = 0.25
    h2h: float = 0.05
    ml: float = 0.25

    def as_dict(self) -> dict[str, float]:
        return {
            "poisson": self.poisson,
            "elo": self.elo,
            "form": self.form,
            "h2h": self.h2h,
            "ml": self.ml,
        }

    def normalize(self) -> None:
        total = self.poisson + self.elo + self.form + self.h2h + self.ml
        if total > 0:
            self.poisson /= total
            self.elo /= total
            self.form /= total
            self.h2h /= total
            self.ml /= total


@dataclass
class ValueBetCriteria:
    min_edge: float = 0.05          # Minimum %5 edge
    min_confidence: float = 0.55    # Minimum model confidence
    max_odds: float = 10.0          # Maksimum oran
    min_odds: float = 1.30          # Minimum oran
    kelly_fraction: float = 0.25    # Quarter Kelly
    vig_method: str = "shin"        # Vig removal: "shin", "multiplicative", "additive"

    def __post_init__(self):
        self.min_edge = float(os.getenv("VALUE_BET_EDGE_MIN", self.min_edge))
        self.min_confidence = float(os.getenv("PREDICTION_CONFIDENCE_MIN", self.min_confidence))
        self.vig_method = os.getenv("VIG_METHOD", self.vig_method)


@dataclass
class RiskConfig:
    """Risk management parameters."""
    drawdown_soft: float = 0.10         # Soft drawdown threshold (stake reduction begins)
    drawdown_hard: float = 0.25         # Hard drawdown threshold (betting halts)
    max_stake_fraction: float = 0.05    # Max stake as fraction of bankroll
    staking_policy: str = "kelly_quarter"  # flat, kelly_full, kelly_half, kelly_quarter, vol_targeted
    daily_loss_limit: float = 0.10      # Max daily loss as fraction of morning bankroll
    slippage_enabled: bool = False      # Enable slippage simulation in backtest
    bankroll_floor: float = 1.0         # Minimum bankroll below which betting stops

    def __post_init__(self):
        self.drawdown_soft = float(os.getenv("DRAWDOWN_SOFT", self.drawdown_soft))
        self.drawdown_hard = float(os.getenv("DRAWDOWN_HARD", self.drawdown_hard))
        self.max_stake_fraction = float(os.getenv("MAX_STAKE_FRACTION", self.max_stake_fraction))
        self.staking_policy = os.getenv("STAKING_POLICY", self.staking_policy)


@dataclass
class PollingIntervals:
    """Polling intervals in seconds."""
    match_scan: int = 3600          # Her saat maç taraması
    odds_update: int = 900          # 15 dakikada oran güncelleme
    prediction_check: int = 1800    # 30 dakikada tahmin kontrolü
    brain_save: int = 600           # 10 dakikada brain kayıt


@dataclass
class Config:
    """Main configuration for Football Prophet."""
    api_keys: APIKeys = field(default_factory=APIKeys)
    model_weights: ModelWeights = field(default_factory=ModelWeights)
    value_bet: ValueBetCriteria = field(default_factory=ValueBetCriteria)
    risk: RiskConfig = field(default_factory=RiskConfig)
    polling: PollingIntervals = field(default_factory=PollingIntervals)

    # Database
    database_url: str = ""

    # Paths
    base_dir: Path = BASE_DIR
    brain_state_dir: Path = field(default_factory=lambda: BASE_DIR / "brain_state")
    log_dir: Path = field(default_factory=lambda: BASE_DIR / "logs")
    report_dir: Path = field(default_factory=lambda: BASE_DIR / "reports")

    # Leagues to track (codes)
    active_leagues: list[str] = field(default_factory=lambda: [
        "PL", "PD", "SA", "BL1", "FL1", "TSL", "ELC"
    ])

    # General
    log_level: str = "INFO"
    bankroll: float = 1000.0

    # ELO settings
    elo_initial: float = 1500.0
    elo_k_factor: float = 28.0   # Lowered from 32 for more stable ratings

    # Form settings
    form_window: int = 8         # Narrowed from 10 for recent form emphasis
    form_decay: float = 0.88     # Slightly faster decay

    def __post_init__(self):
        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{self.base_dir / 'football_prophet.db'}"
        )
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.bankroll = float(os.getenv("BANKROLL", self.bankroll))
        self.brain_state_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class FreeConfig:
    """Lightweight config for free-tier-only usage."""
    api_keys: APIKeys = field(default_factory=APIKeys)
    database_url: str = ""
    active_leagues: list[str] = field(default_factory=lambda: ["PL", "BL1", "SA"])
    log_level: str = "INFO"

    def __post_init__(self):
        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{BASE_DIR / 'football_prophet.db'}"
        )
