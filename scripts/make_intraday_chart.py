# -*- coding: utf-8 -*-
"""
Intraday chart builder for HINOMARU_SEMI index.
- reads docs/outputs/hinosemi_intraday.csv
- accepts column names: ['ret', 'pct', 'pct_vs_open', 'change']
- dark theme, color by sign, area fill
- saves docs/outputs/hinosemi_intraday.png
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

CSV = Path("docs/outputs/hinosemi_intraday.csv")
PNG = Path("docs/outputs/hinosemi_intraday.png")

def load_series() -> pd.Series:
    if not CSV.exists():
        raise FileNotFoundError(f"not found: {CSV}")
    df = pd.read_csv(CSV, index_col=0, parse_dates=True)

    # 許容する候補列
    candidates = ["ret", "pct", "pct_vs_open", "change", "value"]
    col = next((c for c in candidates if c in df.columns), None)
    if col is None:
        raise KeyError(f"none of columns {candidates} are present in {CSV.name}: {list(df.columns)}")

    s = pd.to_numeric(df[col], errors="coerce").dropna()
    s.name = "pct"
    # index は JST 文字列の場合があるので to_datetime で吸収
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()]
    return s

def plot_intraday(s: pd.Series) -> None:
    last = float(s.iloc[-1])
    up = last >= 0
    line_color = "#24d5db" if up else "#ff6b6b"
    fill_color = "#1a9ba7" if up else "#a83b4a"   # 少し暗め

    # ダークテーマ
    plt.style.use("default")
    plt.rcParams.update({
        "figure.facecolor": "#0e1726",
        "axes.facecolor":   "#0e1726",
        "savefig.facecolor":"#0e1726",
        "axes.edgecolor":   "#334155",
        "axes.labelcolor":  "#cbd5e1",
        "xtick.color":      "#94a3b8",
        "ytick.color":      "#94a3b8",
        "grid.color":       "#334155",
    })

    fig, ax = plt.subplots(figsize=(16, 9), dpi=140)
    ax.plot(s.index, s.values, linewidth=2.2, color=line_color)
    ax.fill_between(s.index, 0, s.values, alpha=0.25, color=fill_color)

    ax.axhline(0, linewidth=1, color="#475569", alpha=0.8)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.set_ylabel("Change vs Open (%)")

    # タイトル（JST想定）
    dstr = s.index[-1].strftime("%Y/%m/%d")
    ax.set_title(f"HINOSEMI Intraday Snapshot ({dstr} JST)", color="#e2e8f0", fontsize=16, pad=12)

    # 余白調整
    fig.tight_layout()
    PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG)
    plt.close(fig)

def main():
    s = load_series()
    if s.empty:
        raise RuntimeError("empty series to plot")
    plot_intraday(s)

if __name__ == "__main__":
    main()
