import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class LivestockBatchTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
        })
        self.admin = self.app.test_client()
        self.manager = self.app.test_client()
        self.operator = self.app.test_client()
        self.viewer = self.app.test_client()
        self.outsider = self.app.test_client()
        with self.app.app_context():
            ensure_admin_user("admin", "123456")

        users = {}
        for key, client, display_name in (
            ("manager", self.manager, "养殖负责人"),
            ("operator", self.operator, "养殖操作员"),
            ("viewer", self.viewer, "养殖查看员"),
            ("outsider", self.outsider, "其他农场人员"),
        ):
            response = self.post(client, "/auth/register", {
                "username": f"livestock_{key}",
                "password": "FarmPass123",
                "displayName": display_name,
            })
            users[key] = response.get_json()["user"]["id"]

        self.post(self.admin, "/auth/login", {"username": "admin", "password": "123456"})
        self.farm = self.create_farm("PIG-FARM", "生猪养殖测试农场")
        self.other_farm = self.create_farm("OTHER-FARM", "其他隔离农场")
        for key, role in (("manager", "manager"), ("operator", "operator"), ("viewer", "viewer")):
            self.post(self.admin, f"/farms/{self.farm['id']}/members", {
                "userId": users[key],
                "roleCode": role,
            })

        self.barn_a = self.create_barn(self.farm["id"], "PIG-A", "育肥一舍", "pig", 100)
        self.barn_b = self.create_barn(self.farm["id"], "PIG-B", "育肥二舍", "pig", 40)
        self.isolation_barn = self.create_barn(self.farm["id"], "ISO-01", "隔离舍", "isolation", 20)
        self.chicken_barn = self.create_barn(self.farm["id"], "CHK-01", "鸡舍", "chicken", 100)
        self.other_barn = self.create_barn(self.other_farm["id"], "PIG-X", "其他农场猪舍", "pig", 100)
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        self.pig_species_id = next(item["id"] for item in catalogs["livestockSpecies"] if item["code"] == "PIG")
        self.chicken_species_id = next(
            item["id"] for item in catalogs["livestockSpecies"] if item["code"] == "CHICKEN"
        )

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
        response = self.post(self.admin, "/farms", {
            "code": code,
            "name": name,
            "ownerName": "测试负责人",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["farm"]

    def create_barn(self, farm_id, code, name, barn_type, capacity):
        response = self.post(self.admin, "/barns", {
            "farmId": farm_id,
            "code": code,
            "name": name,
            "barnType": barn_type,
            "capacity": capacity,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["barn"]

    def batch_input(self, batch_no="PIG-2026-001", entry_no="EN-2026-001", count=60, **changes):
        payload = {
            "farmId": self.farm["id"],
            "speciesId": self.pig_species_id,
            "batchNo": batch_no,
            "name": "八月育肥猪一批",
            "entryNo": entry_no,
            "entryDate": date.today().isoformat(),
            "barnId": self.barn_a["id"],
            "initialCount": count,
            "source": "本地仔猪供应户",
            "notes": "入栏观察七天",
        }
        return {**payload, **changes}

    def create_batch(self, client=None, **changes):
        response = self.post(client or self.manager, "/livestock-batches", self.batch_input(**changes))
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["batch"]

    def movement_input(self, batch_id, movement_no, movement_type, from_barn_id, quantity, **changes):
        payload = {
            "farmId": self.farm["id"],
            "batchId": batch_id,
            "movementNo": movement_no,
            "movementType": movement_type,
            "occurredOn": date.today().isoformat(),
            "fromBarnId": from_barn_id,
            "quantity": quantity,
            "notes": None,
        }
        if movement_type == "TRANSFER":
            payload["toBarnId"] = self.barn_b["id"]
        if movement_type in ("DEATH", "CULL"):
            payload["reason"] = "测试业务原因"
        return {**payload, **changes}

    def add_movement(self, batch_id, movement_no, movement_type, from_barn_id, quantity, **changes):
        response = self.post(
            self.operator,
            "/livestock-movements",
            self.movement_input(batch_id, movement_no, movement_type, from_barn_id, quantity, **changes),
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["batch"]

    def test_roles_collaborate_through_entry_transfer_losses_and_exit(self):
        batch = self.create_batch()
        self.assertEqual(batch["initialCount"], 60)
        self.assertEqual(batch["currentHeadCount"], 60)
        self.assertEqual(batch["barnBalances"][0]["barnId"], self.barn_a["id"])

        after_transfer = self.add_movement(
            batch["id"], "MV-TRANSFER-001", "TRANSFER", self.barn_a["id"], 20
        )
        self.assertEqual(after_transfer["currentHeadCount"], 60)
        self.add_movement(batch["id"], "MV-DEATH-001", "DEATH", self.barn_b["id"], 2)
        self.add_movement(batch["id"], "MV-CULL-001", "CULL", self.barn_a["id"], 1)
        final_batch = self.add_movement(batch["id"], "MV-EXIT-001", "EXIT", self.barn_a["id"], 10)

        self.assertEqual(final_batch["currentHeadCount"], 47)
        self.assertEqual(final_batch["deathCount"], 2)
        self.assertEqual(final_batch["cullCount"], 1)
        self.assertEqual(final_batch["exitCount"], 10)
        balances = {item["barnCode"]: item["headCount"] for item in final_batch["barnBalances"]}
        self.assertEqual(balances, {"PIG-A": 29, "PIG-B": 18})

        viewer_list = self.viewer.get("/api/v1/livestock-batches", query_string={"farmId": self.farm["id"]})
        self.assertEqual(viewer_list.status_code, 200)
        data = viewer_list.get_json()["data"]
        self.assertEqual(data["summary"], {
            "activeBatchCount": 1,
            "currentHeadCount": 47,
            "deathCount": 2,
            "exitedCount": 11,
        })
        self.assertEqual(data["items"][0]["currentHeadCount"], 47)

        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}")
        self.assertEqual(detail.status_code, 200)
        detail_batch = detail.get_json()["data"]["batch"]
        self.assertEqual(detail_batch["movementCount"], 5)
        self.assertEqual(
            [item["movementType"] for item in detail_batch["movements"]],
            ["EXIT", "CULL", "DEATH", "TRANSFER", "ENTRY"],
        )

    def test_retries_boundaries_chronology_and_automatic_close_are_safe(self):
        payload = self.batch_input(count=10, entryDate=(date.today() - timedelta(days=1)).isoformat())
        created = self.post(self.manager, "/livestock-batches", payload)
        self.assertEqual(created.status_code, 201)
        batch = created.get_json()["data"]["batch"]
        self.assertEqual(self.post(self.manager, "/livestock-batches", payload).status_code, 200)
        self.assertEqual(
            self.post(self.manager, "/livestock-batches", {**payload, "initialCount": 11}).status_code,
            409,
        )
        self.assertEqual(
            self.post(self.manager, "/livestock-batches", self.batch_input(
                batch_no="PIG-2026-002", entry_no=payload["entryNo"], count=5
            )).status_code,
            409,
        )

        transfer = self.movement_input(batch["id"], "MV-RETRY-001", "TRANSFER", self.barn_a["id"], 2)
        self.assertEqual(self.post(self.operator, "/livestock-movements", transfer).status_code, 201)
        self.assertEqual(self.post(self.operator, "/livestock-movements", transfer).status_code, 200)
        self.assertEqual(
            self.post(self.operator, "/livestock-movements", {**transfer, "quantity": 1}).status_code,
            409,
        )

        too_many = self.movement_input(batch["id"], "MV-TOO-MANY", "DEATH", self.barn_b["id"], 3)
        response = self.post(self.operator, "/livestock-movements", too_many)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["details"]["available"], 2)

        missing_reason = self.movement_input(batch["id"], "MV-NO-REASON", "DEATH", self.barn_a["id"], 1)
        missing_reason.pop("reason")
        self.assertEqual(self.post(self.operator, "/livestock-movements", missing_reason).status_code, 400)
        future = self.movement_input(
            batch["id"],
            "MV-FUTURE",
            "EXIT",
            self.barn_a["id"],
            1,
            occurredOn=(date.today() + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(self.post(self.operator, "/livestock-movements", future).status_code, 400)
        backdated = self.movement_input(
            batch["id"],
            "MV-BACKDATED",
            "EXIT",
            self.barn_a["id"],
            1,
            occurredOn=(date.today() - timedelta(days=1)).isoformat(),
        )
        self.assertEqual(self.post(self.operator, "/livestock-movements", backdated).status_code, 409)

        self.add_movement(batch["id"], "MV-EXIT-A", "EXIT", self.barn_a["id"], 8)
        closed = self.add_movement(batch["id"], "MV-EXIT-B", "EXIT", self.barn_b["id"], 2)
        self.assertEqual(closed["currentHeadCount"], 0)
        self.assertEqual(closed["status"], "CLOSED")
        rejected = self.post(
            self.operator,
            "/livestock-movements",
            self.movement_input(batch["id"], "MV-AFTER-CLOSE", "EXIT", self.barn_a["id"], 1),
        )
        self.assertEqual(rejected.status_code, 409)
        closed_list = self.viewer.get(
            "/api/v1/livestock-batches",
            query_string={"farmId": self.farm["id"], "status": "CLOSED"},
        )
        self.assertEqual(closed_list.get_json()["data"]["pagination"]["total"], 1)

    def test_permissions_farm_barn_species_and_capacity_boundaries(self):
        viewer_denied = self.post(self.viewer, "/livestock-batches", self.batch_input())
        self.assertEqual(viewer_denied.status_code, 403)
        outsider_denied = self.outsider.get(
            "/api/v1/livestock-batches", query_string={"farmId": self.farm["id"]}
        )
        self.assertEqual(outsider_denied.status_code, 403)

        cross_farm = self.post(self.manager, "/livestock-batches", self.batch_input(barnId=self.other_barn["id"]))
        self.assertEqual(cross_farm.status_code, 409)
        wrong_barn = self.post(self.manager, "/livestock-batches", self.batch_input(barnId=self.chicken_barn["id"]))
        self.assertEqual(wrong_barn.status_code, 409)
        wrong_species = self.post(
            self.manager,
            "/livestock-batches",
            self.batch_input(speciesId=self.chicken_species_id),
        )
        self.assertEqual(wrong_species.status_code, 409)
        over_capacity = self.post(
            self.manager,
            "/livestock-batches",
            self.batch_input(barnId=self.barn_b["id"], initialCount=41),
        )
        self.assertEqual(over_capacity.status_code, 409)

        batch = self.create_batch(count=60)
        second_batch = self.create_batch(
            batch_no="PIG-2026-002",
            entry_no="EN-2026-002",
            count=35,
            barnId=self.barn_b["id"],
        )
        self.assertEqual(second_batch["currentHeadCount"], 35)
        capacity_transfer = self.movement_input(
            batch["id"], "MV-CAPACITY", "TRANSFER", self.barn_a["id"], 6
        )
        self.assertEqual(self.post(self.operator, "/livestock-movements", capacity_transfer).status_code, 409)

        self.patch(self.admin, f"/barns/{self.isolation_barn['id']}", {"isActive": False})
        disabled_destination = self.movement_input(
            batch["id"],
            "MV-DISABLED-BARN",
            "TRANSFER",
            self.barn_a["id"],
            1,
            toBarnId=self.isolation_barn["id"],
        )
        self.assertEqual(self.post(self.operator, "/livestock-movements", disabled_destination).status_code, 409)

    def test_health_and_weight_records_are_auditable_and_calculate_adg(self):
        entry_date = date.today() - timedelta(days=10)
        batch = self.create_batch(entryDate=entry_date.isoformat())
        health = {
            "farmId": self.farm["id"],
            "batchId": batch["id"],
            "recordNo": "HEALTH-001",
            "recordType": "VACCINATION",
            "occurredOn": (entry_date + timedelta(days=1)).isoformat(),
            "description": "猪瘟疫苗首免",
            "medicineName": "猪瘟活疫苗",
            "dosage": "每头 1 头份",
            "notes": "观察无异常",
        }
        self.assertEqual(self.post(self.viewer, "/livestock-health-records", health).status_code, 403)
        created = self.post(self.operator, "/livestock-health-records", health)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.post(self.operator, "/livestock-health-records", health).status_code, 200)
        self.assertEqual(
            self.post(self.operator, "/livestock-health-records", {**health, "description": "内容变化"}).status_code,
            409,
        )

        first_weight = {
            "farmId": self.farm["id"],
            "batchId": batch["id"],
            "recordNo": "WEIGHT-001",
            "occurredOn": entry_date.isoformat(),
            "sampleCount": 10,
            "averageWeight": "20.000",
            "notes": "入栏抽样",
        }
        latest_weight = {
            **first_weight,
            "recordNo": "WEIGHT-002",
            "occurredOn": date.today().isoformat(),
            "averageWeight": "27.500",
            "notes": "十日抽样",
        }
        self.assertEqual(self.post(self.manager, "/livestock-weight-records", first_weight).status_code, 201)
        self.assertEqual(self.post(self.operator, "/livestock-weight-records", latest_weight).status_code, 201)

        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}")
        self.assertEqual(detail.status_code, 200)
        data = detail.get_json()["data"]["batch"]
        self.assertEqual(data["healthRecords"][0]["recordNo"], "HEALTH-001")
        self.assertEqual([item["recordNo"] for item in data["weightRecords"]], ["WEIGHT-002", "WEIGHT-001"])
        self.assertEqual(data["productionSummary"]["latestAverageWeight"], "27.5")
        self.assertEqual(data["productionSummary"]["adg"], "0.750")
        self.assertEqual(data["productionSummary"]["healthRecordCount"], 1)

        before_entry = {**first_weight, "recordNo": "WEIGHT-EARLY", "occurredOn": (entry_date - timedelta(days=1)).isoformat()}
        self.assertEqual(self.post(self.operator, "/livestock-weight-records", before_entry).status_code, 409)

    def test_farm_analysis_reports_trend_mortality_comparison_and_access_boundaries(self):
        entry_date = date.today() - timedelta(days=10)
        first = self.create_batch(entryDate=entry_date.isoformat(), count=50)
        self.add_movement(
            first["id"],
            "MV-ANALYSIS-DEATH",
            "DEATH",
            self.barn_a["id"],
            2,
            occurredOn=(date.today() - timedelta(days=2)).isoformat(),
        )
        second = self.create_batch(
            batch_no="PIG-2026-ANALYSIS",
            entry_no="EN-2026-ANALYSIS",
            entryDate=(date.today() - timedelta(days=1)).isoformat(),
            barnId=self.barn_b["id"],
            count=20,
        )

        response = self.viewer.get(
            "/api/v1/livestock-analysis",
            query_string={"farmId": self.farm["id"], "trendDays": 7},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["summary"], {
            "activeBatchCount": 2,
            "currentHeadCount": 68,
            "entryCount": 70,
            "deathCount": 2,
            "mortalityRate": "2.86",
        })
        self.assertEqual(len(data["trend"]), 7)
        self.assertEqual(data["trend"][0]["currentHeadCount"], 50)
        self.assertEqual(data["trend"][-1]["currentHeadCount"], 68)
        self.assertEqual(sum(point["deathCount"] for point in data["trend"]), 2)
        self.assertEqual(
            [item["batchId"] for item in data["batchComparisons"][:2]],
            [second["id"], first["id"]],
        )
        self.assertEqual(data["batchComparisons"][1]["mortalityRate"], "4.00")
        self.assertEqual(data["period"]["trendDays"], 7)

        invalid = self.operator.get(
            "/api/v1/livestock-analysis",
            query_string={"farmId": self.farm["id"], "trendDays": 6},
        )
        self.assertEqual(invalid.status_code, 400)
        denied = self.outsider.get(
            "/api/v1/livestock-analysis",
            query_string={"farmId": self.farm["id"]},
        )
        self.assertEqual(denied.status_code, 403)

    def test_batch_cost_entries_are_idempotent_auditable_and_permission_scoped(self):
        entry_date = date.today() - timedelta(days=2)
        batch = self.create_batch(entryDate=entry_date.isoformat())
        payload = {
            "farmId": self.farm["id"],
            "batchId": batch["id"],
            "entryNo": "COST-ENTRY-001",
            "businessDate": entry_date.isoformat(),
            "costType": "ENTRY",
            "amount": "12000.00",
            "description": "仔猪入栏采购成本",
            "notes": "按供应户结算单登记",
        }

        self.assertEqual(self.post(self.viewer, "/livestock-cost-entries", payload).status_code, 403)
        created = self.post(self.manager, "/livestock-cost-entries", payload)
        self.assertEqual(created.status_code, 201)
        entry = created.get_json()["data"]["costEntry"]
        self.assertEqual(entry["amount"], "12000.00")
        self.assertEqual(self.post(self.manager, "/livestock-cost-entries", payload).status_code, 200)
        self.assertEqual(
            self.post(self.manager, "/livestock-cost-entries", {**payload, "amount": "12001"}).status_code,
            409,
        )
        self.assertEqual(
            self.post(self.operator, "/livestock-cost-entries", {
                **payload,
                "entryNo": "COST-EARLY-001",
                "businessDate": (entry_date - timedelta(days=1)).isoformat(),
            }).status_code,
            409,
        )

        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}").get_json()["data"]["batch"]
        self.assertEqual(detail["productionSummary"]["totalAdditionalCost"], "12000.00")
        self.assertEqual(detail["productionSummary"]["totalProductionCost"], "12000.00")
        self.assertEqual(detail["productionSummary"]["productionCostPerHead"], "200.00")
        self.assertEqual(detail["costEntries"][0]["status"], "POSTED")

        self.assertEqual(
            self.post(self.viewer, f"/livestock-cost-entries/{entry['id']}/cancel").status_code,
            403,
        )
        cancelled = self.post(self.operator, f"/livestock-cost-entries/{entry['id']}/cancel")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["data"]["costEntry"]["status"], "CANCELLED")
        self.assertEqual(
            self.post(self.operator, f"/livestock-cost-entries/{entry['id']}/cancel").status_code,
            200,
        )
        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}").get_json()["data"]["batch"]
        self.assertEqual(detail["productionSummary"]["totalAdditionalCost"], "0.00")
        self.assertEqual(detail["costEntries"][0]["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
