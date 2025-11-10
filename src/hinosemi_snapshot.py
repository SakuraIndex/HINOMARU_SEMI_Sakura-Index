# -*- coding: utf-8 -*-
"""
HINOMARU SEMICONDUCTOR Index (等金額加重・Intraday)
- 取得: Yahoo!Finance (period=1d, interval=5m→fallback 15m)
- 出力:
  docs/outputs/hinosemi_intraday.csv
  docs/outputs/hinosemi_stats.json
  docs/outputs/last_run.txt
  docs/outputs/hinosemi_post_intraday.txt
"""

import json
import math
from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

KEY = "HINOSEMI"
OUT_DIR = "docs/outputs"

# 東証ティッカー（Yahoo!Finance 形式）
# 例: 8035.T（東京エレクトロン）、285A.T（キオクシア）
JP_TICKERS: Dict[str, str] = {
    "8035.T": "東京エレクトロン",
    "6857.T": "アドバンテスト",
    "285A.T": "キオクシア",                 # 2024/12/18 上場
    "6920.T": "レーザーテック",
    "6146.T": "ディスコ",
    "6526.T": "ソシオネクスト",
    "6723.T": "ルネサスエレクトロニクス",
}

def _now_jst_str() -> str:
    return datetime.now(timezone.utc).astimezone(
        timezone.utc
    ).astimezone(pd.Timestamp.now(tz="Asia/Tokyo").tz).strftime("%Y/%m/%d %H:%M (JST)")

def _to_jst_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df = df.tz_convert("Asia/Tokyo")
    df.index.name = "datetime_jst"
    return df

def _download_one(ticker: str) -> pd.DataFrame:
    """1銘柄を 5m→15m の順で取得。成功したものを返す。"""
    for interval in ("5m", "15m"):
        try:
            df = yf.download(
                ticker,
                period="1d",
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception:
            df = pd.DataFrame()
        if df is not None and not df.empty:
            df = _to_jst_index(df)
            df["Ticker"] = ticker
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
    """
    各銘柄の「Close / 初回Open - 1」を%にして等金額平均。
    """
    if raw.empty:
        raise RuntimeError("no prices at all")

    # 必須列の存在を保証
    need = {"Open", "Close", "Ticker"}
    if not need.issubset(set(raw.columns)):
        raise RuntimeError(f"missing columns: {need - set(raw.columns)}")

    # 銘柄ごとの基準（最初の Open）
    def _pct(df_one: pd.DataFrame) -> pd.Series:
        first_open = df_one["Open"].dropna().iloc[:1]
        if first_open.empty or not np.isfinite(first_open.iloc[0]):
            return pd.Series(dtype=float)
        base = float(first_open.iloc[0])
        # Close ベースで % 変化
        s = (df_one["Close"].astype(float) / base - 1.0) * 100.0
        s.name = df_one["Ticker"].iloc[0]
        return s

    pts = []
    for t, df1 in raw.groupby("Ticker"):
        s = _pct(df1)
        if not s.empty:
            pts.append(s)

    if not pts:
        raise RuntimeError("no valid series after cleaning")

    mat = pd.concat(pts, axis=1).sort_index()
    # 等金額平均（列方向の平均）
    avg = mat.mean(axis=1, skipna=True)
    # 不要に広いギャップを掃除（NaN は前方補完）
    avg = avg.ffill().dropna()
    if avg.empty:
        raise RuntimeError("no prices after ffill")
    return avg

def save_outputs(series: pd.Series, tickers: List[str]) -> None:
    series = series.copy()
    series.name = "ret"
    csv_path = f"{OUT_DIR}/hinosemi_intraday.csv"
    series.to_frame().to_csv(csv_path, index_label="datetime_jst")

    # 統計 / 投稿文
    last_pct = float(series.iloc[-1])
    stats = {
        "key": KEY,
        "pct_intraday": round(last_pct, 2),
        "updated_at": datetime.now(tz=pd.Timestamp.now(tz="Asia/Tokyo").tz).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(f"{OUT_DIR}/hinosemi_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/last_run.txt", "w", encoding="utf-8") as f:
        f.write(datetime.now(tz=pd.Timestamp.now(tz="Asia/Tokyo").tz).strftime("%Y/%m/%d %H:%M:%S"))

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
        # 取得 API 側の瞬断などで起こりうる
        raise RuntimeError("no prices at all")

    series = build_intraday_series(raw)
    save_outputs(series, tickers)

if __name__ == "__main__":
    main()
