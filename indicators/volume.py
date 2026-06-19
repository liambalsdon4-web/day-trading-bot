from __future__ import annotations
import pandas as pd
from api.models import IndicatorVote
from indicators.base import BaseIndicator


class VolumeIndicator(BaseIndicator):
    weight = 0.15
    name = "VOLUME"

    def __init__(self, period: int = 20, spike_multiplier: float = 2.0):
        self.period = period
        self.spike_multiplier = spike_multiplier

    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        try:
            close = ohlcv["close"]
            volume = ohlcv["volume"]
            if len(volume) < self.period + 1:
                return self._neutral()
            avg_vol = float(volume.iloc[-self.period - 1:-1].mean())
            curr_vol = float(volume.iloc[-1])
            ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0
            price_change = float(close.iloc[-1]) - float(close.iloc[-2])
            if ratio >= self.spike_multiplier:
                if price_change > 0:
                    return IndicatorVote(indicator=self.name, vote="bullish", value=round(ratio, 2),
                                         weight=self.weight, reason=f"Volume spike {ratio:.1f}x avg with price up")
                else:
                    return IndicatorVote(indicator=self.name, vote="bearish", value=round(ratio, 2),
                                         weight=self.weight, reason=f"Volume spike {ratio:.1f}x avg with price down")
            return IndicatorVote(indicator=self.name, vote="neutral", value=round(ratio, 2),
                                 weight=self.weight, reason=f"Volume ratio={ratio:.2f}x (no spike)")
        except Exception:
            return self._neutral()
