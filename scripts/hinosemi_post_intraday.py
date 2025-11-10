# scripts/hinosemi_post_intraday.py
import os
import json
from datetime import timezone, timedelta, datetime

OUT_DIR = "docs/outputs"
STATS = os.path.join(OUT_DIR, "hinosemi_stats.json")
POST = os.path.join(OUT_DIR, "hinosemi_post_intraday.txt")
JST = timezone(timedelta(hours=9))

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATS, "r", encoding="utf-8") as f:
        stats = json.load(f)

    pct = stats.get("pct_intraday", 0.0)
    tickers = stats.get("tickers", [])
    ts = datetime.now(JST).strftime("%Y/%m/%d %H:%M")

    lines = [
        "【HINOSEMI｜日の丸半導体指数】",
        f"本日：{pct:+.2f}%",
        f"構成：{', '.join(tickers)}",
        "#桜Index #HINOSEMI",
    ]
    with open(POST, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
