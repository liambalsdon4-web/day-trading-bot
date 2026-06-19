from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
from api.models import IndicatorVote


class BaseIndicator(ABC):
    weight: float = 1.0
    name: str = "base"

    @abstractmethod
    def vote(self, ohlcv: pd.DataFrame) -> IndicatorVote:
        """Return a vote given an OHLCV DataFrame. Never raises — returns neutral on bad data."""
        ...

    def _neutral(self, value: float = 0.0, reason: str = "insufficient data") -> IndicatorVote:
        return IndicatorVote(
            indicator=self.name, vote="neutral",
            value=value, weight=self.weight, reason=reason,
        )
