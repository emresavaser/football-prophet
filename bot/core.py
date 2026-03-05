"""FootballProphet - Main orchestrator class."""

from __future__ import annotations

from typing import Optional

from config.settings import Config
from brain.state import ProphetState
from brain.memory import ProphetMemory
from brain.learning import AdaptiveLearner
from brain.persistence import BrainPersistence
from data.database import DatabaseManager
from data.cache import MatchDataOracle
from data_sources.football_data_org import FootballDataOrgAdapter
from data_sources.api_football import APIFootballAdapter
from data_sources.thesportsdb import TheSportsDBAdapter
from data_sources.composite import CompositeAdapter
from data_sources.odds_provider import OddsProvider
from data_sources.base import DataSourceAdapter
from analysis.ensemble import EnsemblePredictor
from analysis.indicators.team_strength import TeamStrengthCalculator
from odds.value_finder import ValueFinder
from execution.scheduler import MatchScheduler
from execution.prediction_manager import PredictionManager
from execution.backtest_engine import BacktestEngine
from notifications.telegram import TelegramNotifier
from utils.logging import setup_logging, get_logger

log = get_logger(__name__)


class FootballProphet:
    """
    Main bot class - wires up all services.
    Similar to eclipse_scalper pattern: brain + data + analysis + execution.
    """

    def __init__(self, config: Config):
        self.config = config

        # Brain components
        self.state = ProphetState()
        self.memory = ProphetMemory()
        self.learner = AdaptiveLearner(initial_weights=config.model_weights.as_dict())
        self.persistence = BrainPersistence(config.brain_state_dir)

        # Data layer
        self.db = DatabaseManager(config.database_url)
        self.cache = MatchDataOracle(
            cache_dir=config.brain_state_dir / "cache",
            max_age_seconds=config.polling.match_scan,
        )

        # Data sources
        self.data_source: Optional[DataSourceAdapter] = None
        self.odds_provider: Optional[OddsProvider] = None
        self._init_data_sources()

        # Analysis
        self.ensemble = EnsemblePredictor(
            memory=self.memory,
            learner=self.learner,
            k_factor=config.elo_k_factor,
            form_window=config.form_window,
            form_decay=config.form_decay,
        )
        self.strength_calc = TeamStrengthCalculator(self.memory)

        # Value bet finder (with vig method)
        self.value_finder = ValueFinder(
            min_edge=config.value_bet.min_edge,
            min_confidence=config.value_bet.min_confidence,
            min_odds=config.value_bet.min_odds,
            max_odds=config.value_bet.max_odds,
            kelly_fraction=config.value_bet.kelly_fraction,
            vig_method=config.value_bet.vig_method,
        )

        # Execution
        self.scheduler: Optional[MatchScheduler] = None
        self.prediction_manager: Optional[PredictionManager] = None
        self.backtest_engine: Optional[BacktestEngine] = None

        # Notifications
        self.notifier: Optional[TelegramNotifier] = None

    def _init_data_sources(self) -> None:
        keys = self.config.api_keys
        primary: DataSourceAdapter | None = None

        if keys.football_data_org:
            primary = FootballDataOrgAdapter(keys.football_data_org)
        elif keys.api_football:
            primary = APIFootballAdapter(keys.api_football)

        if primary:
            # TSL is not available on football-data.org free tier,
            # use TheSportsDB as fallback for TSL
            tsdb = TheSportsDBAdapter()
            self.data_source = CompositeAdapter(
                default=primary,
                overrides={"TSL": tsdb},
            )
        else:
            self.data_source = None

        if keys.odds_api:
            self.odds_provider = OddsProvider(keys.odds_api)

    async def initialize(self) -> None:
        """Initialize all async components."""
        log.info("initializing", version="1.0.0")

        # Setup logging
        setup_logging(
            level=self.config.log_level,
            log_dir=self.config.log_dir,
        )

        # Init database
        await self.db.init_db()
        log.info("database_ready")

        # Load brain state
        loaded = self.persistence.load()
        if loaded:
            self.state, self.memory, self.learner = loaded
            self.ensemble = EnsemblePredictor(
                memory=self.memory,
                learner=self.learner,
                k_factor=self.config.elo_k_factor,
                form_window=self.config.form_window,
                form_decay=self.config.form_decay,
            )
            log.info("brain_loaded", teams=len(self.memory.team_profiles))
        else:
            log.info("brain_fresh_start")

        # Load cache
        self.cache.load_from_disk()

        # Init execution components
        if self.data_source:
            self.scheduler = MatchScheduler(
                db=self.db,
                data_source=self.data_source,
                active_leagues=self.config.active_leagues,
                scan_interval=self.config.polling.match_scan,
            )

        self.prediction_manager = PredictionManager(
            db=self.db,
            ensemble=self.ensemble,
            memory=self.memory,
            state=self.state,
            value_finder=self.value_finder,
        )

        self.backtest_engine = BacktestEngine(
            db=self.db,
            memory=self.memory,
            min_edge=self.config.value_bet.min_edge,
            kelly_fraction=self.config.value_bet.kelly_fraction,
            bankroll=self.config.bankroll,
            vig_method=self.config.value_bet.vig_method,
            drawdown_soft=self.config.risk.drawdown_soft,
            drawdown_hard=self.config.risk.drawdown_hard,
            max_stake_fraction=self.config.risk.max_stake_fraction,
            staking_policy=self.config.risk.staking_policy,
            bankroll_floor=self.config.risk.bankroll_floor,
            slippage_enabled=self.config.risk.slippage_enabled,
        )

        # Init Telegram
        keys = self.config.api_keys
        if keys.telegram_bot_token and keys.telegram_chat_id:
            self.notifier = TelegramNotifier(
                bot_token=keys.telegram_bot_token,
                chat_id=keys.telegram_chat_id,
            )

        log.info("initialization_complete")

    async def save_state(self) -> None:
        """Save brain state and cache to disk."""
        self.persistence.save(self.state, self.memory, self.learner)
        self.cache.save_to_disk()
        log.debug("state_saved")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        log.info("shutting_down")
        await self.save_state()

        if self.data_source:
            await self.data_source.close()
        if self.odds_provider:
            await self.odds_provider.close()
        await self.db.close()

        log.info("shutdown_complete")
