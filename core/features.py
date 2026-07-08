"""Vectorised technical features used by the signal scorer and backtester.

Pure functions over an OHLCV DataFrame (columns: open, high, low, close, volume).
`compute()` returns the latest values needed for a regime-aware decision, or None
if there isn't enough data.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd_hist(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def bollinger_pct_b(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = mid + std_dev * sd
    lower = mid - std_dev * sd
    width = (upper - lower).replace(0, np.nan)
    return (close - lower) / width


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    # Wilder's smoothing
    return _true_range(high, low, close).ewm(alpha=1 / period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down
    atr_ = _true_range(high, low, close).ewm(alpha=1 / period, adjust=False).mean().replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def compute(ohlcv: pd.DataFrame, atr_period: int = 14) -> dict | None:
    if ohlcv is None or len(ohlcv) < 55:
        return None
    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    volume = ohlcv["volume"].astype(float)

    ema9, ema21, ema50 = ema(close, 9), ema(close, 21), ema(close, 50)
    hist = macd_hist(close)
    rsi14 = rsi(close, 14)
    pctb = bollinger_pct_b(close)
    atr_s = atr(high, low, close, atr_period)
    adx_s = adx(high, low, close, 14)

    vol_avg = float(volume.iloc[-21:-1].mean())
    vol_ratio = float(volume.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0

    def last(s: pd.Series, default: float = 0.0) -> float:
        v = s.iloc[-1]
        return float(v) if pd.notna(v) else default

    prev_close = float(close.iloc[-2]) if pd.notna(close.iloc[-2]) else last(close)
    return {
        "close": last(close),
        "ema9": last(ema9), "ema21": last(ema21), "ema50": last(ema50),
        "hist": last(hist), "hist_prev": float(hist.iloc[-2]) if pd.notna(hist.iloc[-2]) else 0.0,
        "rsi": last(rsi14, 50.0),
        "pctb": last(pctb, 0.5),
        "atr": last(atr_s),
        "adx": last(adx_s, 0.0),
        "vol_ratio": vol_ratio,
        "price_change": last(close) - prev_close,
    }
