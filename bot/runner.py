"""Async runner with polling loops and signal handling."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

from .core import FootballProphet
from config.settings import Config
from utils.logging import get_logger

log = get_logger(__name__)


class Runner:
    """
    Async daemon runner for Football Prophet.
    Manages polling loops: match scan, odds update, prediction check, brain save.
    """

    def __init__(self, prophet: FootballProphet):
        self._prophet = prophet
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the daemon with all polling loops."""
        self._running = True
        p = self._prophet

        log.info("runner_starting", leagues=p.config.active_leagues)

        # Setup signal handlers
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Launch polling loops
        polling = p.config.polling

        if p.scheduler:
            self._tasks.append(
                asyncio.create_task(self._poll_loop("match_scan", self._scan_matches, polling.match_scan))
            )
            self._tasks.append(
                asyncio.create_task(self._poll_loop("prediction_check", self._check_predictions, polling.prediction_check))
            )

        if p.odds_provider:
            self._tasks.append(
                asyncio.create_task(self._poll_loop("odds_update", self._update_odds, polling.odds_update))
            )

        self._tasks.append(
            asyncio.create_task(self._poll_loop("brain_save", self._save_brain, polling.brain_save))
        )

        log.info("runner_started", loops=len(self._tasks))

        # Wait for all tasks
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Gracefully stop the runner."""
        log.info("runner_stopping")
        self._running = False
        for task in self._tasks:
            task.cancel()
        await self._prophet.shutdown()
        log.info("runner_stopped")

    async def _poll_loop(self, name: str, func, interval: int) -> None:
        """Generic polling loop with error resilience."""
        while self._running:
            try:
                await func()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("poll_error", loop=name, error=str(e))
            await asyncio.sleep(interval)

    async def _scan_matches(self) -> None:
        """Scan for upcoming matches and generate predictions."""
        p = self._prophet
        if not p.scheduler or not p.prediction_manager:
            return

        # Scan upcoming matches
        upcoming = await p.scheduler.scan_upcoming(days_ahead=7)
        p.state.scan_stats.record_scan(matches=len(upcoming))

        # Generate predictions for new matches
        for match_info in upcoming:
            match_id = match_info["match_id"]
            if match_id in p.state.active_predictions:
                continue  # Already predicted

            # Get odds if available
            odds_dict = {}
            if p.odds_provider:
                cached = p.cache.get_odds(match_id)
                if cached:
                    odds_dict = cached

            prediction, value_bets = await p.prediction_manager.predict_match(
                match_id=match_id,
                home_team_id=match_info["home_team_id"],
                away_team_id=match_info["away_team_id"],
                league_code=match_info["league_code"],
                odds=odds_dict,
                home_team_name=match_info["home_team"],
                away_team_name=match_info["away_team"],
            )

            # Notify value bets
            if value_bets and p.notifier:
                for vb in value_bets:
                    await p.notifier.send_value_bet_alert(
                        home_team=match_info["home_team"],
                        away_team=match_info["away_team"],
                        market=vb.market,
                        odds=vb.odds,
                        edge=vb.edge,
                        ev=vb.ev,
                        kelly=vb.kelly_stake,
                        confidence=vb.confidence,
                    )

        # Sync results
        await p.scheduler.sync_results()

    async def _check_predictions(self) -> None:
        """Check prediction results for finished matches."""
        p = self._prophet
        if not p.prediction_manager:
            return

        results = await p.prediction_manager.check_results()

        # Update team strengths after new results
        for league_code in p.config.active_leagues:
            p.strength_calc.update_all(league_code)

        if results:
            log.info("predictions_checked", count=len(results))

    async def _update_odds(self) -> None:
        """Fetch latest odds for upcoming matches."""
        p = self._prophet
        if not p.odds_provider:
            return

        for league_code in p.config.active_leagues:
            try:
                odds_list = await p.odds_provider.fetch_odds(league_code)
                for raw_odds in odds_list:
                    p.cache.cache_odds(
                        hash(raw_odds.match_external_id),
                        {
                            "home_win": raw_odds.home_win,
                            "draw": raw_odds.draw,
                            "away_win": raw_odds.away_win,
                            "over_25": raw_odds.over_25,
                            "under_25": raw_odds.under_25,
                        },
                    )
            except Exception as e:
                log.error("odds_update_error", league=league_code, error=str(e))

    async def _save_brain(self) -> None:
        """Periodic brain state save."""
        await self._prophet.save_state()


def run_daemon(config: Optional[Config] = None) -> None:
    """Entry point for running as daemon."""
    if config is None:
        config = Config()

    async def _main():
        prophet = FootballProphet(config)
        await prophet.initialize()
        runner = Runner(prophet)

        try:
            await runner.start()
        except KeyboardInterrupt:
            await runner.stop()

    asyncio.run(_main())
