# scripts/make_intraday_chart.py
# intraday CSV から％列を安全に選び、PNGを生成します。
import os
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


OUT_DIR = Path("docs/outputs")
PNG_NAME = "hinosemi_intraday.png"


def _load_intraday_csv() -> pd.DataFrame:
    # リポ内の *_intraday.csv を優先して取得
    cand = sorted(p for p in OUT_DIR.glob("*_intraday.csv"))
    if not cand:
        raise FileNotFoundError("intraday csv not found under docs/outputs")
    df = pd.read_csv(cand[0], parse_dates=["datetime_jst"])
    df = df.set_index("datetime_jst")
    # index を tz-naive のままでも可。表示だけなので OK
    return df


def _pick_pct(df: pd.DataFrame) -> pd.Series:
    """
    互換のため下記いずれかを許容:
      - pct（推奨エイリアス）
      - pct_vs_prevclose（前日終値比）
      - pct_vs_open（寄り比・旧仕様）
    """
    for col in ("pct", "pct_vs_prevclose", "pct_vs_open"):
        if col in df.columns:
            return df[col].astype(float)
    raise RuntimeError("pct column not found")


def _plot(y: pd.Series, title: str) -> None:
    plt.figure(figsize=(12, 6), dpi=120)
    ax = plt.gca()
    ax.set_facecolor("#0a1622")
    plt.plot(y.index, y.values, linewidth=2)
    # ゼロ基準より上を塗る
    ax.fill_between(y.index, 0, y.values, where=(y.values >= 0), alpha=0.25)
    ax.axhline(0.0, linewidth=1, alpha=0.5)

    ax.set_title(title, fontsize=14)
    ax.set_ylabel("Change vs Prev Close (%)")
    ax.set_xlabel("")

    # 余白＆枠線控えめ
    for spine in ax.spines.values():
        spine.set_alpha(0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / PNG_NAME)
    plt.close()


def main():
    df = _load_intraday_csv()
    y = _pick_pct(df).dropna()
    if y.empty:
        raise RuntimeError("no data to draw")
    _plot(y, "HINOSEMI Intraday Snapshot (JST)")


if __name__ == "__main__":
    main()
