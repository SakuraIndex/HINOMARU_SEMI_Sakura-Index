# src/hinosemi_snapshot.py  修正完全版
import os
import json                    # ← 追加
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))

TICKERS = [
    "8035.T",   # 東京エレクトロン
    "6857.T",   # アドバンテスト
    "285A.T",   # キオクシア ← 285A に修正済み
    "6920.T",   # レーザーテック
    "6146.T",   # ディスコ
    "6526.T",   # ソシオネクスト
    "6723.T",   # ルネサスエレクトロニクス
]

def _ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_intraday(tickers):
    # 今日の日本時間分を取得（5分足）
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d",
        interval="5m",
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    # yfinanceの返却を縦に積む
    frames = []
    for t in tickers:
        df = data[t].copy()
        df = df.reset_index().rename(columns={"Datetime": "datetime_utc"})
        df["Ticker"] = t
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # UTC→JST
    df["datetime_jst"] = pd.to_datetime(df["datetime_utc"]).dt.tz_convert(JST)
    # 必要列だけ並べる
    df = df[["datetime_jst", "Open", "Close", "Ticker"]].dropna()
    return df

def _build_intraday_series(raw: pd.DataFrame) -> pd.DataFrame:
    # 始値で揃えて騰落率(%)を算出 → 等金額加重
    raw = raw.copy()
    # 各ティッカーの「当日始値」
    open_map = (
        raw.sort_values("datetime_jst")
           .groupby("Ticker")["Open"]
           .first()
    )
    raw = raw.merge(open_map.rename("Open0"), on="Ticker", how="left")
    raw["pct_vs_open"] = (raw["Close"] / raw["Open0"] - 1.0) * 100.0
    # 時刻ごとに平均（等金額加重）
    s = (raw.groupby("datetime_jst")["pct_vs_open"].mean()
           .rename("pct_vs_open"))
    return s.to_frame()

def save_outputs(series: pd.DataFrame, tickers: list[str]) -> None:
    _ensure_outdir()
    # CSV（可視化やデバッグ用）
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  index_label="datetime_jst")
    # 統計JSON（ダッシュボードなどで利用）
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": float(series["pct_vs_open"].iloc[-1]) if len(series) else 0.0,
        "updated_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(os.path.join(OUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False, indent=2))  # ← 修正ポイント

def main():
    raw = _download_intraday(TICKERS)
    series = _build_intraday_series(raw)
    save_outputs(series, TICKERS)

if __name__ == "__main__":
    main()
