import tempfile
import unittest
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class FarmAccessTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
        })
        self.admin_client = self.app.test_client()
        self.member_client = self.app.test_client()
        self.outsider_client = self.app.test_client()
        with self.app.app_context():
            ensure_admin_user("admin", "123456")

        member = self.post(self.member_client, "/auth/register", {
            "username": "farm_member",
            "password": "FarmPass123",
            "displayName": "养殖操作员",
        })
        outsider = self.post(self.outsider_client, "/auth/register", {
            "username": "farm_outsider",
            "password": "FarmPass123",
            "displayName": "其他用户",
        })
        self.member_id = member.get_json()["user"]["id"]
        self.outsider_id = outsider.get_json()["user"]["id"]
        self.login_admin()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf_headers(self, client):
        response = client.get("/api/v1/auth/csrf")
        return {"X-CSRF-Token": response.get_json()["csrfToken"]}

    def post(self, client, path, payload=None):
        return client.post(f"/api/v1{path}", json=payload, headers=self.csrf_headers(client))

    def patch(self, client, path, payload):
        return client.patch(f"/api/v1{path}", json=payload, headers=self.csrf_headers(client))

    def login_admin(self):
        response = self.post(self.admin_client, "/auth/login", {
            "username": "admin",
            "password": "123456",
        })
        self.assertEqual(response.status_code, 200)

    def create_farm(self):
        response = self.post(self.admin_client, "/farms", {
            "code": "farm-001",
            "name": "家庭综合农场",
            "ownerName": "张负责人",
            "address": "云南省示范村",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["farm"]

    def test_admin_assigns_members_and_queries_are_isolated(self):
        farm = self.create_farm()
        self.assertEqual(farm["code"], "FARM-001")
        self.assertEqual(self.member_client.get("/api/v1/farms").get_json()["data"]["pagination"]["total"], 0)

        assigned = self.post(self.admin_client, f"/farms/{farm['id']}/members", {
            "userId": self.member_id,
            "roleCode": "operator",
        })
        self.assertEqual(assigned.status_code, 201)

        member_farms = self.member_client.get("/api/v1/farms").get_json()["data"]
        self.assertEqual(member_farms["pagination"]["total"], 1)
        self.assertEqual(member_farms["items"][0]["accessRole"], "operator")
        self.assertEqual(self.member_client.get(f"/api/v1/farms/{farm['id']}").status_code, 200)

        denied = self.outsider_client.get(f"/api/v1/farms/{farm['id']}")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "FARM_ACCESS_DENIED")
        self.assertEqual(self.outsider_client.get("/api/v1/farms").get_json()["data"]["pagination"]["total"], 0)
        self.assertEqual(self.post(self.member_client, "/farms", {
            "code": "DENIED",
            "name": "无权农场",
            "ownerName": "普通用户",
        }).status_code, 403)

        disabled = self.patch(self.admin_client, f"/farms/{farm['id']}/members/{self.member_id}", {
            "isActive": False,
        })
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(self.member_client.get("/api/v1/farms").get_json()["data"]["pagination"]["total"], 0)

    def test_farm_code_is_unique_and_member_roles_can_change(self):
        farm = self.create_farm()
        duplicate = self.post(self.admin_client, "/farms", {
            "code": "FARM-001",
            "name": "重复农场",
            "ownerName": "重复负责人",
        })
        self.assertEqual(duplicate.status_code, 409)

        self.post(self.admin_client, f"/farms/{farm['id']}/members", {
            "userId": self.outsider_id,
            "roleCode": "viewer",
        })
        changed = self.patch(self.admin_client, f"/farms/{farm['id']}/members/{self.outsider_id}", {
            "roleCode": "manager",
        })
        self.assertEqual(changed.get_json()["data"]["member"]["roleCode"], "manager")
        members = self.admin_client.get(f"/api/v1/farms/{farm['id']}/members")
        self.assertEqual(members.status_code, 200)
        self.assertEqual(len(members.get_json()["data"]["items"]), 1)

    def test_farm_address_can_be_cleared_but_required_fields_cannot_be_null(self):
        farm = self.create_farm()

        cleared = self.patch(self.admin_client, f"/farms/{farm['id']}", {"address": None})
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()["data"]["farm"]["address"])

        rejected = self.patch(self.admin_client, f"/farms/{farm['id']}", {"name": None})
        self.assertEqual(rejected.status_code, 400)

    def test_barns_and_plots_are_isolated_by_farm_membership(self):
        farm = self.create_farm()
        self.post(self.admin_client, f"/farms/{farm['id']}/members", {
            "userId": self.member_id,
            "roleCode": "operator",
        })

        barn_response = self.post(self.admin_client, "/barns", {
            "farmId": farm["id"],
            "code": "pig-01",
            "name": "育肥一舍",
            "barnType": "pig",
            "capacity": 180,
        })
        self.assertEqual(barn_response.status_code, 201)
        barn = barn_response.get_json()["data"]["barn"]
        self.assertEqual(barn["code"], "PIG-01")

        plot_response = self.post(self.admin_client, "/plots", {
            "farmId": farm["id"],
            "code": "plot-01",
            "name": "东山烟田",
            "areaMu": "100.000",
            "soilType": "红壤",
        })
        self.assertEqual(plot_response.status_code, 201)
        plot = plot_response.get_json()["data"]["plot"]
        self.assertEqual(plot["areaMu"], "100")

        barn_list = self.member_client.get("/api/v1/barns", query_string={"farmId": farm["id"]})
        self.assertEqual(barn_list.status_code, 200)
        self.assertEqual(barn_list.get_json()["data"]["items"][0]["id"], barn["id"])

        plot_list = self.member_client.get(
            "/api/v1/plots",
            query_string={"farmId": farm["id"], "keyword": "红壤", "status": "active"},
        )
        self.assertEqual(plot_list.status_code, 200)
        self.assertEqual(plot_list.get_json()["data"]["pagination"]["total"], 1)

        denied = self.outsider_client.get("/api/v1/barns", query_string={"farmId": farm["id"]})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "FARM_ACCESS_DENIED")
        self.assertEqual(self.post(self.member_client, "/barns", {
            "farmId": farm["id"],
            "code": "DENIED",
            "name": "无权圈舍",
            "barnType": "pig",
            "capacity": 10,
        }).status_code, 403)

        cleared = self.patch(self.admin_client, f"/plots/{plot['id']}", {"soilType": None})
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()["data"]["plot"]["soilType"])

    def test_farm_resource_codes_and_numeric_constraints_are_enforced(self):
        farm = self.create_farm()
        barn_input = {
            "farmId": farm["id"],
            "code": "PIG-01",
            "name": "育肥一舍",
            "barnType": "pig",
            "capacity": 180,
        }
        self.assertEqual(self.post(self.admin_client, "/barns", barn_input).status_code, 201)
        self.assertEqual(self.post(self.admin_client, "/barns", barn_input).status_code, 409)

        invalid_capacity = {**barn_input, "code": "PIG-02", "capacity": -1}
        self.assertEqual(self.post(self.admin_client, "/barns", invalid_capacity).status_code, 400)
        invalid_area = {
            "farmId": farm["id"],
            "code": "PLOT-01",
            "name": "无效地块",
            "areaMu": 0,
        }
        self.assertEqual(self.post(self.admin_client, "/plots", invalid_area).status_code, 400)


if __name__ == "__main__":
    unittest.main()
