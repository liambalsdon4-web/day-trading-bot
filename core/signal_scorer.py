"""Regime-aware, state-based signal scorer.

Classifies each symbol as TRENDING (ADX high) or RANGING and interprets the
indicators accordingly, so trend and mean-reversion signals no longer fight each
other. Trend indicators dominate in a trend; Bollinger/RSI dominate (and flip to
mean-reversion) in a range. Returns a SignalScore, including the current ATR for
volatility-based risk sizing.
"""
from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from api.models import SignalScore, IndicatorVote
from config.settings import settings
from core import features


def _vote(name: str, direction: str, value: float, weight: float, reason: str) -> IndicatorVote:
    return IndicatorVote(indicator=name, vote=direction, value=round(float(value), 4),
                         weight=weight, reason=reason)


# Dynamic weights per regime (each sums to 1.0)
_TREND_W = {"EMA_CROSS": 0.30, "MACD": 0.30, "RSI": 0.10, "BBANDS": 0.10, "VOLUME": 0.20}
_RANGE_W = {"EMA_CROSS": 0.05, "MACD": 0.05, "RSI": 0.30, "BBANDS": 0.30, "VOLUME": 0.30}


def score_symbol(symbol: str, ohlcv: pd.DataFrame, asset_class: str) -> SignalScore:
    now = datetime.now(timezone.utc)
    f = features.compute(ohlcv, settings.atr_period)
    if f is None:
        return SignalScore(symbol=symbol, asset_class=asset_class, timestamp=now, votes=[],
                           bull_score=0, bear_score=0, net_score=0, action="HOLD",
                           confidence=0, atr=0.0)

    trending = f["adx"] >= settings.adx_trend_threshold
    trend_up = f["ema9"] > f["ema21"] and f["close"] >= f["ema50"]
    trend_down = f["ema9"] < f["ema21"] and f["close"] <= f["ema50"]
    regime = "trend" if trending else "range"
    w = _TREND_W if trending else _RANGE_W

    votes: list[IndicatorVote] = []

    # ── EMA trend state (continuous, not just the crossover event) ──
    if f["ema9"] > f["ema21"]:
        votes.append(_vote("EMA_CROSS", "bullish", f["ema9"] - f["ema21"], w["EMA_CROSS"],
                           f"EMA9>EMA21 uptrend ({regime})"))
    elif f["ema9"] < f["ema21"]:
        votes.append(_vote("EMA_CROSS", "bearish", f["ema9"] - f["ema21"], w["EMA_CROSS"],
                           f"EMA9<EMA21 downtrend ({regime})"))
    else:
        votes.append(_vote("EMA_CROSS", "neutral", 0, w["EMA_CROSS"], "EMA flat"))

    # ── MACD histogram sign + slope ──
    if f["hist"] > 0 and f["hist"] >= f["hist_prev"]:
        votes.append(_vote("MACD", "bullish", f["hist"], w["MACD"], "MACD histogram positive & rising"))
    elif f["hist"] < 0 and f["hist"] <= f["hist_prev"]:
        votes.append(_vote("MACD", "bearish", f["hist"], w["MACD"], "MACD histogram negative & falling"))
    else:
        votes.append(_vote("MACD", "neutral", f["hist"], w["MACD"], "MACD momentum flattening"))

    # ── RSI: trend-confirm in a trend, mean-reversion in a range ──
    r = f["rsi"]
    if trending:
        if trend_up and r < 70:
            votes.append(_vote("RSI", "bullish", r, w["RSI"], f"RSI={r:.0f} confirms uptrend"))
        elif trend_down and r > 30:
            votes.append(_vote("RSI", "bearish", r, w["RSI"], f"RSI={r:.0f} confirms downtrend"))
        else:
            votes.append(_vote("RSI", "neutral", r, w["RSI"], f"RSI={r:.0f} extreme — step aside in trend"))
    else:
        if r < 35:
            votes.append(_vote("RSI", "bullish", r, w["RSI"], f"RSI={r:.0f} oversold (range)"))
        elif r > 65:
            votes.append(_vote("RSI", "bearish", r, w["RSI"], f"RSI={r:.0f} overbought (range)"))
        else:
            votes.append(_vote("RSI", "neutral", r, w["RSI"], f"RSI={r:.0f} neutral"))

    # ── Bollinger %B: continuation in a trend, reversion in a range ──
    b = f["pctb"]
    if trending:
        if trend_up and b > 0.8:
            votes.append(_vote("BBANDS", "bullish", b, w["BBANDS"], f"%B={b:.2f} riding upper band (trend)"))
        elif trend_down and b < 0.2:
            votes.append(_vote("BBANDS", "bearish", b, w["BBANDS"], f"%B={b:.2f} riding lower band (trend)"))
        else:
            votes.append(_vote("BBANDS", "neutral", b, w["BBANDS"], f"%B={b:.2f}"))
    else:
        if b < 0.1:
            votes.append(_vote("BBANDS", "bullish", b, w["BBANDS"], f"%B={b:.2f} at lower band (range)"))
        elif b > 0.9:
            votes.append(_vote("BBANDS", "bearish", b, w["BBANDS"], f"%B={b:.2f} at upper band (range)"))
        else:
            votes.append(_vote("BBANDS", "neutral", b, w["BBANDS"], f"%B={b:.2f} mid-band"))

    # ── Volume confirmation ──
    vr = f["vol_ratio"]
    if vr >= 1.5 and f["price_change"] > 0:
        votes.append(_vote("VOLUME", "bullish", vr, w["VOLUME"], f"Volume {vr:.1f}x avg, price up"))
    elif vr >= 1.5 and f["price_change"] < 0:
        votes.append(_vote("VOLUME", "bearish", vr, w["VOLUME"], f"Volume {vr:.1f}x avg, price down"))
    else:
        votes.append(_vote("VOLUME", "neutral", vr, w["VOLUME"], f"Volume {vr:.1f}x avg (no confirmation)"))

    total_w = sum(v.weight for v in votes) or 1.0
    bull = sum(v.weight for v in votes if v.vote == "bullish") / total_w * 100
    bear = sum(v.weight for v in votes if v.vote == "bearish") / total_w * 100
    net = bull - bear

    # Entry gate. With trend_only_entries, only BUY in a confirmed uptrend regime
    # (cuts noisy range-bound buys); otherwise just avoid buying into a downtrend.
    allow_buy = net >= settings.buy_threshold
    if settings.trend_only_entries:
        allow_buy = allow_buy and trending and trend_up
    else:
        allow_buy = allow_buy and not trend_down

    if allow_buy:
        action = "BUY"
    elif net <= settings.sell_threshold:
        action = "SELL"
    else:
        action = "HOLD"

    return SignalScore(
        symbol=symbol, asset_class=asset_class, timestamp=now, votes=votes,
        bull_score=round(bull, 1), bear_score=round(bear, 1), net_score=round(net, 1),
        action=action, confidence=round(abs(net) / 100.0, 3), atr=round(f["atr"], 6),
    )
