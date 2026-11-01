"""かんたん資産メモ assetmemo

資産の内訳を手入力で記録し、合計とカテゴリ別の割合を表示するメモ。
価格の自動取得は行わず、売買などの取引機能もない。あくまで
「いま何にいくらあるか」を書き留めるための道具。
データは SQLite に保存する。単一ファイル Flask + SQLite。
"""
import os
import sqlite3

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)
DB_PATH = os.environ.get("ASSETMEMO_DB", os.path.join(os.path.dirname(__file__), "assetmemo.db"))
CATEGORIES = ["現金", "預金", "株式", "投資信託", "暗号資産", "その他"]
BAR_COLORS = {
    "現金": "#74c0fc", "預金": "#4dabf7", "株式": "#9775fa",
    "投資信託": "#63e6be", "暗号資産": "#ffd43b", "その他": "#adb5bd",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    db.commit()
    db.close()


def summarize(db):
    """(総額, [(カテゴリ, 合計, 割合%), ...]) を返す。カテゴリ順は CATEGORIES どおり。"""
    rows = db.execute(
        "SELECT category, COALESCE(SUM(amount), 0) AS total FROM assets GROUP BY category"
    ).fetchall()
    by_cat = {r["category"]: r["total"] for r in rows}
    total = sum(by_cat.values())
    breakdown = []
    for cat in CATEGORIES:
        subtotal = by_cat.get(cat, 0)
        pct = (subtotal * 100.0 / total) if total else 0.0
        breakdown.append({"category": cat, "total": subtotal, "pct": round(pct, 1),
                          "color": BAR_COLORS[cat]})
    return total, breakdown


PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>かんたん資産メモ</title>
<style>body{font-family:sans-serif;max-width:680px;margin:2em auto;padding:0 1em}
.total{background:#fdf6e3;border:1px solid #d9b84a;border-radius:8px;padding:1em;font-size:1.1em}
.bar-row{margin:.5em 0}.bar{height:18px;border-radius:4px}
table{border-collapse:collapse}td,th{border-bottom:1px solid #ccc;padding:.3em .6em}
.note{color:#555;font-size:.9em}</style>
</head><body>
<h1>かんたん資産メモ</h1>
<p>資産の内訳を手入力で記録するメモです。<strong>価格の自動取得はしません。売買などの取引機能もありません。</strong>金額は自分で更新してください。</p>

<div class="total">資産の合計：<strong>{{ total }} 円</strong></div>

<h2>カテゴリ別の内訳</h2>
{% for b in breakdown %}
<div class="bar-row">
  {{ b.category }}：{{ b.total }} 円（{{ b.pct }}%）
  <div class="bar" style="background:{{ b.color }};width:{{ b.pct }}%"></div>
</div>
{% endfor %}

<h2>資産を登録</h2>
<form method="post" action="{{ url_for('add') }}">
  <label>名前 <input type="text" name="name" placeholder="例：〇〇銀行 普通預金" required></label>
  <label>カテゴリ
    <select name="category">{% for c in categories %}<option>{{ c }}</option>{% endfor %}</select></label>
  <label>金額（円） <input type="number" name="amount" min="0" step="1" required></label>
  <button type="submit">登録する</button>
</form>

<h2>登録済みの資産</h2>
<table>
<tr><th>名前</th><th>カテゴリ</th><th>金額</th><th>操作</th></tr>
{% for a in assets %}
<tr><td>{{ a.name }}</td><td>{{ a.category }}</td><td>{{ a.amount }} 円</td>
<td><form method="post" action="{{ url_for('delete', aid=a.id) }}" onsubmit="return confirm('この資産を削除しますか？')"><button type="submit">削除</button></form></td></tr>
{% else %}<tr><td colspan="4">まだ登録されていません</td></tr>{% endfor %}
</table>
<p class="note">※ 割合は登録済み金額にもとづく単純計算です。価格変動は反映されません。</p>
</body></html>"""


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    db = get_db()
    assets = db.execute("SELECT * FROM assets ORDER BY category, id").fetchall()
    total, breakdown = summarize(db)
    return render_template_string(
        PAGE, assets=assets, total=total, breakdown=breakdown, categories=CATEGORIES
    )


@app.route("/add", methods=["POST"])
def add():
    name = (request.form.get("name") or "").strip()
    category = request.form.get("category", "その他")
    try:
        amount = int(request.form.get("amount") or 0)
    except ValueError:
        return redirect(url_for("index"))
    if name and category in CATEGORIES and amount >= 0:
        db = get_db()
        db.execute(
            "INSERT INTO assets(name, category, amount) VALUES(?, ?, ?)",
            (name, category, amount),
        )
        db.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:aid>", methods=["POST"])
def delete(aid):
    db = get_db()
    db.execute("DELETE FROM assets WHERE id = ?", (aid,))
    db.commit()
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
