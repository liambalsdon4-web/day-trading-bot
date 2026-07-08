"""Backtest the current strategy on historical bars.

Replays each symbol bar-by-bar through the real signal_scorer, then simulates
entries/exits with the same ATR stops/targets/trailing and execution costs the
live bot uses. Fills happen on the *next* bar's open; stops/targets are checked
against the next bar's high/low (stop assumed to fill first — conservative).

Usage:
    python backtest.py                      # defaults: 5m bars, 60 days
    python backtest.py --interval 1m --period 7d
    python backtest.py --symbols AAPL,BTC-USD --interval 15m --period 60d

Note: the live bot trades 1-minute bars, but yfinance only serves ~7 days of 1m.
5m/60d is used by default for a statistically meaningful sample — treat it as a
proxy, and re-run with --interval 1m --period 7d for the exact live timeframe.
"""
from __future__ import annotations
import argparse
import pandas as pd
from config.settings import settings
from core import signal_scorer

WARMUP = 60          # bars needed before features are valid
MAX_BARS_HELD = 200  # proxy for the time-based exit


def fetch(symbol: str, interval: str, period: str) -> pd.DataFrame | None:
    import yfinance as yf
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    return df[keep].dropna()


def backtest_symbol(symbol: str, asset_class: str, df: pd.DataFrame) -> dict:
    cost = (settings.slippage_bps + settings.fee_bps) / 10_000.0
    equity = settings.starting_capital
    peak, max_dd = equity, 0.0
    trades: list[float] = []
    pos = None

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)

    for i in range(WARMUP, n - 1):
        sig = signal_scorer.score_symbol(symbol, df.iloc[: i + 1], asset_class)
        nb_open, nb_high, nb_low = opens[i + 1], highs[i + 1], lows[i + 1]

        if pos is not None:
            if nb_high > pos["highest"]:
                pos["highest"] = nb_high
            if sig.atr > 0 and pos["highest"] > pos["entry"]:
                trail = pos["highest"] - settings.atr_trail_mult * sig.atr
                if trail > pos["stop"]:
                    pos["stop"] = trail
            pos["bars"] += 1

            exit_price, reason = None, None
            if nb_low <= pos["stop"]:
                exit_price, reason = pos["stop"], "STOP"          # conservative: stop first
            elif nb_high >= pos["target"]:
                exit_price, reason = pos["target"], "TARGET"
            elif sig.action == "SELL":
                exit_price, reason = nb_open, "SIGNAL"
            elif pos["bars"] >= MAX_BARS_HELD:
                exit_price, reason = nb_open, "TIME"

            if exit_price is not None:
                fill = exit_price * (1 - cost)
                pnl = (fill - pos["entry"]) * pos["qty"]
                equity += pnl
                trades.append(pnl)
                peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
                pos = None

        elif sig.action == "BUY" and sig.atr > 0:
            entry = nb_open * (1 + cost)
            stop = entry - settings.atr_stop_mult * sig.atr
            target = entry + settings.atr_target_mult * sig.atr
            stop_dist = entry - stop
            if stop_dist > 0:
                qty = (equity * settings.risk_per_trade_pct) / stop_dist
                qty = min(qty, equity * settings.max_notional_pct / entry)
                if qty > 0:
                    pos = {"entry": entry, "stop": stop, "target": target,
                           "qty": qty, "highest": entry, "bars": 0}

    if pos is not None:  # close leftover at final close
        fill = closes[-1] * (1 - cost)
        pnl = (fill - pos["entry"]) * pos["qty"]
        equity += pnl
        trades.append(pnl)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    n_trades = len(trades)
    return {
        "symbol": symbol,
        "trades": n_trades,
        "win_rate": (len(wins) / n_trades * 100) if n_trades else 0.0,
        "avg_win": (gross_win / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0),
        "expectancy": (sum(trades) / n_trades) if n_trades else 0.0,
        "return_pct": (equity - settings.starting_capital) / settings.starting_capital * 100,
        "max_dd_pct": max_dd / settings.starting_capital * 100,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(settings.stock_symbols + settings.crypto_symbols))
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--period", default="60d")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    crypto = set(settings.crypto_symbols)

    print(f"\nBacktest — interval={args.interval}, period={args.period}, "
          f"cost={(settings.slippage_bps + settings.fee_bps):.0f}bps/side, "
          f"risk={settings.risk_per_trade_pct*100:.2f}%/trade, "
          f"stop={settings.atr_stop_mult}xATR, target={settings.atr_target_mult}xATR\n")
    header = f"{'SYMBOL':<10}{'TRADES':>7}{'WIN%':>7}{'PF':>7}{'EXPECT':>9}{'RET%':>8}{'MAXDD%':>8}"
    print(header)
    print("-" * len(header))

    rows = []
    for sym in symbols:
        asset = "crypto" if sym in crypto else "stock"
        df = fetch(sym, args.interval, args.period)
        if df is None or len(df) < WARMUP + 10:
            print(f"{sym:<10}   (no/insufficient data)")
            continue
        m = backtest_symbol(sym, asset, df)
        rows.append(m)
        print(f"{m['symbol']:<10}{m['trades']:>7}{m['win_rate']:>7.1f}{m['profit_factor']:>7.2f}"
              f"{m['expectancy']:>9.2f}{m['return_pct']:>8.2f}{m['max_dd_pct']:>8.2f}")

    if rows:
        tot_trades = sum(r["trades"] for r in rows)
        avg_ret = sum(r["return_pct"] for r in rows) / len(rows)
        avg_win_rate = sum(r["win_rate"] * r["trades"] for r in rows) / tot_trades if tot_trades else 0
        print("-" * len(header))
        print(f"{'TOTAL/AVG':<10}{tot_trades:>7}{avg_win_rate:>7.1f}{'':>7}{'':>9}{avg_ret:>8.2f}")
        print("\nPF=profit factor (gross win/gross loss), EXPECT=avg $ per trade on "
              f"${settings.starting_capital:,.0f}, RET%=per-symbol return, MAXDD%=max drawdown.\n")


if __name__ == "__main__":
    main()
