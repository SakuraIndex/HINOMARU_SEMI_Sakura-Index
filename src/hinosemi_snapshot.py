# -*- coding: utf-8 -*-
"""
HINOMARU SEMICONDUCTOR Index (等金額加重・Intraday)
"""
import os
import json
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

KEY = "HINOSEMI"
OUT_DIR = "docs/outputs"

JP_TICKERS: Dict[str, str] = {
    "8035.T": "東京エレクトロン",
    "6857.T": "アドバンテスト",
    "285A.T": "キオクシア",       # 2024/12/18 上場
    "6920.T": "レーザーテック",
    "6146.T": "ディスコ",
    "6526.T": "ソシオネクスト",
    "6723.T": "ルネサスエレクトロニクス",
}

# ---------- helpers ----------
def _now_jst():
    return pd.Timestamp.now(tz="Asia/Tokyo").to_pydatetime()

def _to_jst_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df.tz_convert("Asia/Tokyo").rename_axis("datetime_jst")

def _flatten_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    want = ["open", "high", "low", "close", "adj close", "volume"]
    out = pd.DataFrame(index=df.index)
    low0 = [tuple(map(lambda x: str(x).lower(), c)) for c in df.columns]
    for name in want:
        for col, low in zip(df.columns, low0):
            if low[0] == name:
                out[name.title() if name != "adj close" else "Adj Close"] = df[col]
                break
    return out

def _standardize_ohlc(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = _flatten_multiindex(df)
    mapping = {c: str(c).lower().strip() for c in df.columns}
    df = df.rename(columns=mapping)
    if "adj close" not in df.columns and "adjclose" in df.columns:
        df["adj close"] = df["adjclose"]
    rename_back = {}
    for c in df.columns:
        if c == "adj close":
            rename_back[c] = "Adj Close"
        else:
            rename_back[c] = c.title()
    df = df.rename(columns=rename_back)
    if "Close" not in df.columns and "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"]
    need = {"Open", "Close"}
    if not need.issubset(set(df.columns)):
        return pd.DataFrame()
    df["Ticker"] = ticker
    df = _to_jst_index(df)
    for col in ["Open", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["Open", "Close", "Ticker"]].dropna(how="any")

def _download_one(ticker: str) -> pd.DataFrame:
    for interval in ("5m", "15m"):
        try:
            raw = yf.download(
                ticker, period="1d", interval=interval,
                auto_adjust=False, progress=False, threads=False
            )
        except Exception:
            raw = pd.DataFrame()
        df = _standardize_ohlc(raw, ticker)
        if not df.empty:
            return df
    return pd.DataFrame()

def fetch_prices(tickers: List[str]) -> pd.DataFrame:
    frames = []
    for t in tickers:
        df = _download_one(t)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_index()

def build_intraday_series(raw: pd.DataFrame) -> pd.Series:
    if raw.empty:
        raise RuntimeError("no prices at all")
    need = {"Open", "Close", "Ticker"}
    if not need.issubset(set(raw.columns)):
        missing = need - set(raw.columns)
        raise RuntimeError(f"missing columns: {missing}")
    series_list = []
    for t, df1 in raw.groupby("Ticker"):
        base = df1["Open"].dropna()
        if base.empty:
            continue
        base = float(base.iloc[0])
        if not np.isfinite(base) or base == 0:
            continue
        s = (df1["Close"].astype(float) / base - 1.0) * 100.0
        s.name = t
        series_list.append(s)
    if not series_list:
        raise RuntimeError("no valid series after cleaning")
    mat = pd.concat(series_list, axis=1).sort_index()
    avg = mat.mean(axis=1, skipna=True).ffill().dropna()
    if avg.empty:
        raise RuntimeError("no prices after ffill")
    return avg

def save_outputs(series: pd.Series, tickers: List[str]) -> None:
    # ★ 出力先フォルダを必ず作成
    os.makedirs(OUT_DIR, exist_ok=True)

    series = series.copy()
    series.name = "ret"
    (series.to_frame()
           .to_csv(f"{OUT_DIR}/hinosemi_intraday.csv", index_label="datetime_jst"))

    last_pct = float(series.iloc[-1])
    stats = {
        "key": KEY,
        "pct_intraday": round(last_pct, 2),
        "updated_at": _now_jst().strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(f"{OUT_DIR}/hinosemi_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/last_run.txt", "w", encoding="utf-8") as f:
        f.write(_now_jst().strftime("%Y/%m/%d %H:%M:%S"))

    sign = "+" if last_pct >= 0 else ""
    post = [
        "【HINOSEMI｜日の丸半導体指数】",
        f"本日: {sign}{last_pct:.2f}%",
        f"構成: {','.join(tickers)}",
        "#桜Index #HINOSEMI",
    ]
    with open(f"{OUT_DIR}/hinosemi_post_intraday.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(post))

def main():
    tickers = list(JP_TICKERS.keys())
    raw = fetch_prices(tickers)
    if raw.empty:
        raise RuntimeError("no prices at all")
    series = build_intraday_series(raw)
    save_outputs(series, tickers)

if __name__ == "__main__":
    main()
