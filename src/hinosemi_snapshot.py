# src/hinosemi_snapshot.py
from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import yfinance as yf
from pathlib import Path

OUT_DIR = Path("docs/outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ✅ 正規メンバーを固定（順序も固定）
MEMBERS = [
    "8035.T",  # 東京エレクトロン
    "6857.T",  # アドバンテスト
    "285A.T",  # キオクシア
    "6920.T",  # レーザーテック
    "6146.T",  # ディスコ
    "6526.T",  # ソシオネクスト
    "6723.T",  # ルネサス
]

def _now_jst():
    return datetime.now(timezone(timedelta(hours=9)))

def _download_intraday(tickers: list[str]) -> pd.DataFrame:
    # 1分足/当日分に相当する履歴を取得（なくても NaN で返る）
    data = yf.download(
        tickers=tickers,
        interval="1m",
        period="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    # yfinance の戻りをフラット化: (Datetime, Ticker) の MultiIndex に統一
    frames = []
    for t in tickers:
        # 取得できない銘柄は空→落ちないように握りつぶす
        if (t in data) and ("Open" in data[t]) and ("Close" in data[t]):
            df_t = data[t][["Open", "Close"]].copy()
            df_t.columns = pd.MultiIndex.from_product([[t], df_t.columns])
            frames.append(df_t)
    if not frames:
        # 何も取れない場合でも後段が落ちないように空の DataFrame を返す
        return pd.DataFrame(columns=pd.MultiIndex.from_product([tickers, ["Open","Close"]]))

    df = pd.concat(frames, axis=1).sort_index()
    return df

def build_intraday_series() -> pd.DataFrame:
    raw = _download_intraday(MEMBERS)

    # Open/Close をピボットしやすい形へ
    # index: Datetime, columns: (Ticker, Field)
    df = raw.copy()
    # Open が 0 や NaN は除外（割り算回避）
    open_ = df.xs("Open", axis=1, level=1)
    close_ = df.xs("Close", axis=1, level=1)
    pct_vs_open = (close_ - open_) / open_
    # 列は Ticker、index は Datetime
    pct_vs_open.index.name = "datetime"

    # 今日日中（JST）に絞る（なくても可）
    jst = _now_jst()
    today_jst = jst.date()
    pct_vs_open = pct_vs_open[pct_vs_open.index.tz_localize(None).date == today_jst]

    # 可視化・CSV 用に保存
    return pct_vs_open

def save_outputs(pct: pd.DataFrame):
    # CSV（可視化用デバッグ）
    csv_path = OUT_DIR / "hinosemi_intraday.csv"
    pct.to_csv(csv_path, index_label="datetime_jst")

    # 統計（ポスト文やダッシュボード用）
    last_pct = float(pct.iloc[-1].mean()) if (len(pct) > 0) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": round(last_pct * 100, 2),
        "updated_at": _now_jst().strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        # ✅ ここを“取得できた列”ではなく、必ず正規メンバーで書き出す
        "tickers": MEMBERS,
    }
    (OUT_DIR / "hinosemi_stats.json").write_text(
        pd.io.json.dumps(stats, force_ascii=False, indent=2)
    )

def main():
    pct = build_intraday_series()
    save_outputs(pct)

if __name__ == "__main__":
    main()
