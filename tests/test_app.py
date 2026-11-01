import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["ASSETMEMO_DB"] = _tmp.name

import app as app_module  # noqa: E402


class AssetMemoTest(unittest.TestCase):
    def setUp(self):
        app_module.init_db()
        self.client = app_module.app.test_client()
        with app_module.app.app_context():
            conn = app_module.get_db()
            conn.execute("DELETE FROM assets")
            conn.commit()

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_index_ok_and_disclaimer(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("かんたん資産メモ", body)
        self.assertIn("価格の自動取得はしません", body)
        self.assertIn("取引機能もありません", body)

    def test_totals_and_breakdown(self):
        self.client.post("/add", data={"name": "銀行預金", "category": "預金", "amount": "300000"})
        self.client.post("/add", data={"name": "財布の現金", "category": "現金", "amount": "100000"})
        with app_module.app.app_context():
            conn = app_module.get_db()
            total, breakdown = app_module.summarize(conn)
        self.assertEqual(total, 400000)
        by_cat = {b["category"]: b for b in breakdown}
        self.assertEqual(by_cat["預金"]["total"], 300000)
        self.assertEqual(by_cat["預金"]["pct"], 75.0)
        self.assertEqual(by_cat["現金"]["pct"], 25.0)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("400000 円", body)
        self.assertIn("75.0%", body)

    def test_add_visible_delete_gone(self):
        self.client.post("/add", data={"name": "投資信託A", "category": "投資信託", "amount": "50000"})
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("投資信託A", body)
        with app_module.app.app_context():
            conn = app_module.get_db()
            aid = conn.execute("SELECT id FROM assets").fetchone()["id"]
        res = self.client.post(f"/delete/{aid}")
        self.assertEqual(res.status_code, 302)
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("投資信託A", body)
        self.assertIn("0 円", body)

    def test_invalid_category_rejected(self):
        self.client.post("/add", data={"name": "だめな資産", "category": "不動産", "amount": "100"})
        with app_module.app.app_context():
            conn = app_module.get_db()
            n = conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
