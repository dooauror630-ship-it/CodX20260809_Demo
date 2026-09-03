import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class CropCycleTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
        })
        self.admin = self.app.test_client()
        self.viewer = self.app.test_client()
        self.member_id = None
        with self.app.app_context():
            ensure_admin_user("admin", "123456")
        member = self.post(self.viewer, "/auth/register", {
            "username": "crop_viewer", "password": "FarmPass123", "displayName": "种植查看员",
        })
        self.member_id = member.get_json()["user"]["id"]
        self.post(self.admin, "/auth/login", {"username": "admin", "password": "123456"})
        self.farm = self.create_farm("CROP-001")
        self.post(self.admin, f"/farms/{self.farm['id']}/members", {
            "userId": self.member_id, "roleCode": "viewer",
        })
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        self.kg_unit = next(item for item in catalogs["units"] if item["code"] == "KG")
        self.crop_type = next(item for item in catalogs["cropTypes"] if item["code"] == "TOBACCO")
        self.variety = self.crop_type["varieties"][0] if self.crop_type["varieties"] else self.create_variety()
        plot = self.post(self.admin, "/plots", {
            "farmId": self.farm["id"], "code": "PLOT-01", "name": "东山烟田", "areaMu": "100",
        })
        self.plot = plot.get_json()["data"]["plot"]
        self.warehouse = self.post(self.admin, "/warehouses", {
            "farmId": self.farm["id"], "code": "CROP-WH", "name": "农产品暂存仓",
        }).get_json()["data"]["warehouse"]

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

    def create_farm(self, code):
        response = self.post(self.admin, "/farms", {"code": code, "name": "种植测试农场", "ownerName": "测试负责人"})
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["farm"]

    def create_variety(self):
        response = self.post(self.admin, "/crop-varieties", {
            "cropTypeId": self.crop_type["id"], "code": "K326", "name": "K326",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["variety"]

    def cycle_payload(self, code="CYCLE-01", area="40", start=None, end=None):
        start = start or date.today().isoformat()
        end = end or (date.today() + timedelta(days=90)).isoformat()
        return {
            "farmId": self.farm["id"], "cycleCode": code, "plotId": self.plot["id"],
            "cropTypeId": self.crop_type["id"], "varietyId": self.variety["id"], "areaMu": area,
            "plannedStartDate": start, "plannedEndDate": end, "notes": "春季种植",
        }

    def test_create_list_detail_and_idempotency(self):
        response = self.post(self.admin, "/crop-cycles", self.cycle_payload())
        self.assertEqual(response.status_code, 201)
        cycle = response.get_json()["data"]["cycle"]
        self.assertEqual(cycle["cycleCode"], "CYCLE-01")
        self.assertEqual(cycle["areaMu"], "40")
        repeated = self.post(self.admin, "/crop-cycles", self.cycle_payload(code="cycle-01"))
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["data"]["cycle"]["id"], cycle["id"])
        listed = self.viewer.get("/api/v1/crop-cycles", query_string={"farmId": self.farm["id"]})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["pagination"]["total"], 1)
        detail = self.viewer.get(f"/api/v1/crop-cycles/{cycle['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["data"]["cycle"]["plotName"], "东山烟田")

    def test_area_and_overlap_constraints(self):
        too_large = self.post(self.admin, "/crop-cycles", self.cycle_payload(area="101"))
        self.assertEqual(too_large.status_code, 409)
        self.assertEqual(too_large.get_json()["code"], "CROP_CYCLE_AREA_EXCEEDED")
        self.assertEqual(self.post(self.admin, "/crop-cycles", self.cycle_payload(area="60")).status_code, 201)
        overlap = self.post(self.admin, "/crop-cycles", self.cycle_payload(code="CYCLE-02", area="41"))
        self.assertEqual(overlap.status_code, 409)
        self.assertEqual(overlap.get_json()["code"], "CROP_CYCLE_OVERLAP_AREA_EXCEEDED")
        separate = self.post(self.admin, "/crop-cycles", self.cycle_payload(
            code="CYCLE-03", area="50", start=(date.today() + timedelta(days=91)).isoformat(),
            end=(date.today() + timedelta(days=180)).isoformat(),
        ))
        self.assertEqual(separate.status_code, 201)

    def test_status_rules_and_viewer_write_denied(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload()).get_json()["data"]["cycle"]
        denied = self.post(self.viewer, "/crop-cycles", self.cycle_payload(code="DENIED"))
        self.assertEqual(denied.status_code, 403)
        active = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["data"]["cycle"]["status"], "ACTIVE")
        invalid = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "PLANNED"})
        self.assertEqual(invalid.status_code, 409)
        future = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
            "status": "HARVESTING", "actualStartDate": (date.today() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(future.status_code, 400)

    def test_cross_farm_references_rejected(self):
        other_farm = self.create_farm("CROP-002")
        other_plot = self.post(self.admin, "/plots", {
            "farmId": other_farm["id"], "code": "OTHER-01", "name": "其他地块", "areaMu": "20",
        }).get_json()["data"]["plot"]
        payload = self.cycle_payload()
        payload["plotId"] = other_plot["id"]
        response = self.post(self.admin, "/crop-cycles", payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "PLOT_FARM_MISMATCH")

    def test_field_operations_require_active_cycle_and_validate_dates_area(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload(area="40")).get_json()["data"]["cycle"]
        planned = self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "LAND_PREPARATION",
            "operationDate": date.today().isoformat(), "areaMu": "20",
        })
        self.assertEqual(planned.status_code, 409)
        self.assertEqual(planned.get_json()["code"], "CROP_CYCLE_OPERATION_STATUS_INVALID")
        self.assertEqual(self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"}).status_code, 200)

        too_large = self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "LAND_PREPARATION",
            "operationDate": date.today().isoformat(), "areaMu": "41",
        })
        self.assertEqual(too_large.status_code, 409)
        self.assertEqual(too_large.get_json()["code"], "FIELD_OPERATION_AREA_EXCEEDED")
        before = self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "SOWING",
            "operationDate": (date.today() - timedelta(days=1)).isoformat(), "areaMu": "20",
        })
        self.assertEqual(before.status_code, 409)
        self.assertEqual(before.get_json()["code"], "FIELD_OPERATION_BEFORE_START")
        future = self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "SOWING",
            "operationDate": (date.today() + timedelta(days=1)).isoformat(), "areaMu": "20",
        })
        self.assertEqual(future.status_code, 400)

        created = self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "LAND_PREPARATION",
            "operationDate": date.today().isoformat(), "areaMu": "40", "laborHours": "8",
            "machineHours": "2.5", "laborCost": "320", "serviceCost": "100", "notes": "机械整地",
        })
        self.assertEqual(created.status_code, 201)
        operation = created.get_json()["data"]["operation"]
        self.assertEqual(operation["laborCost"], "320.00")
        listed = self.viewer.get("/api/v1/field-operations", query_string={"farmId": self.farm["id"], "cropCycleId": cycle["id"]})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["pagination"]["total"], 1)

    def test_field_operation_cross_farm_and_viewer_write_are_rejected(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload()).get_json()["data"]["cycle"]
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
        denied = self.post(self.viewer, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "IRRIGATION",
            "operationDate": date.today().isoformat(), "areaMu": "10",
        })
        self.assertEqual(denied.status_code, 403)
        other_farm = self.create_farm("CROP-003")
        cross = self.post(self.admin, "/field-operations", {
            "farmId": other_farm["id"], "cropCycleId": cycle["id"], "operationType": "IRRIGATION",
            "operationDate": date.today().isoformat(), "areaMu": "10",
        })
        self.assertEqual(cross.status_code, 409)
        self.assertEqual(cross.get_json()["code"], "CROP_CYCLE_FARM_MISMATCH")

    def test_harvest_batch_rules_list_and_idempotency(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload()).get_json()["data"]["cycle"]
        payload = {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": "harvest-01",
            "harvestDate": date.today().isoformat(), "grossWeight": "120.5", "netWeight": "116",
            "unitId": self.kg_unit["id"], "warehouseId": self.warehouse["id"], "notes": "第一采",
        }
        blocked = self.post(self.admin, "/harvest-batches", payload)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "CROP_CYCLE_HARVEST_STATUS_INVALID")
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        invalid = {**payload, "netWeight": "121"}
        self.assertEqual(self.post(self.admin, "/harvest-batches", invalid).status_code, 400)
        created = self.post(self.admin, "/harvest-batches", payload)
        self.assertEqual(created.status_code, 201)
        batch = created.get_json()["data"]["batch"]
        self.assertEqual(batch["harvestNo"], "HARVEST-01")
        self.assertEqual(batch["warehouseName"], "农产品暂存仓")
        repeated = self.post(self.admin, "/harvest-batches", payload)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["data"]["batch"]["id"], batch["id"])
        listed = self.viewer.get("/api/v1/harvest-batches", query_string={
            "farmId": self.farm["id"], "cropCycleId": cycle["id"],
        })
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["total"], 1)

    def test_tobacco_curing_lifecycle_and_weight_limits(self):
        start_at = datetime.now().replace(microsecond=0) - timedelta(hours=2)
        end_at = start_at + timedelta(hours=1)
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload(
            start=(date.today() - timedelta(days=1)).isoformat(),
        )).get_json()["data"]["cycle"]
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
            "status": "ACTIVE", "actualStartDate": (date.today() - timedelta(days=1)).isoformat(),
        })
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        self.post(self.admin, "/harvest-batches", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": "HARVEST-01",
            "harvestDate": date.today().isoformat(), "grossWeight": "120", "netWeight": "100",
            "unitId": self.kg_unit["id"], "warehouseId": self.warehouse["id"],
        })
        payload = {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "curingNo": "curing-01",
            "startAt": start_at.isoformat(), "inputWeight": "80",
            "unitId": self.kg_unit["id"], "notes": "第一炉",
        }
        denied = self.post(self.viewer, "/tobacco-curing-batches", payload)
        self.assertEqual(denied.status_code, 403)
        too_much = self.post(self.admin, "/tobacco-curing-batches", {**payload, "inputWeight": "101"})
        self.assertEqual(too_much.status_code, 409)
        self.assertEqual(too_much.get_json()["code"], "CURING_INPUT_EXCEEDS_HARVEST")
        created = self.post(self.admin, "/tobacco-curing-batches", payload)
        self.assertEqual(created.status_code, 201)
        batch = created.get_json()["data"]["batch"]
        self.assertEqual(batch["curingNo"], "CURING-01")
        self.assertEqual(self.post(self.admin, "/tobacco-curing-batches", payload).status_code, 200)
        exceeded = self.patch(self.admin, f"/tobacco-curing-batches/{batch['id']}/complete", {
            "endAt": end_at.isoformat(), "outputWeight": "81",
            "fuelCost": "120", "electricityCost": "35",
        })
        self.assertEqual(exceeded.status_code, 409)
        completed_payload = {
            "endAt": end_at.isoformat(), "outputWeight": "32",
            "fuelCost": "120", "electricityCost": "35",
        }
        completed = self.patch(self.admin, f"/tobacco-curing-batches/{batch['id']}/complete", completed_payload)
        self.assertEqual(completed.status_code, 200)
        result = completed.get_json()["data"]["batch"]
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["curingEfficiency"], "40.00")
        costs = self.admin.get(f"/api/v1/crop-cycles/{cycle['id']}/cost-summary").get_json()["data"]
        self.assertEqual(costs["curingCost"], "155.00")
        self.assertEqual(costs["totalCost"], "155.00")
        self.assertEqual(self.patch(self.admin, f"/tobacco-curing-batches/{batch['id']}/complete", completed_payload).status_code, 200)
        listed = self.viewer.get("/api/v1/tobacco-curing-batches", query_string={
            "farmId": self.farm["id"], "cropCycleId": cycle["id"],
        })
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
