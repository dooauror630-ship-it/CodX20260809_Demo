import tempfile
import unittest
from pathlib import Path
from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class FarmOverviewTestCase(unittest.TestCase):
    def test_empty_farm_overview(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app({"TESTING": True, "DATABASE_ENGINE": "sqlite", "DATABASE": str(Path(folder) / "test.db"), "SECRET_KEY": "test"})
            client = app.test_client()
            with app.app_context():
                ensure_admin_user("admin", "123456")
            def csrf():
                return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}
            self.assertEqual(client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}, headers=csrf()).status_code, 200)
            farm = client.post("/api/v1/farms", json={"code": "AN-01", "name": "分析农场", "ownerName": "负责人"}, headers=csrf()).get_json()["data"]["farm"]
            response = client.get("/api/v1/analytics/farm-overview", query_string={"farmId": farm["id"]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["data"]["trade"]["grossProfit"], "0.00")
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
