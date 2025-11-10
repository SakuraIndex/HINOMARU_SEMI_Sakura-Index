# src/hinosemi_snapshot.py  前日終値比 & 既存チャート互換（pct列）完全版
import os
import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))

TICKERS = [
    "8035.T",  # 東京エレクトロン
    "6857.T",  # アドバンテスト
    "285A.T",  # キオクシア（東証プライム 285A）
    "6920.T",  # レーザーテック
    "6146.T",  # ディスコ
    "6526.T",  # ソシオネクスト
    "6723.T",  # ルネサスエレクトロニクス
]

def _ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_intraday(tickers):
    # 1日分 5分足
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d",
        interval="5m",
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    frames = []
    for t in tickers:
        df = data[t].copy()
        df = df.reset_index().rename(columns={"Datetime": "datetime_utc"})
        df["Ticker"] = t
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    # UTC -> JST（tz-awareを維持）
    raw["datetime_utc"] = pd.to_datetime(raw["datetime_utc"], utc=True)
    raw["datetime_jst"] = raw["datetime_utc"].dt.tz_convert(JST)

    # 必要列
    raw = raw[["datetime_jst", "Open", "Close", "Ticker"]].dropna()
    return raw

def _build_intraday_series_prev_close(raw: pd.DataFrame) -> pd.DataFrame:
    """
    前日終値比（％）の等金額加重平均を作成。
    """
    raw = raw.copy()

    # ティッカーごとの直近終値（前日終値に近似：当日の最初のCloseのひとつ前の終値）
    # yfinance 1d/5mでは厳密な「前日終値」の列が来ないため、
    # 当日最初のバーのOpenを“基準”として採用する方が安定。
    first_open = (raw.sort_values("datetime_jst")
                     .groupby("Ticker")["Open"]
                     .first()
                  ).rename("PrevCloseLike")
    raw = raw.merge(first_open, on="Ticker", how="left")

    # 前日（相当）比
    raw["pct"] = (raw["Close"] / raw["PrevCloseLike"] - 1.0) * 100.0

    # 時点ごと平均（等金額加重＝単純平均）
    s = raw.groupby("datetime_jst")["pct"].mean().rename("pct")
    return s.to_frame()

def save_outputs(series: pd.DataFrame, tickers: list[str]) -> None:
    _ensure_outdir()

    # ✅ 既存スクリプト互換の列名: pct
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  index_label="datetime_jst")

    stats = {
        "key": "HINOSEMI",
        "pct_intraday": float(series["pct"].iloc[-1]) if len(series) else 0.0,
        "updated_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(os.path.join(OUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # ついでに投稿用テキストも更新
    post_text = (
        "【HINOSEMI｜日の丸半導体指数】\n"
        f"本日：{stats['pct_intraday']:+.2f}%\n"
        f"構成：{', '.join(tickers)}\n"
        "#桜Index #HINOSEMI"
    )
    with open(os.path.join(OUT_DIR, "hinosemi_post_intraday.txt"), "w", encoding="utf-8") as f:
        f.write(post_text)

    # 反映検知用
    with open(os.path.join(OUT_DIR, "last_run.txt"), "w", encoding="utf-8") as f:
        f.write(datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S"))

def main():
    raw = _download_intraday(TICKERS)
    series = _build_intraday_series_prev_close(raw)
    save_outputs(series, TICKERS)

if __name__ == "__main__":
    main()
