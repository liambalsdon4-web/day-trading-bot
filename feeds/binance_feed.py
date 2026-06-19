from __future__ import annotations
import asyncio
import pandas as pd
from feeds.base import AbstractFeed, normalize_ohlcv
from config.settings import settings


class BinanceFeed(AbstractFeed):
    """CCXT-based polling feed for crypto OHLCV data."""

    def __init__(self):
        super().__init__()
        self._running = False
        self._symbols: list[str] = []
        import ccxt
        exchange_class = getattr(ccxt, settings.crypto_exchange)
        creds = {}
        if settings.binance_api_key:
            creds = {"apiKey": settings.binance_api_key, "secret": settings.binance_secret}
        self._exchange = exchange_class(creds)

    async def start(self, symbols: list[str]) -> None:
        self._symbols = symbols
        self._running = True
        await self._refresh_all()
        while self._running:
            await asyncio.sleep(settings.tick_interval_seconds)
            await self._refresh_all()

    async def stop(self) -> None:
        self._running = False

    async def _refresh_all(self) -> None:
        for symbol in self._symbols:
            try:
                await asyncio.to_thread(self._fetch_symbol, symbol)
            except Exception:
                pass

    def _fetch_symbol(self, symbol: str) -> None:
        raw = self._exchange.fetch_ohlcv(symbol, timeframe="1m", limit=settings.ohlcv_bars)
        if not raw:
            return
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = normalize_ohlcv(df)
        self._cache[symbol] = df.iloc[-settings.ohlcv_bars:]
        self._latest_price[symbol] = float(df["close"].iloc[-1])
