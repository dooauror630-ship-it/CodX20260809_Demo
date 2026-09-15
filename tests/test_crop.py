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
        self.other_unit = next(item for item in catalogs["units"] if item["id"] != self.kg_unit["id"])
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

    def create_crop_variety(self, crop_type, code):
        response = self.post(self.admin, "/crop-varieties", {
            "cropTypeId": crop_type["id"], "code": code, "name": code,
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

    def test_grading_records_enforce_harvest_net_weight(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload()).get_json()["data"]["cycle"]
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        harvest = self.post(self.admin, "/harvest-batches", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": "GRADE-HARVEST",
            "harvestDate": date.today().isoformat(), "grossWeight": "105", "netWeight": "100",
            "unitId": self.kg_unit["id"], "warehouseId": self.warehouse["id"],
        }).get_json()["data"]["batch"]
        payload = {
            "farmId": self.farm["id"], "harvestBatchId": harvest["id"], "gradeCode": "c1f",
            "quantity": "60", "unitPriceReference": "28.5", "notes": "中桔一",
        }
        self.assertEqual(self.post(self.viewer, "/grading-records", payload).status_code, 403)
        created = self.post(self.admin, "/grading-records", payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["data"]["record"]["referenceValue"], "1710.00")
        self.assertEqual(self.post(self.admin, "/grading-records", payload).status_code, 200)
        duplicate = self.post(self.admin, "/grading-records", {**payload, "quantity": "59"})
        self.assertEqual(duplicate.status_code, 409)
        exceeded = self.post(self.admin, "/grading-records", {
            **payload, "gradeCode": "B2F", "quantity": "41",
        })
        self.assertEqual(exceeded.status_code, 409)
        self.assertEqual(exceeded.get_json()["code"], "GRADING_QUANTITY_EXCEEDED")
        listed = self.viewer.get("/api/v1/grading-records", query_string={
            "farmId": self.farm["id"], "harvestBatchId": harvest["id"],
        }).get_json()["data"]
        self.assertEqual(listed["gradedQuantity"], "60")
        self.assertEqual(listed["ungradedQuantity"], "40")
        self.assertEqual(listed["referenceValue"], "1710.00")

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

    def test_analysis_zero_state_and_close_requires_harvest(self):
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload()).get_json()["data"]["cycle"]
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
        direct_close = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "CLOSED"})
        self.assertEqual(direct_close.status_code, 409)
        self.assertEqual(direct_close.get_json()["code"], "CROP_CYCLE_STATUS_INVALID")
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        close = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "CLOSED"})
        self.assertEqual(close.status_code, 409)
        self.assertEqual(close.get_json()["code"], "CROP_CYCLE_CLOSE_REQUIRES_HARVEST")

        analysis = self.viewer.get(f"/api/v1/crop-cycles/{cycle['id']}/analysis")
        self.assertEqual(analysis.status_code, 200)
        data = analysis.get_json()["data"]
        self.assertIsNone(data["unitName"])
        self.assertEqual(data["harvest"]["totalNetWeight"], "0.00")
        self.assertEqual(data["harvest"]["yieldPerMu"], "0.00")
        self.assertEqual(data["grading"]["gradeStructure"], [])
        self.assertEqual(data["cost"]["unitOutputCost"], "0.00")

    def test_analysis_aggregates_production_and_close_gates_curing(self):
        start_at = datetime.now().replace(microsecond=0) - timedelta(hours=2)
        cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload(
            start=(date.today() - timedelta(days=1)).isoformat(),
        )).get_json()["data"]["cycle"]
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
            "status": "ACTIVE", "actualStartDate": (date.today() - timedelta(days=1)).isoformat(),
        })
        self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        harvest_payload = {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": "ANALYSIS-01",
            "harvestDate": date.today().isoformat(), "grossWeight": "105", "netWeight": "100",
            "unitId": self.kg_unit["id"], "warehouseId": self.warehouse["id"],
        }
        harvest = self.post(self.admin, "/harvest-batches", harvest_payload).get_json()["data"]["batch"]
        mismatched = self.post(self.admin, "/harvest-batches", {
            **harvest_payload, "harvestNo": "ANALYSIS-02", "unitId": self.other_unit["id"],
        })
        self.assertEqual(mismatched.status_code, 409)
        self.assertEqual(mismatched.get_json()["code"], "HARVEST_UNIT_MISMATCH")
        self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "OTHER",
            "operationDate": date.today().isoformat(), "areaMu": "40", "laborCost": "200",
            "serviceCost": "50",
        })
        for grade_code, quantity, price in (("C1F", "60", "28.5"), ("B2F", "20", "20")):
            self.post(self.admin, "/grading-records", {
                "farmId": self.farm["id"], "harvestBatchId": harvest["id"], "gradeCode": grade_code,
                "quantity": quantity, "unitPriceReference": price,
            })
        curing = self.post(self.admin, "/tobacco-curing-batches", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "curingNo": "ANALYSIS-CURING",
            "startAt": start_at.isoformat(), "inputWeight": "80", "unitId": self.kg_unit["id"],
        }).get_json()["data"]["batch"]
        close = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "CLOSED"})
        self.assertEqual(close.status_code, 409)
        self.assertEqual(close.get_json()["code"], "CROP_CYCLE_CLOSE_CURING_IN_PROGRESS")
        self.patch(self.admin, f"/tobacco-curing-batches/{curing['id']}/complete", {
            "endAt": (start_at + timedelta(hours=1)).isoformat(), "outputWeight": "40",
            "fuelCost": "120", "electricityCost": "35",
        })

        analysis = self.viewer.get(f"/api/v1/crop-cycles/{cycle['id']}/analysis").get_json()["data"]
        self.assertEqual(analysis["unitName"], self.kg_unit["name"])
        self.assertEqual(analysis["harvest"], {
            "batchCount": 1, "totalNetWeight": "100.00", "yieldPerMu": "2.50",
        })
        self.assertEqual(analysis["curing"]["efficiency"], "50.00")
        self.assertEqual(analysis["grading"]["gradedQuantity"], "80.00")
        self.assertEqual(analysis["grading"]["ungradedQuantity"], "20.00")
        self.assertEqual(analysis["grading"]["gradingRate"], "80.00")
        self.assertEqual(analysis["grading"]["referenceValue"], "2110.00")
        self.assertEqual(analysis["grading"]["gradeStructure"][0]["gradeCode"], "B2F")
        self.assertEqual(analysis["cost"]["totalCost"], "405.00")
        self.assertEqual(analysis["cost"]["unitOutputCost"], "4.05")
        closed = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "CLOSED"})
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.get_json()["data"]["cycle"]["status"], "CLOSED")

    def test_crop_operation_suggestions_cover_supported_crops(self):
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        crop_types = {item["code"]: item for item in catalogs["cropTypes"]}
        start = date.today() - timedelta(days=50)
        expected_types = {
            "GARLIC": {"LAND_PREPARATION", "SOWING", "WEEDING", "FERTILIZATION", "IRRIGATION", "PEST_CONTROL"},
            "RICE": {"LAND_PREPARATION", "SOWING", "TRANSPLANTING", "IRRIGATION", "FERTILIZATION", "PEST_CONTROL"},
            "RAPESEED": {"LAND_PREPARATION", "SOWING", "WEEDING", "FERTILIZATION", "PEST_CONTROL"},
        }
        cycles = {}
        for index, (code, operation_types) in enumerate(expected_types.items(), start=1):
            crop_type = crop_types[code]
            variety = self.create_crop_variety(crop_type, f"{code}-V1")
            payload = self.cycle_payload(
                code=f"{code}-01",
                area="20",
                start=start.isoformat(),
                end=(date.today() + timedelta(days=100)).isoformat(),
            )
            payload.update({"cropTypeId": crop_type["id"], "varietyId": variety["id"]})
            cycle = self.post(self.admin, "/crop-cycles", payload).get_json()["data"]["cycle"]
            self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
                "status": "ACTIVE", "actualStartDate": start.isoformat(),
            })
            response = self.viewer.get(f"/api/v1/crop-cycles/{cycle['id']}/operation-suggestions")
            self.assertEqual(response.status_code, 200)
            suggestions = response.get_json()["data"]["items"]
            self.assertEqual({item["operationType"] for item in suggestions}, operation_types)
            self.assertEqual(suggestions[0]["suggestedDate"], start.isoformat())
            self.assertTrue(any(item["overdue"] for item in suggestions))
            cycles[code] = cycle

        garlic = cycles["GARLIC"]
        self.post(self.admin, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": garlic["id"], "operationType": "LAND_PREPARATION",
            "operationDate": date.today().isoformat(), "areaMu": "20",
        })
        suggestions = self.viewer.get(
            f"/api/v1/crop-cycles/{garlic['id']}/operation-suggestions"
        ).get_json()["data"]["items"]
        land_preparation = next(item for item in suggestions if item["operationType"] == "LAND_PREPARATION")
        self.assertTrue(land_preparation["recorded"])
        self.assertFalse(land_preparation["overdue"])

        tobacco = self.post(self.admin, "/crop-cycles", self.cycle_payload(
            code="TOBACCO-SUGGESTIONS", area="20", start=(date.today() + timedelta(days=101)).isoformat(),
            end=(date.today() + timedelta(days=190)).isoformat(),
        )).get_json()["data"]["cycle"]
        response = self.viewer.get(f"/api/v1/crop-cycles/{tobacco['id']}/operation-suggestions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["items"], [])

    def test_crop_farm_analysis_compares_cycles_without_combining_units(self):
        cycles = []
        for index, unit in enumerate((self.kg_unit, self.other_unit), start=1):
            cycle = self.post(self.admin, "/crop-cycles", self.cycle_payload(
                code=f"COMPARE-{index}", area="40",
            )).get_json()["data"]["cycle"]
            self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "ACTIVE"})
            self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
            self.post(self.admin, "/harvest-batches", {
                "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": f"COMPARE-H-{index}",
                "harvestDate": date.today().isoformat(), "grossWeight": "110", "netWeight": "100",
                "unitId": unit["id"], "warehouseId": self.warehouse["id"],
            })
            cycles.append((cycle, unit))

        response = self.viewer.get("/api/v1/crop-analysis", query_string={"farmId": self.farm["id"]})
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["data"]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual({item["cycleId"] for item in items}, {cycle["id"] for cycle, _unit in cycles})
        self.assertEqual({item["unitName"] for item in items}, {unit["name"] for _cycle, unit in cycles})
        self.assertTrue(all(item["totalNetWeight"] == "100.00" for item in items))

        other_farm = self.create_farm("CROP-ANALYSIS-OTHER")
        denied = self.viewer.get("/api/v1/crop-analysis", query_string={"farmId": other_farm["id"]})
        self.assertEqual(denied.status_code, 403)


if __name__ == "__main__":
    unittest.main()
