# scripts/make_intraday_chart.py
# HINOSEMI intraday chart (dark theme, unified with other indexes)

import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from datetime import timezone

OUT_DIR = "docs/outputs"
CSV_PATH = os.path.join(OUT_DIR, "hinosemi_intraday.csv")
PNG_PATH = os.path.join(OUT_DIR, "hinosemi_intraday.png")

TITLE_KEY = "HINOSEMI"

def _pick_datetime(df: pd.DataFrame) -> pd.Series:
    # 可能性のある日時カラムを順に探索
    for c in ["datetime_jst", "datetime", "time", "Date"]:
        if c in df.columns:
            return pd.to_datetime(df[c], utc=False, errors="coerce")
    # インデックスが日時ならそれを使う
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index.tz_localize(None)
    raise RuntimeError("datetime column not found")

def _pick_pct(df: pd.DataFrame) -> pd.Series:
    # 既定（他指数と同じ）: pct_vs_open（単位は%）
    for c in ["pct_vs_open", "retail7_pct", "qbit5_pct", "pct", "change_pct"]:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            return s
    # 終値から当日騰落率を再計算（万一のバックアップ）
    if {"Open", "Close"}.issubset(df.columns):
        open0 = pd.to_numeric(df["Open"], errors="coerce").replace(0, pd.NA).iloc[0]
        close = pd.to_numeric(df["Close"], errors="coerce")
        s = (close / open0 - 1.0) * 100.0
        return s
    raise RuntimeError("pct column not found")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    # 日時＆%列を特定
    t = _pick_datetime(df)
    y = _pick_pct(df)

    # 整形
    msk = (~t.isna()) & (~y.isna())
    t, y = t[msk], y[msk]
    if len(y) == 0:
        raise RuntimeError("no intraday points to plot")

    last_pct = float(y.iloc[-1])

    # ======== 描画（他指数と統一）========
    # 背景（濃紺/黒）
    fig, ax = plt.subplots(figsize=(15, 8), dpi=180)
    fig.patch.set_facecolor("#0b1117")
    ax.set_facecolor("#0e171f")

    # 線色：上昇=シアン、下落=ピンク
    up_color = "#7efcff"
    down_color = "#ff7fbf"
    line_color = up_color if last_pct >= 0 else down_color

    ax.plot(t, y, lw=2.2, color=line_color, solid_capstyle="round", antialiased=True)
    # ゼロ基準で塗りつぶし
    ax.fill_between(t, 0, y, where=(y >= 0), interpolate=True, color=up_color, alpha=0.12)
    ax.fill_between(t, 0, y, where=(y < 0),  interpolate=True, color=down_color, alpha=0.12)

    # 目盛り・軸
    ax.grid(True, color="#1b2a35", alpha=0.35, linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#445664")

    ax.tick_params(colors="#c9d1d9", labelsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.1f}%"))
    ax.set_ylabel("Change vs Open (%)", color="#c9d1d9", labelpad=10)

    # タイトル（JST 表示）
    # tの最終日付から日付文字列を作成
    date_str = pd.to_datetime(t.iloc[-1]).strftime("%Y/%m/%d")
    ax.set_title(f"{TITLE_KEY} Intraday Snapshot (JST)\n{date_str}",
                 color="#e6edf3", fontsize=16, pad=12, loc="center")

    # 余白調整・保存
    plt.tight_layout()
    plt.savefig(PNG_PATH, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)

if __name__ == "__main__":
    main()
