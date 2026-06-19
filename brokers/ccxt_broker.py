from __future__ import annotations
import os
import asyncio
from brokers.base import AbstractBroker
from config.settings import settings


class CCXTBroker(AbstractBroker):
    """CCXT-based crypto broker. Paper mode simulates fills locally."""

    def __init__(self, current_prices: dict):
        self._prices = current_prices
        import ccxt
        exchange_class = getattr(ccxt, settings.crypto_exchange)
        creds = {}
        if settings.binance_api_key:
            creds = {"apiKey": settings.binance_api_key, "secret": settings.binance_secret}
        self._exchange = exchange_class(creds)

    async def place_order(self, symbol: str, side: str, qty: float,
                          stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict:
        if settings.mode == "paper":
            price = self._prices.get(symbol, 0.0)
            return {"id": "paper", "symbol": symbol, "side": side,
                    "qty": qty, "filled_price": price, "status": "filled"}

        assert os.getenv("CONFIRM_LIVE_TRADING") == "YES_I_UNDERSTAND", (
            "Set CONFIRM_LIVE_TRADING=YES_I_UNDERSTAND to enable live crypto trading"
        )
        order = await asyncio.to_thread(
            self._exchange.create_order, symbol, "market", side.lower(), qty
        )
        return {"id": order["id"], "symbol": symbol, "side": side,
                "qty": qty, "filled_price": order.get("price", 0), "status": "filled"}

    async def close_position(self, symbol: str, qty: float, current_price: float) -> dict:
        return await self.place_order(symbol, "SELL", qty)

    async def get_current_price(self, symbol: str) -> float:
        try:
            ticker = await asyncio.to_thread(self._exchange.fetch_ticker, symbol)
            return float(ticker["last"] or 0)
        except Exception:
            return self._prices.get(symbol, 0.0)
