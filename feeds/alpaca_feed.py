from __future__ import annotations
import asyncio
import pandas as pd
from feeds.base import AbstractFeed, normalize_ohlcv
from config.settings import settings


class AlpacaFeed(AbstractFeed):
    """Alpaca historical data polling for live stock data."""

    def __init__(self):
        super().__init__()
        self._running = False
        self._symbols: list[str] = []
        from alpaca.data.historical import StockHistoricalDataClient
        self._client = StockHistoricalDataClient(
            settings.alpaca_api_key, settings.alpaca_secret_key
        )

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
            except Exception as e:
                print(f"[feed] failed to fetch {symbol}: {e}")

    def _fetch_symbol(self, symbol: str) -> None:
        if symbol in settings.crypto_symbols:
            self._fetch_crypto_yfinance(symbol)
        else:
            self._fetch_stock_alpaca(symbol)

    def _fetch_stock_alpaca(self, symbol: str) -> None:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from datetime import datetime, timedelta, timezone
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=datetime.now(timezone.utc) - timedelta(days=5),
            limit=settings.ohlcv_bars,
        )
        bars = self._client.get_stock_bars(req)
        df = bars.df
        if df.empty:
            return
        df = df.reset_index()
        df = df.rename(columns={"timestamp": "datetime"})
        df = normalize_ohlcv(df)
        self._cache[symbol] = df.iloc[-settings.ohlcv_bars:]
        self._latest_price[symbol] = float(df["close"].iloc[-1])

    def _fetch_crypto_yfinance(self, symbol: str) -> None:
        import yfinance as yf
        import pandas as pd
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
