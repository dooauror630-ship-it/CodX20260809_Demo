import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user
from backend.app.modules.inventory.purchase_service import reconcile_inventory


class PurchaseInventoryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-secret-key",
        })
        self.admin = self.app.test_client()
        self.operator = self.app.test_client()
        self.manager = self.app.test_client()
        self.viewer = self.app.test_client()
        self.outsider = self.app.test_client()
        with self.app.app_context():
            ensure_admin_user("admin", "123456")
        users = {}
        for key, client, name in (
            ("operator", self.operator, "采购操作员"),
            ("manager", self.manager, "农场负责人"),
            ("viewer", self.viewer, "库存查看员"),
            ("outsider", self.outsider, "其他农场用户"),
        ):
            response = self.post(client, "/auth/register", {
                "username": f"purchase_{key}",
                "password": "FarmPass123",
                "displayName": name,
            })
            users[key] = response.get_json()["user"]["id"]
        self.post(self.admin, "/auth/login", {"username": "admin", "password": "123456"})
        self.farm = self.create_farm("PURCHASE-01", "采购验收农场")
        for key, role in (("operator", "operator"), ("manager", "manager"), ("viewer", "viewer")):
            self.post(self.admin, f"/farms/{self.farm['id']}/members", {
                "userId": users[key],
                "roleCode": role,
            })
        self.warehouse = self.create_warehouse(self.farm["id"], "MAIN-WH", "生产物资主仓")
        self.secondary_warehouse = self.create_warehouse(self.farm["id"], "SECOND-WH", "生产物资分仓")
        self.barn = self.create_barn(self.farm["id"], "PIG-BARN", "育肥一舍")
        category = self.create_category(self.farm["id"], "FEED")
        unit_id = next(
            unit["id"]
            for unit in self.admin.get("/api/v1/catalogs").get_json()["data"]["units"]
            if unit["code"] == "KG"
        )
        self.item = self.create_item(self.farm["id"], category["id"], unit_id, "PIG-FEED", True)
        self.supplier = self.create_supplier(self.farm["id"], "SUP-01")

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

    def create_warehouse(self, farm_id, code, name="生产物资仓"):
        response = self.post(self.admin, "/warehouses", {
            "farmId": farm_id,
            "code": code,
            "name": name,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["warehouse"]

    def create_barn(self, farm_id, code, name):
        response = self.post(self.admin, "/barns", {
            "farmId": farm_id,
            "code": code,
            "name": name,
            "barnType": "pig",
            "capacity": 180,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["barn"]

    def create_category(self, farm_id, code):
        response = self.post(self.admin, "/item-categories", {
            "farmId": farm_id,
            "code": code,
            "name": "饲料",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["category"]

    def create_item(
        self,
        farm_id,
        category_id,
        unit_id,
        code,
        lot_tracking,
        item_type="feed",
        name="育肥猪全价料",
    ):
        response = self.post(self.admin, "/items", {
            "farmId": farm_id,
            "categoryId": category_id,
            "unitId": unit_id,
            "code": code,
            "name": name,
            "itemType": item_type,
            "safetyStock": 5,
            "lotTracking": lot_tracking,
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["item"]

    def create_supplier(self, farm_id, code):
        response = self.post(self.admin, "/suppliers", {
            "farmId": farm_id,
            "code": code,
            "name": "放心饲料供应商",
            "contact": "李经理",
            "phone": "13800000000",
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()["data"]["supplier"]

    def purchase_input(
        self,
        order_no,
        quantity="10",
        unit_price="12.345",
        lot_no="LOT-001",
        expires_on="2027-08-15",
    ):
        return {
            "farmId": self.farm["id"],
            "orderNo": order_no,
            "supplierId": self.supplier["id"],
            "warehouseId": self.warehouse["id"],
            "orderDate": "2026-08-15",
            "notes": "采购验收",
            "lines": [{
                "itemId": self.item["id"],
                "quantity": quantity,
                "unitPrice": unit_price,
                "lotNo": lot_no,
                "expiresOn": expires_on,
            }],
        }

    def transfer_input(self, document_no, quantity="4", lot_no="LOT-001"):
        return {
            "farmId": self.farm["id"],
            "documentNo": document_no,
            "fromWarehouseId": self.warehouse["id"],
            "toWarehouseId": self.secondary_warehouse["id"],
            "transferDate": "2026-08-15",
            "itemId": self.item["id"],
            "quantity": quantity,
            "lotNo": lot_no,
        }

    def production_operation_input(
        self,
        document_no,
        operation_type="issue",
        quantity="6",
        lot_no="LOT-001",
        cost_object_type="barn",
    ):
        payload = {
            "farmId": self.farm["id"],
            "documentNo": document_no,
            "operationType": operation_type,
            "operationDate": "2026-08-15",
            "warehouseId": self.warehouse["id"],
            "itemId": self.item["id"],
            "quantity": quantity,
            "lotNo": lot_no,
            "costObjectType": cost_object_type,
        }
        if cost_object_type == "barn":
            payload["costObjectId"] = self.barn["id"]
        return payload

    def purchase_return_input(
        self,
        document_no,
        purchase,
        quantity="2",
        warehouse_id=None,
        purchase_line_id=None,
        return_date="2026-08-16",
    ):
        return {
            "farmId": self.farm["id"],
            "documentNo": document_no,
            "purchaseId": purchase["id"],
            "purchaseLineId": purchase_line_id or purchase["lines"][0]["id"],
            "returnDate": return_date,
            "warehouseId": warehouse_id or self.warehouse["id"],
            "quantity": quantity,
        }

    def inventory_count_input(self, count_no, warehouse_id=None, count_date="2026-08-16"):
        return {
            "farmId": self.farm["id"],
            "countNo": count_no,
            "warehouseId": warehouse_id or self.warehouse["id"],
            "countDate": count_date,
            "notes": "月度饲料盘点",
        }

    def test_posting_is_idempotent_and_balances_reconcile(self):
        created = self.post(self.operator, "/purchases", self.purchase_input("PO-001"))
        self.assertEqual(created.status_code, 201)
        purchase = created.get_json()["data"]["purchase"]
        self.assertEqual(purchase["status"], "DRAFT")
        self.assertEqual(purchase["totalAmount"], "123.45")
        before = self.operator.get("/api/v1/stocks", query_string={"farmId": self.farm["id"]})
        self.assertEqual(before.get_json()["data"]["pagination"]["total"], 0)

        posted = self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": 1})
        self.assertEqual(posted.status_code, 200)
        self.assertEqual(posted.get_json()["data"]["purchase"]["status"], "POSTED")
        repeated = self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": 1})
        self.assertEqual(repeated.status_code, 200)

        stocks = self.operator.get("/api/v1/stocks", query_string={"farmId": self.farm["id"]}).get_json()["data"]
        self.assertEqual(stocks["pagination"]["total"], 1)
        self.assertEqual(stocks["items"][0]["quantity"], "10")
        self.assertEqual(stocks["items"][0]["averageCost"], "12.345")
        self.assertEqual(stocks["summary"]["totalValue"], "123.45")
        ledger = self.operator.get(
            "/api/v1/stock-ledger", query_string={"farmId": self.farm["id"]}
        ).get_json()["data"]
        self.assertEqual(ledger["pagination"]["total"], 1)
        self.assertEqual(ledger["items"][0]["lotNo"], "LOT-001")

        second = self.post(self.operator, "/purchases", self.purchase_input(
            "PO-002", quantity="10", unit_price="20", lot_no="LOT-002"
        )).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{second['id']}/post", {"version": second["version"]})
        stock = self.operator.get(
            "/api/v1/stocks", query_string={"farmId": self.farm["id"]}
        ).get_json()["data"]["items"][0]
        self.assertEqual(stock["quantity"], "20")
        self.assertEqual(stock["averageCost"], "16.1725")
        self.assertEqual(stock["inventoryValue"], "323.45")
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_roles_versions_and_cancellation_are_enforced(self):
        denied_purchase = self.post(self.viewer, "/purchases", self.purchase_input("PO-DENIED"))
        self.assertEqual(denied_purchase.status_code, 403)
        denied_supplier = self.post(self.operator, "/suppliers", {
            "farmId": self.farm["id"],
            "code": "SUP-DENIED",
            "name": "无权供应商",
        })
        self.assertEqual(denied_supplier.status_code, 403)
        manager_supplier = self.post(self.manager, "/suppliers", {
            "farmId": self.farm["id"],
            "code": "SUP-02",
            "name": "负责人新增供应商",
        })
        self.assertEqual(manager_supplier.status_code, 201)

        purchase = self.post(self.operator, "/purchases", self.purchase_input("PO-EDIT")).get_json()["data"]["purchase"]
        stale_input = {**self.purchase_input("PO-EDIT"), "version": purchase["version"] + 1}
        stale = self.patch(self.operator, f"/purchases/{purchase['id']}", stale_input)
        self.assertEqual(stale.status_code, 409)
        updated = self.patch(self.operator, f"/purchases/{purchase['id']}", {
            **self.purchase_input("PO-EDIT", unit_price="13"),
            "version": purchase["version"],
        })
        self.assertEqual(updated.status_code, 200)
        current = updated.get_json()["data"]["purchase"]
        cancelled = self.post(self.operator, f"/purchases/{purchase['id']}/cancel", {
            "version": current["version"],
        })
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["data"]["purchase"]["status"], "CANCELLED")
        rejected_post = self.post(self.operator, f"/purchases/{purchase['id']}/post", {
            "version": cancelled.get_json()["data"]["purchase"]["version"],
        })
        self.assertEqual(rejected_post.status_code, 409)
        outsider = self.outsider.get("/api/v1/purchases", query_string={"farmId": self.farm["id"]})
        self.assertEqual(outsider.status_code, 403)

    def test_transfer_moves_stock_once_and_enforces_roles_and_availability(self):
        purchase = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-TRANSFER", quantity="10"),
        ).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})

        denied = self.post(self.viewer, "/stock-transfers", self.transfer_input("TR-DENIED"))
        self.assertEqual(denied.status_code, 403)
        created = self.post(self.operator, "/stock-transfers", self.transfer_input("TR-001"))
        self.assertEqual(created.status_code, 201)
        transfer = created.get_json()["data"]["transfer"]
        self.assertEqual(transfer["documentType"], "WAREHOUSE_TRANSFER")
        self.assertEqual(transfer["quantity"], "4")
        self.assertEqual(transfer["unitCost"], "12.345")

        repeated = self.post(self.operator, "/stock-transfers", self.transfer_input("TR-001"))
        self.assertEqual(repeated.status_code, 200)
        changed_duplicate = self.post(
            self.operator,
            "/stock-transfers",
            self.transfer_input("TR-001", quantity="3"),
        )
        self.assertEqual(changed_duplicate.status_code, 409)

        insufficient = self.post(
            self.operator,
            "/stock-transfers",
            self.transfer_input("TR-TOO-MUCH", quantity="7"),
        )
        self.assertEqual(insufficient.status_code, 409)
        self.assertEqual(insufficient.get_json()["code"], "STOCK_INSUFFICIENT")
        wrong_lot = self.post(
            self.manager,
            "/stock-transfers",
            self.transfer_input("TR-WRONG-LOT", quantity="1", lot_no="LOT-MISSING"),
        )
        self.assertEqual(wrong_lot.status_code, 409)
        self.assertEqual(wrong_lot.get_json()["code"], "LOT_STOCK_INSUFFICIENT")

        stocks = self.viewer.get(
            "/api/v1/stocks",
            query_string={"farmId": self.farm["id"], "pageSize": 100},
        ).get_json()["data"]
        by_warehouse = {item["warehouseId"]: item for item in stocks["items"]}
        self.assertEqual(by_warehouse[self.warehouse["id"]]["quantity"], "6")
        self.assertEqual(by_warehouse[self.secondary_warehouse["id"]]["quantity"], "4")
        self.assertEqual(by_warehouse[self.secondary_warehouse["id"]]["averageCost"], "12.345")

        ledger = self.viewer.get(
            "/api/v1/stock-ledger",
            query_string={"farmId": self.farm["id"], "keyword": "TR-001"},
        ).get_json()["data"]
        self.assertEqual(ledger["pagination"]["total"], 2)
        self.assertEqual({item["quantityDelta"] for item in ledger["items"]}, {"-4", "4"})
        self.assertTrue(all(item["sourceId"] is None for item in ledger["items"]))
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_production_issue_and_return_preserve_cost_and_limit_returns(self):
        purchase = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-ISSUE", quantity="10"),
        ).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})

        denied = self.post(
            self.viewer,
            "/production-stock-operations",
            self.production_operation_input("MAT-DENIED"),
        )
        self.assertEqual(denied.status_code, 403)
        wrong_lot = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input("MAT-WRONG-LOT", quantity="1", lot_no="LOT-MISSING"),
        )
        self.assertEqual(wrong_lot.status_code, 409)
        self.assertEqual(wrong_lot.get_json()["code"], "LOT_STOCK_INSUFFICIENT")

        created = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input("MAT-ISSUE-1"),
        )
        self.assertEqual(created.status_code, 201)
        issue = created.get_json()["data"]["operation"]
        self.assertEqual(issue["documentType"], "PRODUCTION_ISSUE")
        self.assertEqual(issue["quantity"], "6")
        self.assertEqual(issue["unitCost"], "12.345")
        self.assertEqual(issue["costObjectType"], "barn")
        self.assertEqual(issue["costObjectId"], self.barn["id"])

        repeated = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input("MAT-ISSUE-1"),
        )
        self.assertEqual(repeated.status_code, 200)
        changed_duplicate = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input("MAT-ISSUE-1", quantity="5"),
        )
        self.assertEqual(changed_duplicate.status_code, 409)

        second = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-AFTER-ISSUE", quantity="10", unit_price="20", lot_no="LOT-002"),
        ).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{second['id']}/post", {"version": second["version"]})

        returned = self.post(
            self.manager,
            "/production-stock-operations",
            self.production_operation_input("MAT-RETURN-1", operation_type="return", quantity="2"),
        )
        self.assertEqual(returned.status_code, 201)
        returned_operation = returned.get_json()["data"]["operation"]
        self.assertEqual(returned_operation["documentType"], "PRODUCTION_RETURN")
        self.assertEqual(returned_operation["unitCost"], "12.345")
        repeated_return = self.post(
            self.manager,
            "/production-stock-operations",
            self.production_operation_input("MAT-RETURN-1", operation_type="return", quantity="2"),
        )
        self.assertEqual(repeated_return.status_code, 200)

        excessive_return = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input("MAT-RETURN-TOO-MUCH", operation_type="return", quantity="5"),
        )
        self.assertEqual(excessive_return.status_code, 409)
        self.assertEqual(excessive_return.get_json()["code"], "RETURN_EXCEEDS_ISSUED")
        self.assertEqual(excessive_return.get_json()["details"]["available"], "4")
        wrong_object = self.post(
            self.operator,
            "/production-stock-operations",
            self.production_operation_input(
                "MAT-RETURN-WRONG-OBJECT",
                operation_type="return",
                quantity="1",
                cost_object_type="farm",
            ),
        )
        self.assertEqual(wrong_object.status_code, 409)
        self.assertEqual(wrong_object.get_json()["code"], "RETURN_EXCEEDS_ISSUED")

        stock = self.viewer.get(
            "/api/v1/stocks",
            query_string={"farmId": self.farm["id"]},
        ).get_json()["data"]["items"][0]
        self.assertEqual(stock["quantity"], "16")
        self.assertEqual(stock["averageCost"], "17.1294")
        ledger = self.viewer.get(
            "/api/v1/stock-ledger",
            query_string={"farmId": self.farm["id"], "keyword": "MAT-"},
        ).get_json()["data"]
        self.assertEqual(ledger["pagination"]["total"], 2)
        self.assertEqual({item["quantityDelta"] for item in ledger["items"]}, {"-6", "2"})
        self.assertTrue(all(item["costObjectType"] == "BARN" for item in ledger["items"]))
        self.assertTrue(all(item["costObjectId"] == self.barn["id"] for item in ledger["items"]))
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_crop_cycle_production_issue_validates_scope_status_dates_and_is_idempotent(self):
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        crop_type = next(item for item in catalogs["cropTypes"] if item["code"] == "TOBACCO")
        variety = crop_type["varieties"][0] if crop_type["varieties"] else self.post(self.admin, "/crop-varieties", {
            "cropTypeId": crop_type["id"], "code": "CROP-STOCK-V", "name": "投入品测试品种",
        }).get_json()["data"]["variety"]
        plot = self.post(self.admin, "/plots", {
            "farmId": self.farm["id"], "code": "CROP-STOCK-01", "name": "投入品测试地块", "areaMu": "80",
        }).get_json()["data"]["plot"]
        cycle_payload = {
            "farmId": self.farm["id"],
            "cycleCode": "CROP-STOCK-001",
            "plotId": plot["id"],
            "cropTypeId": crop_type["id"],
            "varietyId": variety["id"],
            "areaMu": "40",
            "plannedStartDate": "2026-08-01",
            "plannedEndDate": "2026-08-31",
        }
        cycle = self.post(self.admin, "/crop-cycles", cycle_payload).get_json()["data"]["cycle"]
        purchase = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-CROP-CYCLE", quantity="10"),
        ).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})

        planned = self.production_operation_input("CROP-PLANNED", quantity="1", cost_object_type="crop_cycle")
        planned["costObjectId"] = cycle["id"]
        planned["operationDate"] = "2026-08-15"
        response = self.post(self.operator, "/production-stock-operations", planned)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "CROP_CYCLE_NOT_ACTIVE")

        active = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
            "status": "ACTIVE", "actualStartDate": "2026-08-01",
        })
        self.assertEqual(active.status_code, 200)
        before = dict(planned, documentNo="CROP-BEFORE", operationDate="2026-07-31")
        response = self.post(self.operator, "/production-stock-operations", before)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "PRODUCTION_DATE_BEFORE_CROP_CYCLE")
        after = dict(planned, documentNo="CROP-AFTER", operationDate="2026-09-03")
        response = self.post(self.operator, "/production-stock-operations", after)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "PRODUCTION_DATE_AFTER_CROP_CYCLE")

        created = dict(planned, documentNo="CROP-ISSUE-001")
        response = self.post(self.operator, "/production-stock-operations", created)
        self.assertEqual(response.status_code, 201)
        operation = response.get_json()["data"]["operation"]
        self.assertEqual(operation["costObjectType"], "crop_cycle")
        self.assertEqual(operation["costObjectId"], cycle["id"])
        repeated = self.post(self.operator, "/production-stock-operations", created)
        self.assertEqual(repeated.status_code, 200)

        second_issue = dict(planned, documentNo="CROP-ISSUE-002", quantity="2")
        second_response = self.post(self.operator, "/production-stock-operations", second_issue)
        self.assertEqual(second_response.status_code, 201)
        field_operation_response = self.post(self.manager, "/field-operations", {
            "farmId": self.farm["id"],
            "cropCycleId": cycle["id"],
            "operationType": "FERTILIZATION",
            "operationDate": "2026-08-15",
            "areaMu": "40",
            "laborCost": "100",
            "serviceCost": "20",
            "notes": "追肥",
        })
        self.assertEqual(field_operation_response.status_code, 201)
        field_operation = field_operation_response.get_json()["data"]["operation"]
        available = self.viewer.get("/api/v1/field-operation-inputs/available", query_string={
            "farmId": self.farm["id"], "fieldOperationId": field_operation["id"],
        })
        self.assertEqual(available.status_code, 200)
        available_documents = available.get_json()["data"]["items"]
        self.assertEqual({item["documentNo"] for item in available_documents}, {"CROP-ISSUE-001", "CROP-ISSUE-002"})
        for item in available_documents:
            payload = {
                "farmId": self.farm["id"],
                "fieldOperationId": field_operation["id"],
                "stockDocumentId": item["stockDocumentId"],
            }
            denied = self.post(self.viewer, "/field-operation-inputs", payload)
            self.assertEqual(denied.status_code, 403)
            bound = self.post(self.operator, "/field-operation-inputs", payload)
            self.assertEqual(bound.status_code, 201)
            repeated_bound = self.post(self.operator, "/field-operation-inputs", payload)
            self.assertEqual(repeated_bound.status_code, 200)
        inputs = self.viewer.get("/api/v1/field-operation-inputs", query_string={
            "farmId": self.farm["id"], "fieldOperationId": field_operation["id"],
        })
        self.assertEqual(inputs.status_code, 200)
        input_data = inputs.get_json()["data"]
        self.assertEqual(input_data["total"], 2)
        self.assertEqual({item["quantity"] for item in input_data["items"]}, {"1", "2"})
        self.assertEqual({item["amount"] for item in input_data["items"]}, {"12.35", "24.69"})
        cost_summary = self.viewer.get(f"/api/v1/crop-cycles/{cycle['id']}/cost-summary")
        self.assertEqual(cost_summary.status_code, 200)
        costs = cost_summary.get_json()["data"]
        self.assertEqual(costs["materialCost"], "37.04")
        self.assertEqual(costs["laborCost"], "100.00")
        self.assertEqual(costs["serviceCost"], "20.00")
        self.assertEqual(costs["totalCost"], "157.04")
        self.assertEqual(costs["costPerMu"], "3.93")
        second_operation = self.post(self.manager, "/field-operations", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "operationType": "IRRIGATION",
            "operationDate": "2026-08-15", "areaMu": "40",
        }).get_json()["data"]["operation"]
        duplicate_binding = self.post(self.operator, "/field-operation-inputs", {
            "farmId": self.farm["id"],
            "fieldOperationId": second_operation["id"],
            "stockDocumentId": available_documents[0]["stockDocumentId"],
        })
        self.assertEqual(duplicate_binding.status_code, 409)
        self.assertEqual(duplicate_binding.get_json()["code"], "FIELD_INPUT_DOCUMENT_BOUND")

        other_farm = self.create_farm("PURCHASE-CROP-02", "其他种植农场")
        other_plot = self.post(self.admin, "/plots", {
            "farmId": other_farm["id"], "code": "OTHER-CROP-01", "name": "其他农场地块", "areaMu": "20",
        }).get_json()["data"]["plot"]
        other_cycle_payload = dict(cycle_payload, farmId=other_farm["id"], cycleCode="OTHER-CROP-001", plotId=other_plot["id"], areaMu="10")
        other_cycle_response = self.post(self.admin, "/crop-cycles", other_cycle_payload)
        self.assertEqual(other_cycle_response.status_code, 201, other_cycle_response.get_json())
        other_cycle = other_cycle_response.get_json()["data"]["cycle"]
        cross = dict(created, documentNo="CROP-CROSS", costObjectId=other_cycle["id"])
        response = self.post(self.operator, "/production-stock-operations", cross)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "COST_OBJECT_FARM_MISMATCH")

        harvesting = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {"status": "HARVESTING"})
        self.assertEqual(harvesting.status_code, 200)
        kg_unit = next(item for item in catalogs["units"] if item["code"] == "KG")
        harvest = self.post(self.manager, "/harvest-batches", {
            "farmId": self.farm["id"], "cropCycleId": cycle["id"], "harvestNo": "CROP-STOCK-HARVEST",
            "harvestDate": "2026-08-31", "grossWeight": "1", "netWeight": "1",
            "unitId": kg_unit["id"], "warehouseId": self.warehouse["id"],
        })
        self.assertEqual(harvest.status_code, 201)
        closed = self.patch(self.admin, f"/crop-cycles/{cycle['id']}/status", {
            "status": "CLOSED", "actualStartDate": "2026-08-01", "actualEndDate": "2026-08-31",
        })
        self.assertEqual(closed.status_code, 200)
        response = self.post(self.operator, "/production-stock-operations", dict(created, documentNo="CROP-CLOSED"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "CROP_CYCLE_CLOSED")

    def test_feed_issue_can_be_traced_to_livestock_batch(self):
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        pig_species_id = next(item["id"] for item in catalogs["livestockSpecies"] if item["code"] == "PIG")
        entry_date = date.today() - timedelta(days=3)
        batch_response = self.post(self.manager, "/livestock-batches", {
            "farmId": self.farm["id"],
            "speciesId": pig_species_id,
            "batchNo": "PIG-FEED-001",
            "name": "饲喂成本测试批次",
            "entryNo": "PIG-ENTRY-001",
            "entryDate": entry_date.isoformat(),
            "barnId": self.barn["id"],
            "initialCount": 20,
        })
        self.assertEqual(batch_response.status_code, 201)
        batch = batch_response.get_json()["data"]["batch"]

        purchase = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-BATCH-FEED", quantity="10"),
        ).get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})
        issue = self.production_operation_input("FEED-BATCH-001", cost_object_type="livestock_batch")
        issue["operationDate"] = date.today().isoformat()
        issue["costObjectId"] = batch["id"]
        created = self.post(self.operator, "/production-stock-operations", issue)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["data"]["operation"]["costObjectType"], "livestock_batch")

        veterinary_category = self.create_category(self.farm["id"], "VETERINARY")
        veterinary_item = self.create_item(
            self.farm["id"],
            veterinary_category["id"],
            self.item["unitId"],
            "PIG-MEDICINE",
            False,
            "veterinary_drug",
            "批次防疫药品",
        )
        medicine_purchase_input = self.purchase_input(
            "PO-BATCH-MEDICINE", quantity="2", unit_price="5", lot_no="LOT-MEDICINE"
        )
        medicine_purchase_input["lines"][0]["itemId"] = veterinary_item["id"]
        medicine_purchase = self.post(
            self.operator,
            "/purchases",
            medicine_purchase_input,
        ).get_json()["data"]["purchase"]
        self.post(
            self.operator,
            f"/purchases/{medicine_purchase['id']}/post",
            {"version": medicine_purchase["version"]},
        )
        medicine_issue = self.production_operation_input(
            "MEDICINE-BATCH-001", quantity="1", lot_no="LOT-MEDICINE", cost_object_type="livestock_batch"
        )
        medicine_issue["operationDate"] = date.today().isoformat()
        medicine_issue["costObjectId"] = batch["id"]
        medicine_issue["itemId"] = veterinary_item["id"]
        self.assertEqual(
            self.post(self.operator, "/production-stock-operations", medicine_issue).status_code,
            201,
        )

        for record_no, occurred_on, average_weight in (
            ("WEIGHT-FEED-001", entry_date, "20.000"),
            ("WEIGHT-FEED-002", date.today(), "22.000"),
        ):
            response = self.post(self.operator, "/livestock-weight-records", {
                "farmId": self.farm["id"],
                "batchId": batch["id"],
                "recordNo": record_no,
                "occurredOn": occurred_on.isoformat(),
                "sampleCount": 10,
                "averageWeight": average_weight,
            })
            self.assertEqual(response.status_code, 201)

        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}")
        self.assertEqual(detail.status_code, 200)
        data = detail.get_json()["data"]["batch"]
        self.assertEqual(data["feedingRecords"][0]["documentNo"], "FEED-BATCH-001")
        self.assertEqual(
            {record["documentNo"] for record in data["materialRecords"]},
            {"FEED-BATCH-001", "MEDICINE-BATCH-001"},
        )
        self.assertEqual(data["productionSummary"]["totalFeedCost"], "74.07")
        self.assertEqual(data["productionSummary"]["totalDirectCost"], "79.07")
        self.assertEqual(data["productionSummary"]["costPerHead"], "3.95")
        self.assertEqual(data["productionSummary"]["costPerHeadBasis"], "CURRENT_ESTIMATE")
        self.assertEqual(
            {item["category"]: item["amount"] for item in data["productionSummary"]["costBreakdown"]},
            {"feed": "74.07", "veterinary_drug": "5.00"},
        )
        self.assertEqual(data["productionSummary"]["totalFeedWeightKg"], "6.000")
        self.assertEqual(data["productionSummary"]["estimatedWeightGainKg"], "40.000")
        self.assertEqual(data["productionSummary"]["fcr"], "0.150")
        self.assertTrue(data["productionSummary"]["fcrEstimated"])
        self.assertEqual(data["productionTrend"][0]["headCount"], 20)
        self.assertEqual(data["productionTrend"][0]["averageWeight"], "20")
        self.assertEqual(data["productionTrend"][-1]["averageWeight"], "22")
        self.assertEqual(data["productionTrend"][-1]["cumulativeDirectCost"], "79.07")
        analysis = self.viewer.get(
            "/api/v1/livestock-analysis",
            query_string={"farmId": self.farm["id"]},
        ).get_json()["data"]
        comparison = next(item for item in analysis["batchComparisons"] if item["batchId"] == batch["id"])
        self.assertEqual(comparison["directCost"], "79.07")
        self.assertEqual(comparison["costPerHead"], "3.95")
        self.assertEqual(comparison["adg"], "0.667")
        self.assertEqual(comparison["fcr"], "0.150")
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_complete_livestock_batch_reconciles_stock_head_count_costs_and_sources(self):
        catalogs = self.admin.get("/api/v1/catalogs").get_json()["data"]
        pig_species_id = next(item["id"] for item in catalogs["livestockSpecies"] if item["code"] == "PIG")
        unit_id = next(item["id"] for item in catalogs["units"] if item["code"] == "KG")
        second_barn = self.create_barn(self.farm["id"], "PIG-BARN-2", "育肥二舍")
        entry_date = date.today() - timedelta(days=14)

        feed_purchase_input = self.purchase_input(
            "SIM-PO-FEED",
            quantity="1000",
            unit_price="2.5",
            lot_no="SIM-FEED-LOT",
        )
        feed_purchase_input["orderDate"] = (entry_date - timedelta(days=1)).isoformat()
        feed_purchase = self.post(self.operator, "/purchases", feed_purchase_input).get_json()["data"]["purchase"]
        self.assertEqual(
            self.post(
                self.operator,
                f"/purchases/{feed_purchase['id']}/post",
                {"version": feed_purchase["version"]},
            ).status_code,
            200,
        )

        medicine_category = self.create_category(self.farm["id"], "SIM-VETERINARY")
        medicine_item = self.create_item(
            self.farm["id"],
            medicine_category["id"],
            unit_id,
            "SIM-MEDICINE",
            False,
            "veterinary_drug",
            "模拟防疫药品",
        )
        medicine_purchase_input = self.purchase_input(
            "SIM-PO-MEDICINE",
            quantity="10",
            unit_price="40",
            lot_no=None,
            expires_on=None,
        )
        medicine_purchase_input["orderDate"] = (entry_date - timedelta(days=1)).isoformat()
        medicine_purchase_input["lines"][0]["itemId"] = medicine_item["id"]
        medicine_purchase = self.post(
            self.operator,
            "/purchases",
            medicine_purchase_input,
        ).get_json()["data"]["purchase"]
        self.assertEqual(
            self.post(
                self.operator,
                f"/purchases/{medicine_purchase['id']}/post",
                {"version": medicine_purchase["version"]},
            ).status_code,
            200,
        )

        batch_response = self.post(self.manager, "/livestock-batches", {
            "farmId": self.farm["id"],
            "speciesId": pig_species_id,
            "batchNo": "SIM-PIG-001",
            "name": "完整闭环模拟批次",
            "entryNo": "SIM-ENTRY-001",
            "entryDate": entry_date.isoformat(),
            "barnId": self.barn["id"],
            "initialCount": 100,
            "source": "模拟仔猪供应户",
        })
        self.assertEqual(batch_response.status_code, 201)
        batch = batch_response.get_json()["data"]["batch"]

        def production(document_no, operation_type, operation_date, quantity, item_id, lot_no):
            payload = self.production_operation_input(
                document_no,
                operation_type=operation_type,
                quantity=quantity,
                lot_no=lot_no,
                cost_object_type="livestock_batch",
            )
            payload.update({
                "operationDate": operation_date.isoformat(),
                "costObjectId": batch["id"],
                "itemId": item_id,
            })
            response = self.post(self.operator, "/production-stock-operations", payload)
            self.assertEqual(response.status_code, 201)

        production("SIM-FEED-ISSUE-1", "issue", entry_date + timedelta(days=1), "200", self.item["id"], "SIM-FEED-LOT")
        production("SIM-MEDICINE-ISSUE", "issue", entry_date + timedelta(days=2), "2", medicine_item["id"], None)

        self.assertEqual(self.post(self.operator, "/livestock-health-records", {
            "farmId": self.farm["id"],
            "batchId": batch["id"],
            "recordNo": "SIM-HEALTH-001",
            "recordType": "VACCINATION",
            "occurredOn": (entry_date + timedelta(days=2)).isoformat(),
            "description": "完成入栏防疫",
            "medicineName": "模拟防疫药品",
            "dosage": "每头按方案使用",
        }).status_code, 201)

        for index, (offset, weight) in enumerate(((0, "20"), (7, "24.9"), (12, "28.4")), start=1):
            self.assertEqual(self.post(self.operator, "/livestock-weight-records", {
                "farmId": self.farm["id"],
                "batchId": batch["id"],
                "recordNo": f"SIM-WEIGHT-{index}",
                "occurredOn": (entry_date + timedelta(days=offset)).isoformat(),
                "sampleCount": 20,
                "averageWeight": weight,
            }).status_code, 201)

        def movement(movement_no, movement_type, occurred_on, from_barn_id, quantity, **extra):
            response = self.post(self.operator, "/livestock-movements", {
                "farmId": self.farm["id"],
                "batchId": batch["id"],
                "movementNo": movement_no,
                "movementType": movement_type,
                "occurredOn": occurred_on.isoformat(),
                "fromBarnId": from_barn_id,
                "quantity": quantity,
                **extra,
            })
            self.assertEqual(response.status_code, 201)
            return response.get_json()["data"]["batch"]

        movement(
            "SIM-TRANSFER-001",
            "TRANSFER",
            entry_date + timedelta(days=8),
            self.barn["id"],
            40,
            toBarnId=second_barn["id"],
        )
        movement(
            "SIM-DEATH-001",
            "DEATH",
            entry_date + timedelta(days=9),
            second_barn["id"],
            2,
            reason="应激反应",
        )
        production("SIM-FEED-ISSUE-2", "issue", entry_date + timedelta(days=10), "100", self.item["id"], "SIM-FEED-LOT")
        production("SIM-FEED-RETURN", "return", entry_date + timedelta(days=11), "20", self.item["id"], "SIM-FEED-LOT")
        movement("SIM-EXIT-001", "EXIT", entry_date + timedelta(days=13), self.barn["id"], 60)
        closed = movement("SIM-EXIT-002", "EXIT", date.today(), second_barn["id"], 38)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["currentHeadCount"], 0)

        cost_entries = []
        for entry_no, offset, cost_type, amount, description in (
            ("SIM-COST-ENTRY", 0, "ENTRY", "20000", "仔猪入栏采购成本"),
            ("SIM-COST-LABOR", 7, "LABOR", "1200", "本批次饲养人工"),
            ("SIM-COST-OVERHEAD", 12, "OVERHEAD", "300", "水电公共费用分摊"),
            ("SIM-COST-OTHER", 13, "OTHER", "100", "待撤销模拟费用"),
        ):
            response = self.post(self.manager, "/livestock-cost-entries", {
                "farmId": self.farm["id"],
                "batchId": batch["id"],
                "entryNo": entry_no,
                "businessDate": (entry_date + timedelta(days=offset)).isoformat(),
                "costType": cost_type,
                "amount": amount,
                "description": description,
            })
            self.assertEqual(response.status_code, 201)
            cost_entries.append(response.get_json()["data"]["costEntry"])
        self.assertEqual(
            self.post(
                self.manager,
                f"/livestock-cost-entries/{cost_entries[-1]['id']}/cancel",
            ).status_code,
            200,
        )

        detail = self.viewer.get(f"/api/v1/livestock-batches/{batch['id']}").get_json()["data"]["batch"]
        self.assertEqual(detail["initialCount"], 100)
        self.assertEqual(detail["deathCount"], 2)
        self.assertEqual(detail["exitCount"], 98)
        self.assertEqual(detail["movementCount"], 5)
        self.assertEqual(len(detail["healthRecords"]), 1)
        self.assertEqual(len(detail["weightRecords"]), 3)
        self.assertEqual(
            {record["documentNo"] for record in detail["materialRecords"]},
            {"SIM-FEED-ISSUE-1", "SIM-FEED-ISSUE-2", "SIM-FEED-RETURN", "SIM-MEDICINE-ISSUE"},
        )
        self.assertEqual(detail["productionSummary"]["totalFeedWeightKg"], "280.000")
        self.assertEqual(detail["productionSummary"]["totalDirectCost"], "780.00")
        self.assertEqual(detail["productionSummary"]["costPerHead"], "7.96")
        self.assertEqual(detail["productionSummary"]["costPerHeadBasis"], "EXITED")
        self.assertEqual(detail["productionSummary"]["totalAdditionalCost"], "21500.00")
        self.assertEqual(detail["productionSummary"]["totalProductionCost"], "22280.00")
        self.assertEqual(detail["productionSummary"]["productionCostPerHead"], "227.35")
        self.assertEqual(
            {item["costType"]: item["amount"] for item in detail["productionSummary"]["additionalCostBreakdown"]},
            {"ENTRY": "20000.00", "LABOR": "1200.00", "OVERHEAD": "300.00"},
        )
        self.assertEqual(len(detail["costEntries"]), 4)
        self.assertEqual(sum(item["status"] == "CANCELLED" for item in detail["costEntries"]), 1)
        self.assertEqual(detail["productionSummary"]["adg"], "0.700")
        self.assertEqual(detail["productionSummary"]["fcr"], "0.340")
        self.assertTrue(detail["productionSummary"]["fcrEstimated"])
        self.assertEqual(detail["productionTrend"][-1]["headCount"], 0)
        self.assertEqual(detail["productionTrend"][-1]["cumulativeDirectCost"], "780.00")

        stocks = self.viewer.get(
            "/api/v1/stocks",
            query_string={"farmId": self.farm["id"], "pageSize": 100},
        ).get_json()["data"]
        stock_by_code = {item["itemCode"]: item for item in stocks["items"]}
        self.assertEqual(stock_by_code["PIG-FEED"]["quantity"], "720")
        self.assertEqual(stock_by_code["SIM-MEDICINE"]["quantity"], "8")
        self.assertEqual(stocks["summary"]["totalValue"], "2120.00")

        analysis = self.viewer.get(
            "/api/v1/livestock-analysis",
            query_string={"farmId": self.farm["id"], "trendDays": 30},
        ).get_json()["data"]
        self.assertEqual(analysis["summary"]["currentHeadCount"], 0)
        self.assertEqual(analysis["summary"]["activeBatchCount"], 0)
        self.assertEqual(analysis["summary"]["mortalityRate"], "2.00")
        comparison = next(item for item in analysis["batchComparisons"] if item["batchId"] == batch["id"])
        self.assertEqual(comparison["directCost"], "780.00")
        self.assertEqual(comparison["costPerHead"], "7.96")
        self.assertEqual(comparison["productionCost"], "22280.00")
        self.assertEqual(comparison["productionCostPerHead"], "227.35")
        self.assertEqual(comparison["fcr"], "0.340")

        rejected = self.production_operation_input(
            "SIM-AFTER-CLOSE",
            quantity="1",
            lot_no="SIM-FEED-LOT",
            cost_object_type="livestock_batch",
        )
        rejected.update({
            "operationDate": date.today().isoformat(),
            "costObjectId": batch["id"],
        })
        self.assertEqual(
            self.post(self.operator, "/production-stock-operations", rejected).status_code,
            409,
        )
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_purchase_returns_use_simulated_costs_and_allow_partial_returns(self):
        first = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-RETURN-A", quantity="10", unit_price="12.345", lot_no="LOT-RET-A"),
        ).get_json()["data"]["purchase"]
        first = self.post(
            self.operator,
            f"/purchases/{first['id']}/post",
            {"version": first["version"]},
        ).get_json()["data"]["purchase"]
        second = self.post(
            self.operator,
            "/purchases",
            self.purchase_input("PO-RETURN-B", quantity="10", unit_price="20", lot_no="LOT-RET-B"),
        ).get_json()["data"]["purchase"]
        second = self.post(
            self.operator,
            f"/purchases/{second['id']}/post",
            {"version": second["version"]},
        ).get_json()["data"]["purchase"]

        denied = self.post(
            self.viewer,
            "/purchase-returns",
            self.purchase_return_input("RET-DENIED", first),
        )
        self.assertEqual(denied.status_code, 403)
        future = self.post(
            self.operator,
            "/purchase-returns",
            self.purchase_return_input("RET-FUTURE", first, return_date="2099-01-01"),
        )
        self.assertEqual(future.status_code, 400)
        self.assertEqual(future.get_json()["code"], "PURCHASE_RETURN_DATE_IN_FUTURE")
        wrong_line = self.post(
            self.operator,
            "/purchase-returns",
            self.purchase_return_input(
                "RET-WRONG-LINE",
                first,
                purchase_line_id=second["lines"][0]["id"],
            ),
        )
        self.assertEqual(wrong_line.status_code, 404)
        self.assertEqual(wrong_line.get_json()["code"], "PURCHASE_LINE_NOT_FOUND")

        returned = self.post(
            self.manager,
            "/purchase-returns",
            self.purchase_return_input("RET-PART-1", first),
        )
        self.assertEqual(returned.status_code, 201)
        purchase_return = returned.get_json()["data"]["purchaseReturn"]
        self.assertEqual(purchase_return["documentType"], "PURCHASE_RETURN")
        self.assertEqual(purchase_return["quantity"], "2")
        self.assertEqual(purchase_return["refundUnitPrice"], "12.345")
        self.assertEqual(purchase_return["refundAmount"], "24.69")
        self.assertEqual(purchase_return["inventoryUnitCost"], "16.1725")
        self.assertEqual(purchase_return["inventoryAmount"], "32.35")

        repeated = self.post(
            self.manager,
            "/purchase-returns",
            self.purchase_return_input("RET-PART-1", first),
        )
        self.assertEqual(repeated.status_code, 200)
        changed_duplicate = self.post(
            self.manager,
            "/purchase-returns",
            self.purchase_return_input("RET-PART-1", first, quantity="1"),
        )
        self.assertEqual(changed_duplicate.status_code, 409)
        self.assertEqual(changed_duplicate.get_json()["code"], "PURCHASE_RETURN_NO_EXISTS")

        detail = self.operator.get(f"/api/v1/purchases/{first['id']}").get_json()["data"]["purchase"]
        self.assertEqual(detail["lines"][0]["returnedQuantity"], "2")
        self.assertEqual(detail["lines"][0]["returnableQuantity"], "8")
        excessive = self.post(
            self.operator,
            "/purchase-returns",
            self.purchase_return_input("RET-TOO-MUCH", first, quantity="9"),
        )
        self.assertEqual(excessive.status_code, 409)
        self.assertEqual(excessive.get_json()["code"], "PURCHASE_RETURN_EXCEEDS_RECEIPT")
        self.assertEqual(excessive.get_json()["details"]["available"], "8")

        moved = self.post(
            self.operator,
            "/stock-transfers",
            self.transfer_input("TR-RETURN-LOT", quantity="8", lot_no="LOT-RET-A"),
        )
        self.assertEqual(moved.status_code, 201)
        missing_lot = self.post(
            self.operator,
            "/purchase-returns",
            self.purchase_return_input("RET-NO-LOT-STOCK", first, quantity="1"),
        )
        self.assertEqual(missing_lot.status_code, 409)
        self.assertEqual(missing_lot.get_json()["code"], "LOT_STOCK_INSUFFICIENT")

        second_return = self.post(
            self.operator,
            "/purchase-returns",
            self.purchase_return_input(
                "RET-PART-2",
                first,
                quantity="3",
                warehouse_id=self.secondary_warehouse["id"],
            ),
        )
        self.assertEqual(second_return.status_code, 201)
        self.assertEqual(second_return.get_json()["data"]["purchaseReturn"]["refundAmount"], "37.04")
        detail = self.viewer.get(f"/api/v1/purchases/{first['id']}").get_json()["data"]["purchase"]
        self.assertEqual(detail["lines"][0]["returnedQuantity"], "5")
        self.assertEqual(detail["lines"][0]["returnableQuantity"], "5")

        stocks = self.viewer.get(
            "/api/v1/stocks",
            query_string={"farmId": self.farm["id"], "pageSize": 100},
        ).get_json()["data"]["items"]
        quantities = {stock["warehouseId"]: stock["quantity"] for stock in stocks}
        self.assertEqual(quantities[self.warehouse["id"]], "10")
        self.assertEqual(quantities[self.secondary_warehouse["id"]], "5")
        ledger = self.viewer.get(
            "/api/v1/stock-ledger",
            query_string={"farmId": self.farm["id"], "keyword": "RET-PART"},
        ).get_json()["data"]
        self.assertEqual(ledger["pagination"]["total"], 2)
        self.assertEqual({entry["quantityDelta"] for entry in ledger["items"]}, {"-2", "-3"})
        self.assertTrue(all(entry["documentType"] == "PURCHASE_RETURN" for entry in ledger["items"]))
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_inventory_count_posts_batch_surplus_and_shortage_and_rejects_stale_snapshots(self):
        for order_no, quantity, unit_price, lot_no in (
            ("PO-COUNT-A", "10", "12.345", "LOT-COUNT-A"),
            ("PO-COUNT-B", "5", "20", "LOT-COUNT-B"),
        ):
            purchase = self.post(
                self.operator,
                "/purchases",
                self.purchase_input(order_no, quantity=quantity, unit_price=unit_price, lot_no=lot_no),
            ).get_json()["data"]["purchase"]
            self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})

        denied = self.post(self.viewer, "/inventory-counts", self.inventory_count_input("IC-DENIED"))
        self.assertEqual(denied.status_code, 403)
        future = self.post(
            self.operator,
            "/inventory-counts",
            self.inventory_count_input("IC-FUTURE", count_date="2099-01-01"),
        )
        self.assertEqual(future.status_code, 400)
        self.assertEqual(future.get_json()["code"], "INVENTORY_COUNT_DATE_IN_FUTURE")
        empty = self.post(
            self.operator,
            "/inventory-counts",
            self.inventory_count_input("IC-EMPTY", warehouse_id=self.secondary_warehouse["id"]),
        )
        self.assertEqual(empty.status_code, 409)
        self.assertEqual(empty.get_json()["code"], "INVENTORY_COUNT_NO_STOCK")

        created = self.post(
            self.operator,
            "/inventory-counts",
            self.inventory_count_input("IC-001"),
        )
        self.assertEqual(created.status_code, 201)
        inventory_count = created.get_json()["data"]["inventoryCount"]
        self.assertEqual(inventory_count["status"], "DRAFT")
        self.assertEqual(inventory_count["lineCount"], 2)
        self.assertEqual(inventory_count["differenceLineCount"], 0)
        by_lot = {line["lotNo"]: line for line in inventory_count["lines"]}
        self.assertEqual(by_lot["LOT-COUNT-A"]["bookQuantity"], "10")
        self.assertEqual(by_lot["LOT-COUNT-B"]["bookQuantity"], "5")

        update_lines = []
        for line in inventory_count["lines"]:
            actual, reason = (
                ("8", "破包损耗") if line["lotNo"] == "LOT-COUNT-A" else ("6", "清点多出")
            )
            update_lines.append({"id": line["id"], "actualQuantity": actual, "reason": reason})
        updated = self.patch(self.manager, f"/inventory-counts/{inventory_count['id']}", {
            "version": inventory_count["version"],
            "notes": "负责人复核完成",
            "lines": update_lines,
        })
        self.assertEqual(updated.status_code, 200)
        inventory_count = updated.get_json()["data"]["inventoryCount"]
        self.assertEqual(inventory_count["version"], 2)
        self.assertEqual(inventory_count["differenceLineCount"], 2)
        differences = {line["lotNo"]: line["differenceQuantity"] for line in inventory_count["lines"]}
        self.assertEqual(differences, {"LOT-COUNT-A": "-2", "LOT-COUNT-B": "1"})
        stale_update = self.patch(self.operator, f"/inventory-counts/{inventory_count['id']}", {
            "version": 1,
            "notes": None,
            "lines": update_lines,
        })
        self.assertEqual(stale_update.status_code, 409)
        self.assertEqual(stale_update.get_json()["code"], "INVENTORY_COUNT_VERSION_CONFLICT")

        denied_post = self.post(
            self.viewer,
            f"/inventory-counts/{inventory_count['id']}/post",
            {"version": inventory_count["version"]},
        )
        self.assertEqual(denied_post.status_code, 403)
        posted = self.post(
            self.operator,
            f"/inventory-counts/{inventory_count['id']}/post",
            {"version": inventory_count["version"]},
        )
        self.assertEqual(posted.status_code, 200)
        posted_count = posted.get_json()["data"]["inventoryCount"]
        self.assertEqual(posted_count["status"], "POSTED")
        self.assertEqual(posted_count["adjustmentDocumentNo"], "IC-001")
        repeated = self.post(
            self.operator,
            f"/inventory-counts/{inventory_count['id']}/post",
            {"version": inventory_count["version"]},
        )
        self.assertEqual(repeated.status_code, 200)

        stocks = self.viewer.get(
            "/api/v1/stocks",
            query_string={"farmId": self.farm["id"], "warehouseId": self.warehouse["id"]},
        ).get_json()["data"]
        self.assertEqual(stocks["items"][0]["quantity"], "14")
        self.assertEqual(stocks["items"][0]["averageCost"], "14.8967")
        self.assertEqual(stocks["items"][0]["inventoryValue"], "208.55")
        ledger = self.viewer.get(
            "/api/v1/stock-ledger",
            query_string={"farmId": self.farm["id"], "keyword": "IC-001"},
        ).get_json()["data"]
        self.assertEqual(ledger["pagination"]["total"], 2)
        self.assertEqual({entry["quantityDelta"] for entry in ledger["items"]}, {"-2", "1"})
        self.assertTrue(all(entry["documentType"] == "INVENTORY_ADJUSTMENT" for entry in ledger["items"]))
        self.assertTrue(all(entry["unitCost"] == "14.8967" for entry in ledger["items"]))
        listed = self.viewer.get(
            "/api/v1/inventory-counts",
            query_string={"farmId": self.farm["id"], "keyword": "IC-001"},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["items"][0]["status"], "POSTED")

        stale = self.post(
            self.operator,
            "/inventory-counts",
            self.inventory_count_input("IC-STALE"),
        ).get_json()["data"]["inventoryCount"]
        moved = self.post(
            self.operator,
            "/stock-transfers",
            self.transfer_input("TR-AFTER-COUNT", quantity="1", lot_no="LOT-COUNT-A"),
        )
        self.assertEqual(moved.status_code, 201)
        stale_post = self.post(
            self.operator,
            f"/inventory-counts/{stale['id']}/post",
            {"version": stale["version"]},
        )
        self.assertEqual(stale_post.status_code, 409)
        self.assertEqual(stale_post.get_json()["code"], "INVENTORY_COUNT_STALE")
        cancelled = self.post(
            self.manager,
            f"/inventory-counts/{stale['id']}/cancel",
            {"version": stale["version"]},
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["data"]["inventoryCount"]["status"], "CANCELLED")
        cancelled_post = self.post(
            self.operator,
            f"/inventory-counts/{stale['id']}/post",
            {"version": stale["version"] + 1},
        )
        self.assertEqual(cancelled_post.status_code, 409)
        self.assertEqual(cancelled_post.get_json()["code"], "INVENTORY_COUNT_CANCELLED")

        missing_reason = self.post(
            self.operator,
            "/inventory-counts",
            self.inventory_count_input("IC-NO-REASON"),
        ).get_json()["data"]["inventoryCount"]
        missing_reason_lines = [
            {
                "id": line["id"],
                "actualQuantity": str(float(line["actualQuantity"]) - 1) if index == 0 else line["actualQuantity"],
                "reason": None,
            }
            for index, line in enumerate(missing_reason["lines"])
        ]
        rejected = self.patch(self.operator, f"/inventory-counts/{missing_reason['id']}", {
            "version": missing_reason["version"],
            "notes": None,
            "lines": missing_reason_lines,
        })
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["code"], "INVENTORY_COUNT_REASON_REQUIRED")
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_inventory_analysis_reports_expiry_trends_consumption_and_access_boundaries(self):
        today = date.today()
        today_text = today.isoformat()
        expiring_on = (today + timedelta(days=15)).isoformat()
        expired_on = (today - timedelta(days=1)).isoformat()

        expiring_payload = self.purchase_input(
            "PO-ANALYSIS",
            quantity="10",
            unit_price="12.5",
            lot_no="LOT-EXPIRING",
            expires_on=expiring_on,
        )
        expiring_payload["orderDate"] = today_text
        created = self.post(self.operator, "/purchases", expiring_payload)
        purchase = created.get_json()["data"]["purchase"]
        self.post(self.operator, f"/purchases/{purchase['id']}/post", {"version": 1})

        expired_payload = self.purchase_input(
            "PO-EXPIRED",
            quantity="2",
            unit_price="5",
            lot_no="LOT-EXPIRED",
            expires_on=expired_on,
        )
        expired_payload["orderDate"] = (today - timedelta(days=10)).isoformat()
        created = self.post(self.manager, "/purchases", expired_payload)
        expired_purchase = created.get_json()["data"]["purchase"]
        self.post(self.manager, f"/purchases/{expired_purchase['id']}/post", {"version": 1})

        transfer = self.transfer_input("TR-ANALYSIS", quantity="4", lot_no="LOT-EXPIRING")
        transfer["transferDate"] = today_text
        self.post(self.operator, "/stock-transfers", transfer)
        issue = self.production_operation_input("PI-ANALYSIS", quantity="3", lot_no="LOT-EXPIRING")
        issue["operationDate"] = today_text
        self.post(self.operator, "/production-stock-operations", issue)
        returned = self.production_operation_input(
            "PR-ANALYSIS",
            operation_type="return",
            quantity="1",
            lot_no="LOT-EXPIRING",
        )
        returned["operationDate"] = today_text
        self.post(self.operator, "/production-stock-operations", returned)

        response = self.viewer.get("/api/v1/inventory-analysis", query_string={
            "farmId": self.farm["id"],
            "expiryDays": 30,
            "trendDays": 30,
        })
        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["data"]
        self.assertEqual(analysis["summary"], {
            "warningLotCount": 3,
            "expiredLotCount": 1,
            "expiringLotCount": 2,
            "periodInboundAmount": "191.25",
            "periodOutboundAmount": "78.75",
        })
        self.assertEqual(len(analysis["trend"]), 30)
        self.assertEqual(analysis["trend"][-1], {
            "date": today_text,
            "inboundAmount": "191.25",
            "outboundAmount": "78.75",
        })
        self.assertEqual(analysis["topConsumedItems"][0]["netQuantity"], "2")
        self.assertEqual(analysis["topConsumedItems"][0]["netAmount"], "22.50")
        quantities = {
            (lot["warehouseName"], lot["lotNo"]): lot["quantity"]
            for lot in analysis["expiryLots"]
        }
        self.assertEqual(quantities[("生产物资主仓", "LOT-EXPIRING")], "4")
        self.assertEqual(quantities[("生产物资分仓", "LOT-EXPIRING")], "4")
        expired = next(lot for lot in analysis["expiryLots"] if lot["lotNo"] == "LOT-EXPIRED")
        self.assertEqual(expired["status"], "EXPIRED")
        self.assertEqual(expired["daysRemaining"], -1)

        warehouse_only = self.manager.get("/api/v1/inventory-analysis", query_string={
            "farmId": self.farm["id"],
            "warehouseId": self.secondary_warehouse["id"],
            "expiryDays": 30,
            "trendDays": 7,
        }).get_json()["data"]
        self.assertEqual(warehouse_only["summary"]["warningLotCount"], 1)
        self.assertEqual(warehouse_only["expiryLots"][0]["quantity"], "4")
        self.assertEqual(warehouse_only["topConsumedItems"], [])

        short_window = self.operator.get("/api/v1/inventory-analysis", query_string={
            "farmId": self.farm["id"],
            "expiryDays": 7,
            "trendDays": 7,
        }).get_json()["data"]
        self.assertEqual(short_window["summary"]["warningLotCount"], 1)
        self.assertEqual(short_window["summary"]["expiringLotCount"], 0)
        self.assertEqual(short_window["summary"]["expiredLotCount"], 1)

        invalid = self.operator.get("/api/v1/inventory-analysis", query_string={
            "farmId": self.farm["id"],
            "expiryDays": 0,
        })
        self.assertEqual(invalid.status_code, 400)
        denied = self.outsider.get("/api/v1/inventory-analysis", query_string={"farmId": self.farm["id"]})
        self.assertEqual(denied.status_code, 403)
        with self.app.app_context():
            self.assertEqual(reconcile_inventory(self.farm["id"]), [])

    def test_lot_and_cross_farm_validation(self):
        no_lot = self.purchase_input("PO-NO-LOT", lot_no=None)
        no_lot["lines"][0]["expiresOn"] = None
        rejected = self.post(self.operator, "/purchases", no_lot)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["code"], "LOT_NO_REQUIRED")

        other_farm = self.create_farm("PURCHASE-02", "其他采购农场")
        cross_farm = {**self.purchase_input("PO-CROSS"), "farmId": other_farm["id"]}
        rejected_cross_farm = self.post(self.admin, "/purchases", cross_farm)
        self.assertEqual(rejected_cross_farm.status_code, 409)
        self.assertEqual(rejected_cross_farm.get_json()["code"], "SUPPLIER_FARM_MISMATCH")


if __name__ == "__main__":
    unittest.main()
