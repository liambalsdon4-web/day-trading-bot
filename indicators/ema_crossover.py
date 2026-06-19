from __future__ import annotations
import pandas as pd
from api.models import IndicatorVote
from indicators.base import BaseIndicator


class EMACrossover(BaseIndicator):
    weight = 0.20
    name = "EMA_CROSS"

    def __init__(self, fast: int = 9, slow: int = 21, lookback: int = 3):
        self.fast = fast
        self.slow = slow
        self.lookback = lookback  # bars to look back for a recent cross

    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        try:
            close = ohlcv["close"]
            if len(close) < self.slow + self.lookback:
                return self._neutral()
            ema_fast = close.ewm(span=self.fast, adjust=False).mean()
            ema_slow = close.ewm(span=self.slow, adjust=False).mean()
            diff = ema_fast - ema_slow
            # Check if a cross happened within the last `lookback` bars
            recent = diff.iloc[-(self.lookback + 1):]
            crossed_up = any(recent.iloc[i] < 0 and recent.iloc[i + 1] >= 0
                             for i in range(len(recent) - 1))
            crossed_down = any(recent.iloc[i] > 0 and recent.iloc[i + 1] <= 0
                               for i in range(len(recent) - 1))
            curr_diff = float(diff.iloc[-1])
            if crossed_up:
                return IndicatorVote(indicator=self.name, vote="bullish", value=round(curr_diff, 4),
                                     weight=self.weight, reason=f"EMA{self.fast} crossed above EMA{self.slow}")
            if crossed_down:
                return IndicatorVote(indicator=self.name, vote="bearish", value=round(curr_diff, 4),
                                     weight=self.weight, reason=f"EMA{self.fast} crossed below EMA{self.slow}")
            return IndicatorVote(indicator=self.name, vote="neutral", value=round(curr_diff, 4),
                                 weight=self.weight, reason="No recent EMA crossover")
        except Exception:
            return self._neutral()
