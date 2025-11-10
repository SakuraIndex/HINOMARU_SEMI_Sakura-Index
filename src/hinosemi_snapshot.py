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
    data = yf.download(
        tickers=tickers, interval="1m", period="1d",
        group_by="ticker", auto_adjust=False, threads=True, progress=False
    )

    frames = []
    for t in tickers:
        if (t in data) and ("Open" in data[t]) and ("Close" in data[t]):
            df_t = data[t][["Open", "Close"]].copy()
            df_t.columns = pd.MultiIndex.from_product([[t], df_t.columns])
            frames.append(df_t)

    if not frames:
        # 何も取れない場合も後段で落ちないよう空の形を返す
        cols = pd.MultiIndex.from_product([tickers, ["Open", "Close"]])
        return pd.DataFrame(columns=cols)

    df = pd.concat(frames, axis=1).sort_index()
    return df

def build_intraday_series() -> pd.DataFrame:
    raw = _download_intraday(MEMBERS)
    open_ = raw.xs("Open", axis=1, level=1)
    close_ = raw.xs("Close", axis=1, level=1)

    # 0/NaN を除外して割り算回避
    open_ = open_.replace(0, np.nan)
    pct_vs_open = (close_ - open_) / open_
    pct_vs_open.index.name = "datetime"

    # JST 当日だけに絞る（任意）
    today = _now_jst().date()
    pct_vs_open = pct_vs_open[pct_vs_open.index.tz_localize(None).date == today]
    return pct_vs_open

def save_outputs(pct: pd.DataFrame):
    # CSV（任意）
    pct.to_csv(OUT_DIR / "hinosemi_intraday.csv", index_label="datetime_jst")

    last_pct = float(pct.iloc[-1].mean()) if len(pct) > 0 else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": round(last_pct * 100, 2),
        "updated_at": _now_jst().strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        # ✅ 取得成否に関わらず固定メンバーを書き出し
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
