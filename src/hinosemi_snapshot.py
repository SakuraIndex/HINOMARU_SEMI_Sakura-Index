# src/hinosemi_snapshot.py  修正完全版（tzエラー対応・堅牢化）
import os
import json
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = "docs/outputs"
JST = timezone(timedelta(hours=9))
JST_TZNAME = "Asia/Tokyo"

TICKERS = [
    "8035.T",   # 東京エレクトロン
    "6857.T",   # アドバンテスト
    "285A.T",   # キオクシア
    "6920.T",   # レーザーテック
    "6146.T",   # ディスコ
    "6526.T",   # ソシオネクスト
    "6723.T",   # ルネサスエレクトロニクス
]

# ---------------------------------------------------------------------------

def _ensure_outdir():
    os.makedirs(OUT_DIR, exist_ok=True)

def _download_intraday(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    各ティッカーの分足 DataFrame を返す（UTC index, ['Open','Close']）。
    """
    data = yf.download(
        tickers=" ".join(tickers),
        period="1d",
        interval="1m",          # 必要に応じて "5m" でもOK
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    out: dict[str, pd.DataFrame] = {}

    # yfinance は複数ティッカーだと MultiIndex で返るのが基本
    if isinstance(data.columns, pd.MultiIndex):
        for t in tickers:
            if t not in data.columns.get_level_values(0):
                continue
            df = data[t].copy()
            if df.empty:
                continue

            cols = {c.lower(): c for c in df.columns}
            if "open" not in cols or "close" not in cols:
                continue

            df = df[[cols["open"], cols["close"]]].rename(columns={
                cols["open"]: "Open",
                cols["close"]: "Close",
            })

            # index を tz-aware UTC に正規化
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")

            out[t] = df
    else:
        # 単一ティッカー構造（想定外だが一応対応）
        cols = {c.lower(): c for c in data.columns}
        if "open" in cols and "close" in cols:
            df = data[[cols["open"], cols["close"]]].rename(columns={
                cols["open"]: "Open",
                cols["close"]: "Close",
            })
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
            # どの銘柄か不明になるので 1 件目にマップ
            out[tickers[0]] = df

    return out

def _first_valid_open(df_jst: pd.DataFrame) -> float | None:
    """JST 09:00〜09:10 の最初の有効ティックを基準始値にする。"""
    win = df_jst.between_time("09:00", "09:10")
    base = win["Open"].dropna()
    if base.empty:
        base = win["Close"].dropna()
    if base.empty:
        return None
    v = float(base.iloc[0])
    return v if np.isfinite(v) and v > 0 else None

def _build_intraday_series(minute_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    minute_map: {ticker: df(UTC, ['Open','Close'])}
    戻り: DataFrame(index=JST分足, columns=['pct_vs_open'])  単位: %
    """
    if not minute_map:
        return pd.DataFrame(columns=["pct_vs_open"], dtype=float)

    # ★ tz を最初から指定して生成（tz_localize不要）
    now_utc = pd.Timestamp.now(tz="UTC")

    # 当日JSTの 00:00 を求める
    now_jst = now_utc.tz_convert(JST_TZNAME)
    jst_midnight = pd.Timestamp(now_jst.date(), tz=JST_TZNAME)
    lo = jst_midnight + pd.Timedelta(hours=9)   # 09:00
    hi = jst_midnight + pd.Timedelta(hours=15)  # 15:00

    per_ticker = []

    for tkr, df in minute_map.items():
        if df.empty:
            continue
        # UTC → JST
        df = df.tz_convert(JST_TZNAME).sort_index()
        # 当日 09:00〜15:00 に限定
        df = df.loc[(df.index >= lo) & (df.index <= hi)]
        if df.empty:
            continue

        base = _first_valid_open(df)
        if base is None:
            continue

        r = (df["Close"] / base - 1.0) * 100.0   # 単位: %
        r.name = tkr
        per_ticker.append(r)

    if not per_ticker:
        return pd.DataFrame(columns=["pct_vs_open"], dtype=float)

    wide = pd.concat(per_ticker, axis=1)  # 列=銘柄, 行=時刻
    # 有効銘柄のみで平均（欠損を 0 扱いしない）
    min_count = max(1, int(np.ceil(0.6 * wide.shape[1])))  # カバレッジ60%以上を採用
    valid = (wide.count(axis=1) >= min_count)
    idx_pct = wide.mean(axis=1, skipna=True).where(valid)

    # 軽いスムージング（3分移動中央値）でトゲを抑制
    idx_pct = idx_pct.rolling(3, min_periods=1, center=True).median()

    # 欠番は前方補間（先頭は埋めない）
    idx_pct = idx_pct.ffill()

    return idx_pct.to_frame(name="pct_vs_open")

def save_outputs(series: pd.DataFrame, tickers: list[str]) -> None:
    _ensure_outdir()
    # CSV（可視化・検証用）
    series.to_csv(os.path.join(OUT_DIR, "hinosemi_intraday.csv"),
                  index_label="datetime_jst")
    # 統計JSON（サイト側で%表示に利用）
    last_val = float(series["pct_vs_open"].dropna().iloc[-1]) if len(series) else 0.0
    stats = {
        "key": "HINOSEMI",
        "pct_intraday": last_val,  # %
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
