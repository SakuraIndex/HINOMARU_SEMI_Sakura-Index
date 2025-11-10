# src/hinosemi_snapshot.py  前日終値比・等金額加重（5分足）安定版
import os
import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))

# 等金額加重・日本株7銘柄
TICKERS = [
    "8035.T",   # 東京エレクトロン
    "6857.T",   # アドバンテスト
    "285A.T",   # キオクシア
    "6920.T",   # レーザーテック
    "6146.T",   # ディスコ
    "6526.T",   # ソシオネクスト
    "6723.T",   # ルネサスエレクトロニクス
]


# ---------- helpers ----------
def _ensure_outdir() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def _today_jst_date(dt_utc: pd.Timestamp) -> pd.Timestamp:
    """
    与えられたUTCタイムスタンプから JST の「日付」を返す。
    """
    return dt_utc.tz_convert(JST).normalize()


def _download_2d_5m(tickers: list[str]) -> pd.DataFrame:
    """
    前日終値を得るために 2日分×5分足を取得し、縦に連結して返す。
    返り値:
        columns: [Open, Close, ... , Ticker]
        index: tz-aware(UTC) DatetimeIndex
    """
    data = yf.download(
        tickers=" ".join(tickers),
        period="2d",            # ← 前日を含める
        interval="5m",
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    frames = []
    for t in tickers:
        df = data[t].copy()
        df = df.reset_index()                    # Datetime 列を出す
        # yfinance は tz-aware(UTC) の Datetime を返すので tz_convert を使う
        df["datetime_utc"] = pd.to_datetime(df["Datetime"]).dt.tz_convert("UTC")
        df["Ticker"] = t
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    # 必要カラムだけ
    out = out[["datetime_utc", "Open", "Close", "Ticker"]].dropna()
    return out


def _build_intraday_series_vs_prevclose(raw: pd.DataFrame) -> pd.DataFrame:
    """
    当日（JST）部分のみ取り出し、
    各銘柄の「前日終値」基準の騰落率(%)を算出して等金額平均する。
    返り値: DataFrame(index: datetime_jst[5m], columns: ['pct'])
    """
    if raw.empty:
        return pd.DataFrame(columns=["pct"])

    # UTC → JST に変換（tz-aware のまま）
    raw = raw.copy()
    raw["datetime_jst"] = pd.to_datetime(raw["datetime_utc"]).dt.tz_convert(JST)
    raw["date_jst"] = raw["datetime_jst"].dt.normalize()

    # 当日の JST 日付を決める（データの最大時刻から推定）
    max_utc = pd.to_datetime(raw["datetime_utc"]).max()
    today_jst = _today_jst_date(max_utc)  # 00:00 JST

    # 前日終値を銘柄ごとに取り出す
    prev_close_map = (
        raw[raw["date_jst"] < today_jst]
        .sort_values(["Ticker", "datetime_jst"])
        .groupby("Ticker")["Close"]
        .last()
    )
    # 当日データだけ
    today = raw[raw["date_jst"] >= today_jst].copy()

    # 前日終値が欠ける銘柄は落とす（上場初日など）
    today = today.merge(
        prev_close_map.rename("prev_close"),
        on="Ticker",
        how="inner",
    )
    # 前日終値比（%）
    today["pct"] = (today["Close"] / today["prev_close"] - 1.0) * 100.0

    # 5分刻みの等金額平均
    series = (
        today.groupby("datetime_jst")["pct"]
        .mean()
        .sort_index()
        .to_frame()
    )
    return series


def _save_csv(series: pd.DataFrame) -> None:
    """
    チャートスクリプトが参照するCSV。
    index: datetime_jst, column: pct
    """
    _ensure_outdir()
    path = os.path.join(OUT_DIR, "hinosemi_intraday.csv")
    series.to_csv(path, index_label="datetime_jst")


def _save_stats(series: pd.DataFrame, tickers: list[str]) -> None:
    """
    ダッシュボードやポスト作成で使う stats.json。
    """
    last_pct = float(series["pct"].iloc[-1]) if len(series) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": last_pct,                          # ← 単位は % 値（そのまま）
        "updated_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(os.path.join(OUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def main() -> None:
    raw = _download_2d_5m(TICKERS)
    series = _build_intraday_series_vs_prevclose(raw)
    _save_csv(series)
    _save_stats(series, TICKERS)


if __name__ == "__main__":
    main()
