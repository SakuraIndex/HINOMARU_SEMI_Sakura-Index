import os
import io
from datetime import datetime, timedelta, timezone
import pytz
import json
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# ---------- 基本設定 ----------
OUTPUT_DIR = "docs/outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

JST = pytz.timezone("Asia/Tokyo")
UTC = pytz.UTC

# 構成銘柄：7銘柄（キオクシアを追加）
TICKERS = {
    "8035.T": "東京エレクトロン",
    "6857.T": "アドバンテスト",
    "6920.T": "レーザーテック",
    "6146.T": "ディスコ",
    "6526.T": "ソシオネクスト",
    "6723.T": "ルネサスエレクトロニクス",
    "285A.T": "キオクシア",   # 2024-12-18 東証プライム上場
}
TICKER_LIST = list(TICKERS.keys())

INDEX_KEY = "HINOSEMI"
BASE_LEVEL = 1000.0
# BASE_DATE より後で “全銘柄に値がある最初の日” を起点に自動リベースされます
BASE_DATE = "2023-01-02"

# ---------- ユーティリティ ----------
def now_jst_str():
    return datetime.now(JST).strftime("%Y/%m/%d %H:%M")

def today_jst_dates():
    now = datetime.now(JST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end

def fetch_daily(start="2022-09-01"):
    df = yf.download(TICKER_LIST, start=start, auto_adjust=True, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    return df

def equal_weight_level_from_close(df_close: pd.DataFrame) -> pd.Series:
    df_close = df_close.dropna(how="all")
    # BASE_DATE 以降で「全銘柄が揃っている最初の行」を起点にする
    df_beg = df_close[df_close.index >= BASE_DATE]
    if df_beg.empty:
        df_beg = df_close
    # 全銘柄そろった最初の1行（欠損を含む行は除外）
    first_valid = df_beg.dropna(how="any")
    if first_valid.empty:
        # 念のためのフォールバック：列ごとに前方埋めしてから再評価
        df_beg = df_beg.ffill()
        first_valid = df_beg.dropna(how="any")
    first_row = first_valid.iloc[0]
    # 正規化 → 等金額平均 → レベル化
    norm = df_close.divide(first_row)
    level = norm.mean(axis=1) * BASE_LEVEL
    return level

def fetch_intraday_today():
    jst_start, jst_end = today_jst_dates()
    intraday = {}
    for t in TICKER_LIST:
        try:
            # 直近2日・1分足（UTC索引）→ JST へ
            df = yf.download(t, period="2d", interval="1m", auto_adjust=True, progress=False)
            if df.empty:
                continue
            df = df.tz_localize(UTC).tz_convert(JST)
            df_today = df[(df.index >= jst_start) & (df.index < jst_end)]
            if not df_today.empty:
                intraday[t] = df_today["Close"].copy()
        except Exception:
            pass
    if not intraday:
        return None
    df = pd.DataFrame(intraday).sort_index()
    return df

def index_pct_vs_open(intra_close: pd.DataFrame) -> pd.Series:
    # その日の最初のレコードを「始値」とみなす（銘柄ごと）
    opens = intra_close.iloc[0]
    rel = intra_close.divide(opens)
    level = rel.mean(axis=1)           # 等金額平均
    pct = (level - 1.0) * 100.0
    return pct

# ---------- メイン ----------
def main():
    # 長期レベル（将来の長期PNG用にも使える）
    daily = fetch_daily(start="2022-09-01")
    level = equal_weight_level_from_close(daily)
    last_level = float(level.dropna().iloc[-1]) if not level.dropna().empty else None

    # 日中
    intra = fetch_intraday_today()
    if intra is None or intra.empty:
        raise RuntimeError("no prices at all")

    pct = index_pct_vs_open(intra)

    # CSV
    csv_path = os.path.join(OUTPUT_DIR, "hinosemi_intraday.csv")
    pct.to_csv(csv_path, header=["pct_vs_open"])

    # JSON
    updated = now_jst_str()
    pct_intraday = float(np.round(pct.iloc[-1], 2))
    stats = {
        "key": INDEX_KEY,
        "pct_intraday": pct_intraday,
        "updated_at": updated,
        "unit": "pct",
        "last_level": round(last_level, 2) if last_level is not None else None,
        "base_date": BASE_DATE,
        "tickers": TICKER_LIST,
    }
    with open(os.path.join(OUTPUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # 投稿テキスト（ここでは簡潔にコード列を明示）
    post_lines = [
        "【日の丸半導体指数】",
        f"本日：{pct_intraday:+.2f}%",
        f"指数：{round(last_level,2) if last_level else 'None'}",
        "構成：8035/6857/6920/6146/6526/6723/285A",
        "#桜Index #HinomaruSemi",
    ]
    with open(os.path.join(OUTPUT_DIR, "hinosemi_post_intraday.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(post_lines))

    # last_run
    with open(os.path.join(OUTPUT_DIR, "last_run.txt"), "w", encoding="utf-8") as f:
        f.write(updated + "\n")

if __name__ == "__main__":
    main()
