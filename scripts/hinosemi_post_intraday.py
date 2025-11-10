# scripts/hinosemi_post_intraday.py
from pathlib import Path
import json

OUT = Path("docs/outputs")

# ✅ 正規メンバー（表示はこの順で）
MEMBERS = [
    "8035.T",  # 東京エレクトロン
    "6857.T",  # アドバンテスト
    "285A.T",  # キオクシア
    "6920.T",  # レーザーテック
    "6146.T",  # ディスコ
    "6526.T",  # ソシオネクスト
    "6723.T",  # ルネサス
]

NAME_MAP = {
    "8035.T": "東京エレクトロン",
    "6857.T": "アドバンテスト",
    "285A.T": "キオクシア",
    "6920.T": "レーザーテック",
    "6146.T": "ディスコ",
    "6526.T": "ソシオネクスト",
    "6723.T": "ルネサスエレクトロニクス",
}

def main():
    stats = json.loads((OUT / "hinosemi_stats.json").read_text(encoding="utf-8"))
    pct = stats.get("pct_intraday", 0.0)

    # 表示はコード列でも日本語名でもOK。ここではコード列を採用（ダッシュボードと整合）
    members_line = ",".join(MEMBERS)
    # もし日本語名にしたい場合は ↓ を使う
    # members_line = " / ".join(NAME_MAP.get(t, t) for t in MEMBERS)

    text = (
        "【HINOSEMI | 日の丸半導体指数】\n"
        f"本日：{pct:+.2f}%\n"
        f"構成：{members_line}\n"
        "#桜Index #HINOSEMI\n"
    )
    (OUT / "hinosemi_post_intraday.txt").write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
