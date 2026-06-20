from __future__ import annotations
import asyncio
import pandas as pd
import yfinance as yf
from feeds.base import AbstractFeed, normalize_ohlcv
from config.settings import settings


class YFinanceFeed(AbstractFeed):
    """Polling feed using yfinance. No API keys required."""

    def __init__(self):
        super().__init__()
        self._running = False
        self._symbols: list[str] = []

    async def start(self, symbols: list[str]) -> None:
        self._symbols = symbols
        self._running = True
        # Initial load
        await self._refresh_all()
        # Keep refreshing every tick interval
        while self._running:
            await asyncio.sleep(settings.tick_interval_seconds)
            await self._refresh_all()

    async def stop(self) -> None:
        self._running = False

    async def _refresh_all(self) -> None:
        for symbol in self._symbols:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_symbol, symbol),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[feed] failed to fetch {symbol}: {e}")

    def _fetch_symbol(self, symbol: str) -> None:
        df = yf.download(symbol, period="5d", interval="1m", progress=False, auto_adjust=True)
        if df.empty:
            return
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = normalize_ohlcv(df)
        if len(df) > settings.ohlcv_bars:
            df = df.iloc[-settings.ohlcv_bars:]
        self._cache[symbol] = df
        self._latest_price[symbol] = float(df["close"].iloc[-1])
