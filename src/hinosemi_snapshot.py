# src/hinosemi_snapshot.py  前日終値比バージョン（推奨）
import os
import json
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))
JST_TZNAME = "Asia/Tokyo"

TICKERS = [
    "8035.T", "6857.T", "285A.T", "6920.T", "6146.T", "6526.T", "6723.T"
]

def _ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_intraday(tickers):
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d",
        interval="1m",
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    out = {}
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            if t not in data.columns.get_level_values(0):
                continue
            df = data[t][["Open","Close"]].copy()
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
            out[t] = df
    return out

def _download_prevclose(tickers):
    """前日終値を取得（2日間分ヒストリカルデータ）"""
    prev = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="2d", interval="1d")
            if len(hist) >= 2:
                prev[t] = float(hist["Close"].iloc[-2])
        except Exception:
            continue
    return prev

def _build_intraday_series(minute_map, prevclose_map):
    if not minute_map:
        return pd.DataFrame(columns=["pct_vs_prevclose"], dtype=float)

    per_ticker = []
    for tkr, df in minute_map.items():
        if df.empty or tkr not in prevclose_map:
            continue
        base = prevclose_map[tkr]
        df = df.tz_convert(JST_TZNAME).sort_index()
        lo, hi = df.between_time("09:00", "15:00"), df.between_time("09:00", "15:00")
        df = df.loc[(df.index >= lo.index.min()) & (df.index <= hi.index.max())]
        if df.empty:
            continue
        r = (df["Close"] / base - 1.0) * 100.0
        r.name = tkr
        per_ticker.append(r)

    if not per_ticker:
        return pd.DataFrame(columns=["pct_vs_prevclose"], dtype=float)

    wide = pd.concat(per_ticker, axis=1)
    idx_pct = wide.mean(axis=1, skipna=True)
    idx_pct = idx_pct.rolling(3, min_periods=1, center=True).median()
    idx_pct = idx_pct.ffill()
    return idx_pct.to_frame(name="pct_vs_prevclose")

def save_outputs(series, tickers):
    _ensure_outdir()
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  index_label="datetime_jst")
    last_val = float(series["pct_vs_prevclose"].dropna().iloc[-1]) if len(series) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": last_val,
        "updated_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(os.path.join(OUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def main():
    minute_map = _download_intraday(TICKERS)
    prevclose_map = _download_prevclose(TICKERS)
    series = _build_intraday_series(minute_map, prevclose_map)
    if series.empty:
        raise RuntimeError("no data")
    save_outputs(series, TICKERS)

if __name__ == "__main__":
    main()
