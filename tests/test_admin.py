import tempfile
import unittest
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class AdminUserManagementTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
        })
        self.admin_client = self.app.test_client()
        self.user_client = self.app.test_client()
        with self.app.app_context():
            self.admin, _created = ensure_admin_user("admin", "123456")
            self.admin_id = self.admin.id

        self.assertEqual(self.post(self.user_client, "/auth/register", {
            "username": "farm_user",
            "password": "FarmPass123",
            "displayName": "普通用户",
        }).status_code, 201)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf_headers(self, client):
        response = client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.get_json()["csrfToken"]}

    def post(self, client, path, payload=None):
        return client.post(
            f"/api/v1{path}",
            json=payload,
            headers=self.csrf_headers(client),
        )

    def patch(self, client, path, payload):
        return client.patch(
            f"/api/v1{path}",
            json=payload,
            headers=self.csrf_headers(client),
        )

    def login_admin(self):
        response = self.post(self.admin_client, "/auth/login", {
            "username": "admin",
            "password": "123456",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["role"], "admin")

    def test_ordinary_user_cannot_access_administration_or_global_analytics(self):
        users = self.user_client.get("/api/v1/admin/users")
        self.assertEqual(users.status_code, 403)
        self.assertEqual(users.get_json()["code"], "ADMIN_REQUIRED")

        overview = self.user_client.get("/api/v1/analytics/overview")
        self.assertEqual(overview.status_code, 403)

    def test_admin_can_list_update_and_reset_user_password(self):
        self.login_admin()
        overview = self.admin_client.get("/api/v1/analytics/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.get_json()["data"]["summary"]["registeredUsers"], 2)

        users = self.admin_client.get("/api/v1/admin/users?keyword=farm&pageSize=5")
        self.assertEqual(users.status_code, 200)
        item = users.get_json()["data"]["items"][0]
        self.assertEqual(item["username"], "farm_user")

        disabled = self.patch(self.admin_client, f"/admin/users/{item['id']}", {
            "displayName": "养殖负责人",
            "isActive": False,
        })
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.get_json()["data"]["user"]["isActive"])
        self.assertEqual(self.user_client.get("/api/v1/auth/me").status_code, 401)

        enabled = self.patch(self.admin_client, f"/admin/users/{item['id']}", {"isActive": True})
        self.assertEqual(enabled.status_code, 200)
        reset = self.post(self.admin_client, f"/admin/users/{item['id']}/password", {
            "password": "NewFarm123",
        })
        self.assertEqual(reset.status_code, 200)

        login = self.post(self.user_client, "/auth/login", {
            "username": "farm_user",
            "password": "NewFarm123",
        })
        self.assertEqual(login.status_code, 200)

    def test_admin_cannot_remove_own_access(self):
        self.login_admin()
        demote = self.patch(self.admin_client, f"/admin/users/{self.admin_id}", {"role": "operator"})
        self.assertEqual(demote.status_code, 400)
        self.assertEqual(demote.get_json()["code"], "ADMIN_SELF_PROTECTION")

        disable = self.patch(self.admin_client, f"/admin/users/{self.admin_id}", {"isActive": False})
        self.assertEqual(disable.status_code, 400)


if __name__ == "__main__":
    unittest.main()
