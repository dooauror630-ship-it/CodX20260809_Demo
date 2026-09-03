import tempfile
import unittest
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.agent.seed import seed_agent_demo
from backend.app.modules.agent.service import inventory_summary, livestock_summary
from backend.app.modules.auth.service import ensure_admin_user
from backend.app.modules.farm.models import Farm


class AgentApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
            "AGENT_API_KEY": "test-agent-key",
            "AGENT_FARM_CODE": "",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            admin, _created = ensure_admin_user("admin", "123456")
            farm = Farm(
                code="AGENT-001",
                name="智能体测试农场",
                owner_name="测试负责人",
                timezone="Asia/Shanghai",
                is_active=True,
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            db.session.add(farm)
            db.session.commit()
            self.farm_id = farm.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def get(self, path, key="test-agent-key"):
        headers = {"x-api-key": key} if key is not None else {}
        return self.client.get(f"/api/v1/agent{path}", headers=headers)

    def test_api_key_is_required(self):
        self.assertEqual(self.get("/farms", None).status_code, 401)
        self.assertEqual(self.get("/farms", "wrong-key").status_code, 401)
        bearer = self.client.get(
            "/api/v1/agent/farms",
            headers={"x-api-key": "Bearer test-agent-key"},
        )
        self.assertEqual(bearer.status_code, 200)

    def test_read_only_business_tools(self):
        farms = self.get("/farms")
        self.assertEqual(farms.status_code, 200)
        self.assertEqual(farms.get_json()["data"]["farms"][0]["name"], "智能体测试农场")

        inventory = self.get(f"/inventory-summary?farmId={self.farm_id}")
        self.assertEqual(inventory.status_code, 200)
        self.assertEqual(inventory.get_json()["data"]["summary"]["stockItemCount"], 0)

        livestock = self.get(f"/livestock-summary?farmId={self.farm_id}")
        self.assertEqual(livestock.status_code, 200)
        self.assertEqual(livestock.get_json()["data"]["summary"]["currentHeadCount"], 0)

    def test_farm_id_is_validated(self):
        response = self.get("/inventory-summary?farmId=abc")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "FARM_ID_INVALID")

    def test_demo_seed_is_repeatable_and_populates_summaries(self):
        with self.app.app_context():
            first = seed_agent_demo()
            second = seed_agent_demo()
            self.assertEqual(first.id, second.id)

            inventory = inventory_summary(first.id)
            self.assertEqual(inventory["summary"]["stockItemCount"], 3)
            self.assertEqual(inventory["summary"]["lowStockCount"], 2)

            livestock = livestock_summary(first.id)
            self.assertEqual(livestock["summary"]["currentHeadCount"], 84)
            self.assertEqual(len(livestock["recentHealthRecords"]), 2)
            self.assertEqual(len(livestock["recentWeightRecords"]), 1)


if __name__ == "__main__":
    unittest.main()
