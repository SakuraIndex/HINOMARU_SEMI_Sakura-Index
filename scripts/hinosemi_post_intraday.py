from pathlib import Path
import json

OUT = Path("docs/outputs")

# ✅ 表示も固定メンバーから生成
MEMBERS = [
    "8035.T", "6857.T", "285A.T", "6920.T", "6146.T", "6526.T", "6723.T"
]

def main():
    stats = json.loads((OUT / "hinosemi_stats.json").read_text(encoding="utf-8"))
    pct = stats.get("pct_intraday", 0.0)
    members_line = ",".join(MEMBERS)

    text = (
        "【HINOSEMI | 日の丸半導体指数】\n"
        f"本日：{pct:+.2f}%\n"
        f"構成：{members_line}\n"
        "#桜Index #HINOSEMI\n"
    )
    (OUT / "hinosemi_post_intraday.txt").write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
