import os, json

OUTPUT_DIR = "docs/outputs"
STATS = os.path.join(OUTPUT_DIR, "hinosemi_stats.json")
POST  = os.path.join(OUTPUT_DIR, "hinosemi_post_intraday.txt")

def main():
    with open(STATS, "r", encoding="utf-8") as f:
        j = json.load(f)
    pct = j.get("pct_intraday", 0.0)
    last = j.get("last_level")
    post_lines = [
        "【日の丸半導体指数】",
        f"本日：{pct:+.2f}%",
        f"指数：{last if last is not None else 'None'}",
        "構成：8035/6857/6920/6146/6526/6723",
        "#桜Index #HinomaruSemi",
    ]
    with open(POST, "w", encoding="utf-8") as f:
        f.write("\n".join(post_lines))

if __name__ == "__main__":
    main()
