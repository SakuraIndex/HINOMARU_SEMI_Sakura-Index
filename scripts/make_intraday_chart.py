import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

OUTPUT_DIR = "docs/outputs"
CSV = os.path.join(OUTPUT_DIR, "hinosemi_intraday.csv")
PNG = os.path.join(OUTPUT_DIR, "hinosemi_intraday.png")

def main():
    df = pd.read_csv(CSV, index_col=0, parse_dates=True)
    s = df["pct_vs_open"].dropna()

    # 配色：上昇系はシアン、下落優勢時はサーモン系に（線色のみ切替）
    is_up = s.iloc[-1] >= 0
    line_color = "#8BE9FD" if is_up else "#FCA5A5"
    area_color = "#0ea5ac33" if is_up else "#ef444433"

    plt.figure(figsize=(12, 6), dpi=140)
    ax = plt.gca()
    ax.set_facecolor("#0b1420")
    plt.gcf().patch.set_facecolor("#0b1420")

    s.plot(ax=ax, lw=2, color=line_color)
    ax.fill_between(s.index, 0, s.values, alpha=0.25, color=area_color)

    ax.set_title(f"Hinomaru Semi Intraday Snapshot ({datetime.now().strftime('%Y/%m/%d (JST)')})",
                 color="#d4e9f7", fontsize=14, pad=12)
    ax.set_ylabel("Change vs Open (%)", color="#b7c2ca")
    ax.tick_params(colors="#9fb6c7")
    for spine in ax.spines.values():
        spine.set_color("#1c2a3a")

    plt.tight_layout()
    plt.savefig(PNG, bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    main()
