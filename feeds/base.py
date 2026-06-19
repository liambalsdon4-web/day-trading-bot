from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd

REQUIRED_COLS = ["open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = 0.0
    return df[REQUIRED_COLS].dropna()


class AbstractFeed(ABC):
    def __init__(self):
        self._cache: dict[str, pd.DataFrame] = {}
        self._latest_price: dict[str, float] = {}

    def get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        return self._cache.get(symbol)

    def get_price(self, symbol: str) -> float:
        return self._latest_price.get(symbol, 0.0)

    @abstractmethod
    async def start(self, symbols: list[str]) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...
