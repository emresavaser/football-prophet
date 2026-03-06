"""Throttled Telegram notifier for alerts and reports."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from utils.logging import get_logger

log = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """
    Sends notifications via Telegram Bot API.
    Includes throttling to avoid rate limits.
    """

    MIN_INTERVAL = 2.0  # Min seconds between messages

    def __init__(self, bot_token: str, chat_id: str):
        self._token = bot_token
        self._chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=30.0)
        self._last_send_ts: float = 0.0

    async def _throttled_send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message with throttling."""
        now = time.time()
        elapsed = now - self._last_send_ts
        if elapsed < self.MIN_INTERVAL:
            await asyncio.sleep(self.MIN_INTERVAL - elapsed)

        try:
            resp = await self._client.post(
                f"{TELEGRAM_API}/bot{self._token}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            self._last_send_ts = time.time()
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error("telegram_send_error", error=str(e))
            return False

    async def send_value_bet_alert(
        self,
        home_team: str,
        away_team: str,
        market: str,
        odds: float,
        edge: float,
        ev: float,
        kelly: float,
        confidence: float,
    ) -> bool:
        """Send value bet alert."""
        market_display = {
            "home_win": "Ev Sahibi Kazanir",
            "draw": "Beraberlik",
            "away_win": "Deplasman Kazanir",
            "over_25": "2.5 Ust",
            "under_25": "2.5 Alt",
            "btts_yes": "KG Var",
            "btts_no": "KG Yok",
        }.get(market, market)

        text = (
            f"<b>VALUE BET BULUNDU</b>\n\n"
            f"<b>{home_team}</b> vs <b>{away_team}</b>\n"
            f"Piyasa: {market_display}\n"
            f"Oran: <b>{odds:.2f}</b>\n"
            f"Edge: <b>+{edge:.1%}</b>\n"
            f"EV: <b>+{ev:.3f}</b>\n"
            f"Kelly: {kelly:.1%}\n"
            f"Guven: {confidence:.0%}"
        )
        return await self._throttled_send(text)

    async def send_daily_summary(
        self,
        predictions_made: int,
        correct: int,
        total_checked: int,
        value_bets_found: int,
        accuracy_30d: float,
    ) -> bool:
        """Send daily prediction summary."""
        text = (
            f"<b>GUNLUK OZET</b>\n\n"
            f"Tahminler: {predictions_made}\n"
            f"Kontrol Edilen: {total_checked}\n"
            f"Dogru: {correct}/{total_checked} "
            f"({correct/total_checked:.0%} )" if total_checked > 0 else ""
            f"\nValue Bet: {value_bets_found}\n"
            f"30 Gun Dogruluk: {accuracy_30d:.1%}"
        )
        return await self._throttled_send(text)

    async def send_model_report(self, weights: dict, performance: dict) -> bool:
        """Send model performance report."""
        lines = ["<b>MODEL PERFORMANS RAPORU</b>\n"]
        for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            perf = performance.get(name, {})
            brier = perf.get("avg_brier", "N/A")
            brier_str = f"{brier:.4f}" if isinstance(brier, float) else brier
            lines.append(f"  {name}: agirlik={w:.3f} brier={brier_str}")

        return await self._throttled_send("\n".join(lines))

    async def send_match_result(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        predicted: str,
        actual: str,
        was_correct: bool,
    ) -> bool:
        """Send match result notification."""
        icon = "+" if was_correct else "-"
        text = (
            f"<b>MAC SONUCU</b> [{icon}]\n\n"
            f"{home_team} {home_score}-{away_score} {away_team}\n"
            f"Tahmin: {predicted} | Gercek: {actual}\n"
            f"{'DOGRU' if was_correct else 'YANLIS'}"
        )
        return await self._throttled_send(text)

    async def close(self) -> None:
        await self._client.aclose()
