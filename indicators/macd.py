from __future__ import annotations
import pandas as pd
from api.models import IndicatorVote
from indicators.base import BaseIndicator


class MACDIndicator(BaseIndicator):
    weight = 0.25
    name = "MACD"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        try:
            close = ohlcv["close"]
            if len(close) < self.slow + self.signal:
                return self._neutral()
            ema_fast = close.ewm(span=self.fast, adjust=False).mean()
            ema_slow = close.ewm(span=self.slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
            # Detect crossover in last 2 bars
            prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
            curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]
            val = round(float(curr_diff), 6)
            if prev_diff < 0 and curr_diff > 0:
                return IndicatorVote(indicator=self.name, vote="bullish", value=val,
                                     weight=self.weight, reason="MACD crossed above signal")
            if prev_diff > 0 and curr_diff < 0:
                return IndicatorVote(indicator=self.name, vote="bearish", value=val,
                                     weight=self.weight, reason="MACD crossed below signal")
            return IndicatorVote(indicator=self.name, vote="neutral", value=val,
                                 weight=self.weight, reason=f"MACD histogram={val:.4f}")
        except Exception:
            return self._neutral()
