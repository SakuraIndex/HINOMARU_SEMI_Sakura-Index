# scripts/make_intraday_chart.py
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timezone, timedelta

OUT_DIR = "docs/outputs"
CSV = os.path.join(OUT_DIR, "hinosemi_intraday.csv")
PNG = os.path.join(OUT_DIR, "hinosemi_intraday.png")
JST = timezone(timedelta(hours=9))

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(CSV, parse_dates=["datetime_jst"])
    if df.empty:
        raise RuntimeError("hinosemi_intraday.csv is empty")

    # 1本時系列（等金額加重の平均を snapshot 側で出力）を期待
    # CSV は index_label=datetime_jst, 列に pct_vs_open がある想定
    # snapshot 完全版では DataFrame to_csv なので列名は 'pct_vs_open'
    s = df.set_index("datetime_jst")["pct_vs_open"]

    # プロット（黒ベース・上昇で明るめ、下落で暗め…は単色線でOK）
    plt.figure(figsize=(14, 6), dpi=180)
    ax = plt.gca()
    ax.set_facecolor("#0b1723")
    plt.plot(s.index, s.values, linewidth=2)

    # 0%を横ライン、背景シェード
    plt.axhline(0, linewidth=1, alpha=0.5)
    ymin, ymax = min(s.min(), -0.1), max(s.max(), 0.1)
    plt.fill_between(s.index, 0, s.values, alpha=0.25)

    plt.title("HINOSEMI Intraday Snapshot (JST)")
    plt.xlabel("")
    plt.ylabel("Change vs Open (%)")
    plt.tight_layout()
    plt.savefig(PNG)
    plt.close()

if __name__ == "__main__":
    main()
