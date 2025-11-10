# scripts/make_intraday_chart.py
# 前のデザイン（ダーク背景 + 0%基準の上下塗り分け + 2行タイトル）で intraday.png を描画する
import os
from datetime import timezone, timedelta
import pandas as pd
import matplotlib.pyplot as plt

JST = timezone(timedelta(hours=9))
OUT_DIR = "docs/outputs"

# 環境やリポ名に依らず使えるようにスラグを自動推定
# 例: HINOMARU_SEMI_Sakura-Index -> "hinosemi"
def _guess_slug():
    # docs/outputs 内の *_intraday.csv を1つ見つけてスラグ採用
    if not os.path.isdir(OUT_DIR):
        return "hinosemi"
    cands = [f for f in os.listdir(OUT_DIR) if f.endswith("_intraday.csv")]
    if cands:
        return cands[0].replace("_intraday.csv", "")
    return "hinosemi"

SLUG = _guess_slug().lower()
CSV_PATH = os.path.join(OUT_DIR, f"{SLUG}_intraday.csv")
PNG_PATH = os.path.join(OUT_DIR, f"{SLUG}_intraday.png")

def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"not found: {path}")
    df = pd.read_csv(path)
    # datetime 列の候補（新旧対応）
    for c in ["datetime_jst", "Datetime_jst", "datetime"]:
        if c in df.columns:
            df["datetime_jst"] = pd.to_datetime(df[c], utc=True, errors="coerce").dt.tz_convert(JST)
            break
    else:
        raise RuntimeError("datetime_jst column not found")

    # 騰落率列の候補（前終値基準があれば最優先）
    pct_cols = ["pct_vs_close", "pct_vs_prevclose", "pct_vs_prev_close",
                "pct_vs_open", "pct", "change_pct"]
    for c in pct_cols:
        if c in df.columns:
            df["pct"] = pd.to_numeric(df[c], errors="coerce")
            break
    else:
        raise RuntimeError("pct column not found")

    df = df[["datetime_jst", "pct"]].dropna().sort_values("datetime_jst")
    df = df.set_index("datetime_jst")
    return df

def _style_axes(ax):
    # 背景色など（前デザインに寄せる）
    ax.set_facecolor("#0f1b28")  # パネル
    ax.figure.set_facecolor("#0b1420")  # 背景
    # スパイン／グリッド
    for sp in ax.spines.values():
        sp.set_color("#1c2a3a")
    ax.grid(True, color="#1c2a3a", linewidth=0.8, alpha=0.6)
    ax.tick_params(colors="#d4e9f7")
    ax.yaxis.label.set_color("#d4e9f7")
    ax.xaxis.label.set_color("#d4e9f7")

def main():
    df = _read_csv(CSV_PATH)
    if df.empty:
        raise RuntimeError("no data to plot")

    x = df.index
    y = df["pct"].astype(float)

    # 図・軸
    fig = plt.figure(figsize=(13.5, 7.6), dpi=110)
    ax = fig.add_subplot(111)
    _style_axes(ax)

    # 0% 基準で塗り分け（上：ティール、下：ワイン）
    ax.fill_between(x, 0, y, where=(y >= 0), color="#1f6b6b", alpha=0.35, linewidth=0)
    ax.fill_between(x, 0, y, where=(y < 0),  color="#5a2b46", alpha=0.35, linewidth=0)

    # ライン（シアン系・やや太め）
    ax.plot(x, y, color="#9be7ee", linewidth=2.0)

    # 0% ラインを薄く
    ax.axhline(0, color="#1c2a3a", linewidth=1.0)

    # 軸ラベル（前終値基準）
    ax.set_ylabel("Change vs Prev Close (%)")

    # 2行タイトル（JST + 日付）
    day_str = x[-1].astimezone(JST).strftime("%Y/%m/%d")
    title_top = f"{SLUG.upper()} Intraday Snapshot (JST)"
    ax.set_title(f"{title_top}\n{day_str}", color="#d4e9f7", fontsize=16, pad=12)

    # 余白と保存
    fig.tight_layout()
    fig.savefig(PNG_PATH, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    main()
