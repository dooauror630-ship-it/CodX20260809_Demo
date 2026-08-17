import os
import unittest
from uuid import uuid4

from sqlalchemy import delete

from backend.app import create_app, db
from backend.app.config import get_mysql_config
from backend.app.modules.auth.models import User


RUN_MYSQL_TESTS = os.getenv("AGRI_RUN_MYSQL_TESTS") == "1"


@unittest.skipUnless(RUN_MYSQL_TESTS, "set AGRI_RUN_MYSQL_TESTS=1 to run MySQL integration tests")
class MySqlAuthIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mysql_config = get_mysql_config()
        if not mysql_config["database"].endswith("_test"):
            raise RuntimeError("MySQL integration tests require a database ending in '_test'")

        cls.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "mysql",
            "MYSQL_CONFIG": mysql_config,
            "SECRET_KEY": "mysql-integration-test-key",
        })
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        self.username = f"test_{uuid4().hex[:12]}"

    def tearDown(self):
        with self.app.app_context():
            db.session.execute(delete(User).where(User.username == self.username))
            db.session.commit()

    def csrf_headers(self):
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.get_json()["csrfToken"]}

    def post(self, path, payload=None):
        return self.client.post(
            f"/api/v1{path}",
            json=payload,
            headers=self.csrf_headers(),
        )

    def test_registration_and_login_use_mysql(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["database"], "mysql")

        registration = self.post("/auth/register", {
            "username": self.username,
            "password": "FarmPass123",
            "displayName": "MySQL测试用户",
        })
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(self.post("/auth/logout").status_code, 200)

        login = self.post("/auth/login", {
            "username": self.username,
            "password": "FarmPass123",
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user"]["username"], self.username)

        overview = self.client.get("/api/v1/analytics/overview")
        self.assertEqual(overview.status_code, 403)
        self.assertEqual(overview.get_json()["code"], "ADMIN_REQUIRED")


if __name__ == "__main__":
    unittest.main()
