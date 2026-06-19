from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from api.models import SignalScore
from config.settings import settings
from indicators.rsi import RSIIndicator
from indicators.macd import MACDIndicator
from indicators.ema_crossover import EMACrossover
from indicators.bollinger import BollingerBands
from indicators.volume import VolumeIndicator

_INDICATORS = [
    RSIIndicator(),
    MACDIndicator(),
    EMACrossover(),
    BollingerBands(),
    VolumeIndicator(),
]


def score_symbol(symbol: str, ohlcv: pd.DataFrame, asset_class: str) -> SignalScore:
    votes = [ind.vote(ohlcv) for ind in _INDICATORS]
    total_weight = sum(v.weight for v in votes)

    bull_score = sum(v.weight for v in votes if v.vote == "bullish") / total_weight * 100
    bear_score = sum(v.weight for v in votes if v.vote == "bearish") / total_weight * 100
    net_score = bull_score - bear_score

    if net_score >= settings.buy_threshold:
        action = "BUY"
    elif net_score <= settings.sell_threshold:
        action = "SELL"
    else:
        action = "HOLD"

    confidence = round(abs(net_score) / 100.0, 3)

    return SignalScore(
        symbol=symbol,
        asset_class=asset_class,
        timestamp=datetime.now(timezone.utc),
        votes=votes,
        bull_score=round(bull_score, 1),
        bear_score=round(bear_score, 1),
        net_score=round(net_score, 1),
        action=action,
        confidence=confidence,
    )
