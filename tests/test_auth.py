import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app import create_app, db


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(self.database_path),
            "SECRET_KEY": "test-secret-key",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf_headers(self, prefix="/api/v1"):
        response = self.client.get(f"{prefix}/auth/csrf")
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.get_json()["csrfToken"]}

    def post(self, path, payload=None, prefix="/api/v1"):
        return self.client.post(
            f"{prefix}{path}",
            json=payload,
            headers=self.csrf_headers(prefix),
        )

    def register(self, username="farm_user", password="FarmPass123", display_name="张三"):
        return self.post("/auth/register", {
            "username": username,
            "password": password,
            "displayName": display_name,
        })

    def test_register_persists_hashed_password_and_rejects_duplicate(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.get_json()["user"])

        database = sqlite3.connect(self.database_path)
        try:
            stored_hash = database.execute(
                "SELECT password_hash FROM users WHERE username = ?", ("farm_user",)
            ).fetchone()[0]
        finally:
            database.close()
        self.assertNotEqual(stored_hash, "FarmPass123")
        self.assertTrue(stored_hash.startswith("scrypt:"))

        duplicate = self.register()
        self.assertEqual(duplicate.status_code, 409)

    def test_login_session_and_logout_flow(self):
        self.assertEqual(self.register().status_code, 201)
        logout = self.post("/auth/logout")
        self.assertEqual(logout.status_code, 200)
        logout_csrf = logout.get_json()["csrfToken"]
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

        wrong_password = self.client.post(
            "/api/v1/auth/login",
            json={"username": "farm_user", "password": "WrongPass123"},
            headers={"X-CSRF-Token": logout_csrf},
        )
        self.assertEqual(wrong_password.status_code, 401)

        login = self.post("/auth/login", {
            "username": "FARM_USER",
            "password": "FarmPass123",
            "remember": True,
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me").get_json()["user"]["username"], "farm_user")

    def test_registration_validation(self):
        bad_username = self.register(username="a")
        self.assertEqual(bad_username.status_code, 400)
        self.assertEqual(bad_username.get_json()["field"], "username")

        weak_password = self.register(username="valid_user", password="password")
        self.assertEqual(weak_password.status_code, 400)
        self.assertEqual(weak_password.get_json()["field"], "password")

        invalid_payload = self.post("/auth/register", [])
        self.assertEqual(invalid_payload.status_code, 400)

        invalid_login = self.post("/auth/login", [])
        self.assertEqual(invalid_login.status_code, 400)

    def test_csrf_legacy_routes_and_system_overview(self):
        missing_csrf = self.client.post("/api/v1/auth/login", json={
            "username": "farm_user",
            "password": "FarmPass123",
        })
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.get_json()["code"], "CSRF_INVALID")

        self.assertEqual(self.register().status_code, 201)
        overview = self.client.get("/api/v1/analytics/overview")
        self.assertEqual(overview.status_code, 403)
        self.assertEqual(overview.get_json()["code"], "ADMIN_REQUIRED")

        self.assertEqual(self.post("/auth/logout").status_code, 200)
        legacy_login = self.post("/auth/login", {
            "username": "farm_user",
            "password": "FarmPass123",
        }, prefix="/api")
        self.assertEqual(legacy_login.status_code, 200)
        self.assertEqual(legacy_login.get_json()["user"]["username"], "farm_user")

        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["database"], "sqlite")


if __name__ == "__main__":
    unittest.main()
