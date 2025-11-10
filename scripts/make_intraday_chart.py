# scripts/make_intraday_chart.py  完全版
# 既存指数と同じダークテーマ / ゼロ基準の塗り分け / 列名は自動検出（pct 優先）

import os
from datetime import timezone, timedelta, datetime

import pandas as pd
import matplotlib.pyplot as plt

JST = timezone(timedelta(hours=9))
IN_CSV  = "docs/outputs/hinosemi_intraday.csv"   # リポ内パス（ジョブごとに同名想定）
OUT_PNG = "docs/outputs/hinosemi_intraday.png"

# ===== スタイル（既存と同等の見た目） =====
BG      = "#0b1420"
PANEL   = "#0f1b28"
LINE    = "#7ee0f5"
FILL    = "#17303d"    # 上側エリア
FILL_NEG= "#3a2334"    # 下側エリア
GRID    = "#1d3145"
TEXT    = "#d4e9f7"

def _pick_pct(df: pd.DataFrame) -> pd.Series:
    # 優先順位で列を探す
    for c in ["pct", "pct_vs_open", "pct_vs_prev_close", "change_pct", "Change"]:
        if c in df.columns:
            return df[c].astype(float)
    raise RuntimeError("pct column not found")

def main():
    df = pd.read_csv(IN_CSV)
    # インデックス
    idx_name = "datetime_jst" if "datetime_jst" in df.columns else df.columns[0]
    df[idx_name] = pd.to_datetime(df[idx_name], utc=True).dt.tz_convert(JST)

    y = _pick_pct(df)
    t = df[idx_name]

    # ===== 描画 =====
    plt.figure(figsize=(13.5, 7.2), dpi=120)
    ax = plt.gca()
    ax.set_facecolor(PANEL)
    plt.gcf().patch.set_facecolor(BG)

    # 0% 基準線
    ax.axhline(0, color=GRID, linewidth=1)

    # フィル（上側／下側で色を分ける）
    ax.fill_between(t, 0, y, where=(y >= 0), alpha=0.6, facecolor=FILL, linewidth=0)
    ax.fill_between(t, 0, y, where=(y < 0),  alpha=0.6, facecolor=FILL_NEG, linewidth=0)

    # ライン
    ax.plot(t, y, linewidth=2.2, color=LINE)

    # 軸など
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(color=GRID, alpha=0.35, linewidth=0.8, axis="y")

    ax.set_ylabel("Change vs Prev Close (%)", color=TEXT)
    ax.set_xlabel("")
    ax.set_title(
        f"HINOSEMI Intraday Snapshot (JST)\n{datetime.now(JST):%Y/%m/%d}",
        color=TEXT, pad=14, fontsize=16, weight="bold"
    )

    # マージン
    plt.tight_layout()
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    plt.savefig(OUT_PNG, facecolor=BG, edgecolor=BG, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    main()
