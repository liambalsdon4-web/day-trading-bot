from __future__ import annotations
import pandas as pd
from api.models import IndicatorVote
from indicators.base import BaseIndicator


class RSIIndicator(BaseIndicator):
    weight = 0.25
    name = "RSI"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        try:
            close = ohlcv["close"]
            if len(close) < self.period + 1:
                return self._neutral()
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(self.period).mean()
            loss = (-delta.clip(upper=0)).rolling(self.period).mean()
            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))
            val = float(rsi.iloc[-1])
            if val < self.oversold:
                return IndicatorVote(indicator=self.name, vote="bullish", value=round(val, 2),
                                     weight=self.weight, reason=f"RSI={val:.1f} (oversold)")
            if val > self.overbought:
                return IndicatorVote(indicator=self.name, vote="bearish", value=round(val, 2),
                                     weight=self.weight, reason=f"RSI={val:.1f} (overbought)")
            return IndicatorVote(indicator=self.name, vote="neutral", value=round(val, 2),
                                 weight=self.weight, reason=f"RSI={val:.1f} (neutral zone)")
        except Exception:
            return self._neutral()
