# src/hinosemi_snapshot.py  修正完全版
import os
import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))

TICKERS = [
    "8035.T",   # 東京エレクトロン
    "6857.T",   # アドバンテスト
    "285A.T",   # キオクシア
    "6920.T",   # レーザーテック
    "6146.T",   # ディスコ
    "6526.T",   # ソシオネクスト
    "6723.T",   # ルネサスエレクトロニクス
]

# ---- helpers ---------------------------------------------------------------

def _ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def _as_jst_today(dt_utc: pd.Timestamp) -> pd.Timestamp:
    """与えられた時刻のJST日付（00:00 JST）を返す"""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.tz_localize("UTC")
    jst = dt_utc.tz_convert("Asia/Tokyo")
    jst_midnight = pd.Timestamp(jst.date(), tz="Asia/Tokyo")
    return jst_midnight

def _download_intraday(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    各ティッカーの分足 DataFrame を返す。
    index: tz-aware(UTC) → のちにJSTへ変換
    columns: ['Open','Close'] だけあればOK
    """
    # 1分足だと落ちやすい場合は "5m" に下げてもOK
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
    for t in tickers:
        if t not in data.columns.get_level_values(0) and t not in data.columns:
            # yfinance 側の欠落
            continue
        try:
            # group_by="ticker" で返る形を想定
            df = data[t].copy()
        except Exception:
            # 単一銘柄形式の返りの場合などに備えるフォールバック
            df = data.copy()

        if df.empty:
            continue

        # 列の正規化
        cols = {c.lower(): c for c in df.columns}
        if "open" not in cols or "close" not in cols:
            # 取得失敗（出来高のみ等）のときはスキップ
            continue
        df = df[[cols["open"], cols["close"]]].rename(columns={cols["open"]:"Open", cols["close"]:"Close"})

        # index を tz-aware UTC に
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")

        out[t] = df

    return out

def _first_valid_open(df_jst: pd.DataFrame) -> float | None:
    """JST 09:00〜09:10 の最初の有効ティックを基準始値とする"""
    win = df_jst.between_time("09:00", "09:10")
    # Open が欠損なら Close を利用
    base = win["Open"].dropna()
    if base.empty:
        base = win["Close"].dropna()
    if base.empty:
        return None
    v = float(base.iloc[0])
    return v if v > 0 else None

def _build_intraday_series(minute_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    minute_map: {ticker: df(UTC, ['Open','Close'])}
    返り値: DataFrame(index=JST分足, columns=['pct_vs_open']), 単位は %
    """
    if not minute_map:
        return pd.DataFrame(columns=["pct_vs_open"], dtype=float)

    now_utc = pd.Timestamp.utcnow().tz_localize("UTC")
    today_jst_00 = _as_jst_today(now_utc)
    lo = today_jst_00 + pd.Timedelta(hours=9)   # 09:00
    hi = today_jst_00 + pd.Timedelta(hours=15)  # 15:00

    per_ticker = []

    for tkr, df in minute_map.items():
        if df.empty:
            continue
        # UTC → JST
        df = df.tz_convert("Asia/Tokyo").sort_index()
        # 当日 09:00〜15:00 に限定
        df = df.loc[(df.index >= lo) & (df.index <= hi)]
        if df.empty:
            continue

        base = _first_valid_open(df)
        if base is None:
            # 当日寄りの有効ティックが取れない場合は除外
            continue

        r = (df["Close"] / base - 1.0) * 100.0   # 単位: %
        r.name = tkr
        per_ticker.append(r)

    if not per_ticker:
        return pd.DataFrame(columns=["pct_vs_open"], dtype=float)

    wide = pd.concat(per_ticker, axis=1)  # 列=銘柄, 行=時刻, NaNはNaNのまま
    # 有効銘柄のみで算術平均（欠損を 0 で埋めない）
    min_count = max(1, int(np.ceil(0.6 * wide.shape[1])))  # カバレッジ60%以上の時刻のみ
    valid = (wide.count(axis=1) >= min_count)
    idx_pct = wide.mean(axis=1, skipna=True).where(valid)

    # 軽いスムージング（3分の移動中央値）※形状安定化・遅延最小
    idx_pct = idx_pct.rolling(3, min_periods=1, center=True).median()

    # 欠番は前方補間（先頭は埋めない）
    idx_pct = idx_pct.ffill()

    return idx_pct.to_frame(name="pct_vs_open")

def save_outputs(series: pd.DataFrame, tickers: list[str]) -> None:
    _ensure_outdir()
    # CSV（可視化やデバッグ用）
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  index_label="datetime_jst")
    # 統計JSON（ダッシュボードなどで利用）
    last_val = float(series["pct_vs_open"].dropna().iloc[-1]) if len(series) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": last_val,  # 単位: %
        "updated_at": datetime.now(JST).strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": tickers,
    }
    with open(os.path.join(OUT_DIR, "hinosemi_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def main():
    minute_map = _download_intraday(TICKERS)
    series = _build_intraday_series(minute_map)
    if series.empty:
        raise RuntimeError("no prices for today (JST)")
    save_outputs(series, TICKERS)

if __name__ == "__main__":
    main()
