from __future__ import annotations
import pandas as pd
from api.models import IndicatorVote
from indicators.base import BaseIndicator


class BollingerBands(BaseIndicator):
    weight = 0.15
    name = "BBANDS"

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        try:
            close = ohlcv["close"]
            if len(close) < self.period:
                return self._neutral()
            rolling = close.rolling(self.period)
            mid = rolling.mean()
            std = rolling.std()
            upper = mid + self.std_dev * std
            lower = mid - self.std_dev * std
            price = float(close.iloc[-1])
            upper_val = float(upper.iloc[-1])
            lower_val = float(lower.iloc[-1])
            # Use %B (0-1 position within bands) as the value
            band_width = upper_val - lower_val
            pct_b = (price - lower_val) / band_width if band_width else 0.5
            if price <= lower_val:
                return IndicatorVote(indicator=self.name, vote="bullish", value=round(pct_b, 3),
                                     weight=self.weight, reason=f"Price at/below lower band (%B={pct_b:.2f})")
            if price >= upper_val:
                return IndicatorVote(indicator=self.name, vote="bearish", value=round(pct_b, 3),
                                     weight=self.weight, reason=f"Price at/above upper band (%B={pct_b:.2f})")
            return IndicatorVote(indicator=self.name, vote="neutral", value=round(pct_b, 3),
                                 weight=self.weight, reason=f"Price within bands (%B={pct_b:.2f})")
        except Exception:
            return self._neutral()
