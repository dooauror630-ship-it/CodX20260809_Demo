import tempfile
import unittest
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class BaseCatalogAccessTestCase(unittest.TestCase):
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
            "username": "catalog_member",
            "password": "FarmPass123",
            "displayName": "资料查看员",
        })
        self.member_id = member.get_json()["user"]["id"]
        self.post(self.outsider_client, "/auth/register", {
            "username": "catalog_outsider",
            "password": "FarmPass123",
            "displayName": "其他农场用户",
        })
        self.post(self.admin_client, "/auth/login", {"username": "admin", "password": "123456"})
        self.farm = self.create_farm("BASE-001", "基础资料农场")
        self.other_farm = self.create_farm("BASE-002", "其他资料农场")
        self.post(self.admin_client, f"/farms/{self.farm['id']}/members", {
            "userId": self.member_id,
            "roleCode": "viewer",
        })

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf_headers(self, client):
        return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}

    def post(self, client, path, payload=None):
        return client.post(f"/api/v1{path}", json=payload, headers=self.csrf_headers(client))

    def patch(self, client, path, payload):
        return client.patch(f"/api/v1{path}", json=payload, headers=self.csrf_headers(client))

    def create_farm(self, code, name):
        response = self.post(self.admin_client, "/farms", {
            "code": code,
            "name": name,
            "ownerName": "测试负责人",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["farm"]

    def create_category(self, farm_id, code, name, parent_id=None):
        response = self.post(self.admin_client, "/item-categories", {
            "farmId": farm_id,
            "parentId": parent_id,
            "code": code,
            "name": name,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["category"]

    def test_default_catalogs_and_crop_varieties(self):
        response = self.member_client.get("/api/v1/catalogs")
        self.assertEqual(response.status_code, 200)
        catalogs = response.get_json()["data"]
        self.assertEqual({item["code"] for item in catalogs["livestockSpecies"]}, {"PIG", "CHICKEN"})
        self.assertEqual(
            {item["code"] for item in catalogs["cropTypes"]},
            {"TOBACCO", "GARLIC", "RICE", "RAPESEED"},
        )
        self.assertIn("KG", {item["code"] for item in catalogs["units"]})

        tobacco_id = next(item["id"] for item in catalogs["cropTypes"] if item["code"] == "TOBACCO")
        denied = self.post(self.member_client, "/crop-varieties", {
            "cropTypeId": tobacco_id,
            "code": "K326",
            "name": "K326",
        })
        self.assertEqual(denied.status_code, 403)

        created = self.post(self.admin_client, "/crop-varieties", {
            "cropTypeId": tobacco_id,
            "code": "k326",
            "name": "K326",
        })
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["data"]["variety"]["code"], "K326")
        duplicate = self.post(self.admin_client, "/crop-varieties", {
            "cropTypeId": tobacco_id,
            "code": "K326",
            "name": "重复品种",
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_warehouses_items_and_read_scope(self):
        warehouse = self.post(self.admin_client, "/warehouses", {
            "farmId": self.farm["id"],
            "code": "main-01",
            "name": "主仓库",
            "location": "主院北侧",
        })
        self.assertEqual(warehouse.status_code, 201)
        self.assertEqual(warehouse.get_json()["data"]["warehouse"]["code"], "MAIN-01")

        root = self.create_category(self.farm["id"], "FEED", "饲料")
        child = self.create_category(self.farm["id"], "PIG-FEED", "猪饲料", root["id"])
        catalogs = self.admin_client.get("/api/v1/catalogs").get_json()["data"]
        kg_id = next(item["id"] for item in catalogs["units"] if item["code"] == "KG")
        item = self.post(self.admin_client, "/items", {
            "farmId": self.farm["id"],
            "categoryId": child["id"],
            "unitId": kg_id,
            "code": "PIG-FEED-01",
            "name": "育肥猪全价料",
            "itemType": "feed",
            "safetyStock": 500,
            "lotTracking": True,
        })
        self.assertEqual(item.status_code, 201)
        self.assertEqual(item.get_json()["data"]["item"]["safetyStock"], "500")

        member_warehouses = self.member_client.get(
            "/api/v1/warehouses", query_string={"farmId": self.farm["id"], "status": "active"}
        )
        self.assertEqual(member_warehouses.status_code, 200)
        self.assertEqual(member_warehouses.get_json()["data"]["pagination"]["total"], 1)
        member_items = self.member_client.get(
            "/api/v1/items", query_string={"farmId": self.farm["id"], "categoryId": child["id"]}
        )
        self.assertEqual(member_items.status_code, 200)
        self.assertEqual(member_items.get_json()["data"]["items"][0]["categoryName"], "猪饲料")

        denied_read = self.outsider_client.get(
            "/api/v1/items", query_string={"farmId": self.farm["id"]}
        )
        self.assertEqual(denied_read.status_code, 403)
        denied_write = self.post(self.member_client, "/warehouses", {
            "farmId": self.farm["id"],
            "code": "DENIED",
            "name": "无权仓库",
        })
        self.assertEqual(denied_write.status_code, 403)

    def test_category_depth_and_cross_farm_references_are_rejected(self):
        root = self.create_category(self.farm["id"], "INPUT", "投入品")
        child = self.create_category(self.farm["id"], "SEED", "种子", root["id"])
        too_deep = self.post(self.admin_client, "/item-categories", {
            "farmId": self.farm["id"],
            "parentId": child["id"],
            "code": "RICE-SEED",
            "name": "水稻种子",
        })
        self.assertEqual(too_deep.status_code, 409)
        self.assertEqual(too_deep.get_json()["code"], "CATEGORY_DEPTH_EXCEEDED")

        other_category = self.create_category(self.other_farm["id"], "OTHER", "其他农场分类")
        kg_id = next(
            item["id"]
            for item in self.admin_client.get("/api/v1/catalogs").get_json()["data"]["units"]
            if item["code"] == "KG"
        )
        cross_farm = self.post(self.admin_client, "/items", {
            "farmId": self.farm["id"],
            "categoryId": other_category["id"],
            "unitId": kg_id,
            "code": "CROSS-01",
            "name": "跨农场物料",
            "itemType": "other",
            "safetyStock": 0,
            "lotTracking": False,
        })
        self.assertEqual(cross_farm.status_code, 409)
        self.assertEqual(cross_farm.get_json()["code"], "CATEGORY_FARM_MISMATCH")


if __name__ == "__main__":
    unittest.main()
