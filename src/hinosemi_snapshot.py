# src/hinosemi_snapshot.py
# 前日終値比で指数を計算。CSVには互換用に pct 列も併記します。
import os
import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))
JST_TZNAME = "Asia/Tokyo"

TICKERS = [
    "8035.T",  # 東京エレクトロン
    "6857.T",  # アドバンテスト
    "285A.T",  # キオクシア
    "6920.T",  # レーザーテック
    "6146.T",  # ディスコ
    "6526.T",  # ソシオネクスト
    "6723.T",  # ルネサス
]


def _ensure_outdir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def _download_intraday(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """当日1分足（UTC index）をティッカー別に取得"""
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d",
        interval="1m",
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    out: dict[str, pd.DataFrame] = {}
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            if t not in data.columns.get_level_values(0):
                continue
            df = data[t][["Open", "Close"]].copy()
            idx = df.index
            if idx.tz is None:
                df.index = idx.tz_localize("UTC")
            else:
                df.index = idx.tz_convert("UTC")
            out[t] = df
    return out


def _download_prevclose(tickers: list[str]) -> dict[str, float]:
    """前日終値を取得（2日分日足から）"""
    prev: dict[str, float] = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="2d", interval="1d", auto_adjust=False)
            if len(hist) >= 2:
                prev[t] = float(hist["Close"].iloc[-2])
        except Exception:
            pass
    return prev


def _build_intraday_series(minute_map: dict[str, pd.DataFrame],
                           prevclose_map: dict[str, float]) -> pd.DataFrame:
    """各時刻の等金額平均（前日終値比％）。CSVは pct と pct_vs_prevclose を出力"""
    if not minute_map:
        return pd.DataFrame(columns=["pct", "pct_vs_prevclose"], dtype=float)

    per_ticker: list[pd.Series] = []
    for tkr, df in minute_map.items():
        if df.empty or tkr not in prevclose_map:
            continue
        base = prevclose_map[tkr]
        # JST帯の取引時間に合わせる
        j = df.tz_convert(JST_TZNAME).sort_index()
        j = j.between_time("09:00", "15:00")
        if j.empty:
            continue
        r = (j["Close"] / base - 1.0) * 100.0
        r.name = tkr
        per_ticker.append(r)

    if not per_ticker:
        return pd.DataFrame(columns=["pct", "pct_vs_prevclose"], dtype=float)

    wide = pd.concat(per_ticker, axis=1)
    idx_pct = wide.mean(axis=1, skipna=True)
    # 少しだけスムージング（視認性向上）
    idx_pct = idx_pct.rolling(3, min_periods=1, center=True).median().ffill()

    out = pd.DataFrame({
        "pct_vs_prevclose": idx_pct,
        "pct": idx_pct,  # 互換エイリアス（旧スクリプト対策）
    })
    out.index.name = "datetime_jst"
    return out


def _save_outputs(series: pd.DataFrame, tickers: list[str]) -> None:
    _ensure_outdir()
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  float_format="%.6f",
                  index_label="datetime_jst")

    last_val = float(series["pct_vs_prevclose"].dropna().iloc[-1]) if len(series) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": last_val,              # 前日終値比（％）
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
    _save_outputs(series, TICKERS)


if __name__ == "__main__":
    main()
