import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from backend.app import create_app, db
from backend.app.modules.auth.models import User
from backend.app.modules.auth.service import ensure_admin_user
from backend.app.modules.catalog.models import Unit
from backend.app.modules.farm.models import Farm, FarmUser
from backend.app.modules.inventory.models import Item, ItemCategory, InventoryBalance, InventoryCount, PurchaseOrder, Supplier, Warehouse
from backend.app.modules.workflow.models import AuditLog
from backend.app.modules.assistant.models import AgentConfirmationNonce
from backend.app.modules.inventory.models import StockDocument


class AssistantSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_ENGINE": "sqlite",
            "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "assistant-test-secret-key",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            admin, _created = ensure_admin_user("admin", "123456")
            self.viewer = User(
                username="viewer",
                display_name="只读用户",
                password_hash=generate_password_hash("ViewerPass123"),
                role="operator",
                is_active=True,
            )
            self.other = User(
                username="other",
                display_name="其他用户",
                password_hash=generate_password_hash("OtherPass123"),
                role="operator",
                is_active=True,
            )
            self.manager = User(
                username="manager",
                display_name="农场负责人",
                password_hash=generate_password_hash("ManagerPass123"),
                role="operator",
                is_active=True,
            )
            db.session.add_all([self.viewer, self.other, self.manager])
            db.session.flush()
            farm = Farm(
                code="ASSISTANT-001",
                name="智能体农场",
                owner_name="测试负责人",
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            other_farm = Farm(
                code="ASSISTANT-002",
                name="其他农场",
                owner_name="其他负责人",
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            db.session.add_all([farm, other_farm])
            db.session.flush()
            db.session.add(FarmUser(farm_id=farm.id, user_id=self.viewer.id, role_code="viewer"))
            db.session.add(FarmUser(farm_id=farm.id, user_id=self.manager.id, role_code="manager"))
            unit = Unit(code="AGENT-KG", name="千克", dimension="MASS", base_factor=Decimal("1"), scale=3)
            category = ItemCategory(
                farm_id=farm.id,
                code="FEED",
                name="饲料",
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            db.session.add_all([unit, category])
            db.session.flush()
            supplier = Supplier(
                farm_id=farm.id,
                code="SUP-01",
                name="测试供应商",
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            warehouse = Warehouse(
                farm_id=farm.id,
                code="WH-01",
                name="主仓库",
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            item = Item(
                farm_id=farm.id,
                category_id=category.id,
                unit_id=unit.id,
                code="ITEM-01",
                name="玉米饲料",
                item_type="FEED",
                safety_stock=Decimal("10"),
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
            db.session.add_all([supplier, warehouse, item])
            db.session.commit()
            self.farm_id = farm.id
            self.other_farm_id = other_farm.id
            self.supplier_id = supplier.id
            self.warehouse_id = warehouse.id
            self.item_id = item.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def csrf(self):
        return {"X-CSRF-Token": self.client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}

    def login(self, username="viewer", password="ViewerPass123"):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=self.csrf(),
        )
        self.assertEqual(response.status_code, 200)

    def issue_token(self, username="viewer", password="ViewerPass123"):
        self.login(username, password)
        response = self.client.post("/api/v1/assistant/session", headers=self.csrf())
        self.assertEqual(response.status_code, 200)
        return response.get_json()["data"]["token"]

    def test_context_is_scoped_to_user_and_read_only(self):
        token = self.issue_token()
        context = self.client.get("/api/v1/assistant/internal/context", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(context.status_code, 200)
        data = context.get_json()["data"]
        self.assertEqual([farm["id"] for farm in data["farms"]], [self.farm_id])
        self.assertEqual([tool["name"] for tool in data["tools"]], [
            "agri_list_farms",
            "agri_current_user",
            "agri_purchase_options",
            "agri_inventory_summary",
            "agri_livestock_summary",
            "agri_trade_summary",
            "agri_crop_summary",
            "agri_trade_profit",
            "agri_inventory_count_detail",
        ])
        self.assertFalse(data["writePolicy"]["enabled"])

    def purchase_payload(self):
        return {
            "farmId": self.farm_id,
            "orderNo": "AGENT-DRAFT-001",
            "supplierId": self.supplier_id,
            "warehouseId": self.warehouse_id,
            "orderDate": "2026-09-09",
            "notes": "智能体草稿测试",
            "lines": [{"itemId": self.item_id, "quantity": 12, "unitPrice": 3.5}],
        }

    def test_purchase_options_and_draft_are_role_scoped_and_idempotent(self):
        viewer_token = self.issue_token()
        options = self.client.get(
            f"/api/v1/assistant/internal/purchase-options?farmId={self.farm_id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(options.status_code, 200)
        self.assertEqual(options.get_json()["data"]["items"][0]["code"], "ITEM-01")

        denied = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload(),
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(denied.status_code, 403)

        admin_token = self.issue_token("admin", "123456")
        headers = {"Authorization": f"Bearer {admin_token}"}
        created = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload(),
            headers=headers,
        )
        self.assertEqual(created.status_code, 200)
        created_data = created.get_json()["data"]
        self.assertTrue(created_data["created"])
        self.assertTrue(created_data["requiresConfirmation"])
        self.assertEqual(created_data["draft"]["status"], "DRAFT")
        purchase_id = created_data["draft"]["id"]

        repeated = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload(),
            headers=headers,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertFalse(repeated.get_json()["data"]["created"])
        self.assertEqual(repeated.get_json()["data"]["draft"]["id"], purchase_id)

        with self.app.app_context():
            self.assertIsNone(db.session.scalar(
                select(InventoryBalance).where(InventoryBalance.farm_id == self.farm_id)
            ))
            self.assertEqual(db.session.scalar(
                select(PurchaseOrder).where(PurchaseOrder.id == purchase_id)
            ).status, "DRAFT")
            self.assertEqual(db.session.scalar(
                select(AuditLog).where(AuditLog.resource_id == purchase_id)
            ).action, "CREATE_DRAFT")

    def test_stock_transfer_draft_requires_confirmation_and_preserves_inventory_until_post(self):
        with self.app.app_context():
            destination = Warehouse(farm_id=self.farm_id, code="WH-02", name="周转仓", created_by_id=1, updated_by_id=1)
            balance = InventoryBalance(
                farm_id=self.farm_id, warehouse_id=self.warehouse_id, item_id=self.item_id,
                quantity=Decimal("20"), average_cost=Decimal("2.5000"),
            )
            db.session.add_all([destination, balance])
            db.session.commit()
            destination_id = destination.id
        token = self.issue_token("manager", "ManagerPass123")
        payload = {
            "farmId": self.farm_id, "documentNo": "AGENT-TRANSFER-001",
            "fromWarehouseId": self.warehouse_id, "toWarehouseId": destination_id,
            "transferDate": "2026-09-09", "itemId": self.item_id, "quantity": 6,
        }
        draft = self.client.post("/api/v1/assistant/internal/stock-transfer-draft", json=payload, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(draft.status_code, 200)
        draft_data = draft.get_json()["data"]
        self.assertEqual(draft_data["draft"]["status"], "DRAFT")
        with self.app.app_context():
            source = db.session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == self.warehouse_id, InventoryBalance.item_id == self.item_id))
            self.assertEqual(source.quantity, Decimal("20.000"))
        confirmed = self.client.post("/api/v1/assistant/internal/stock-transfer-confirm", json={"confirmationToken": draft_data["confirmationToken"]}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.get_json()["data"]["confirmed"])
        with self.app.app_context():
            source = db.session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == self.warehouse_id, InventoryBalance.item_id == self.item_id))
            destination_balance = db.session.scalar(select(InventoryBalance).where(InventoryBalance.warehouse_id == destination_id, InventoryBalance.item_id == self.item_id))
            self.assertEqual(source.quantity, Decimal("14.000"))
            self.assertEqual(destination_balance.quantity, Decimal("6.000"))

    def test_purchase_confirmation_requires_signed_challenge_and_is_idempotent(self):
        token = self.issue_token("admin", "123456")
        headers = {"Authorization": f"Bearer {token}"}
        draft = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload() | {"orderNo": "AGENT-CONFIRM-001"},
            headers=headers,
        )
        self.assertEqual(draft.status_code, 200)
        data = draft.get_json()["data"]
        confirmation_token = data["confirmationToken"]
        purchase_id = data["draft"]["id"]

        viewer_token = self.issue_token()
        owner_denied = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": confirmation_token},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(owner_denied.status_code, 403)
        self.assertEqual(owner_denied.get_json()["code"], "AGENT_CONFIRMATION_OWNER_REQUIRED")

        confirmed = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": confirmation_token},
            headers=headers,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.get_json()["data"]["confirmed"])
        self.assertEqual(confirmed.get_json()["data"]["purchase"]["status"], "POSTED")

        repeated = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": confirmation_token},
            headers=headers,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.get_json()["data"]["alreadyPosted"])

        with self.app.app_context():
            balance = db.session.scalar(
                select(InventoryBalance).where(
                    InventoryBalance.farm_id == self.farm_id,
                    InventoryBalance.item_id == self.item_id,
                )
            )
            self.assertEqual(balance.quantity, Decimal("12.000"))
            self.assertEqual(db.session.scalar(
                select(StockDocument).where(StockDocument.source_id == purchase_id)
            ).document_type, "PURCHASE_RECEIPT")
            self.assertEqual(db.session.scalar(
                select(AuditLog).where(
                    AuditLog.resource_id == purchase_id,
                    AuditLog.action == "CONFIRM_WRITE",
                )
            ).action, "CONFIRM_WRITE")
            consumed_nonce = db.session.scalar(
                select(AgentConfirmationNonce).where(
                    AgentConfirmationNonce.resource_id == purchase_id,
                    AgentConfirmationNonce.action == "purchase-post",
                )
            )
            self.assertIsNotNone(consumed_nonce)
            self.assertGreater(consumed_nonce.user_id, 0)

    def test_purchase_confirmation_rejects_plain_or_tampered_token(self):
        token = self.issue_token("admin", "123456")
        response = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": "tampered-confirmation-token-xxxxxxxx"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["code"], "AGENT_CONFIRMATION_INVALID")

    def test_inventory_count_draft_and_confirmation_are_role_scoped_and_idempotent(self):
        count_payload = {
            "farmId": self.farm_id,
            "countNo": "AGENT-COUNT-001",
            "warehouseId": self.warehouse_id,
            "countDate": "2026-09-09",
            "notes": "智能体盘点草稿测试",
        }

        viewer_token = self.issue_token()
        denied = self.client.post(
            "/api/v1/assistant/internal/inventory-count-draft",
            json=count_payload,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "FARM_WRITE_DENIED")

        # 先用既有受控采购链路准备一笔可盘点库存。
        admin_token = self.issue_token("admin", "123456")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        purchase = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload() | {"orderNo": "AGENT-COUNT-STOCK-001"},
            headers=admin_headers,
        )
        self.assertEqual(purchase.status_code, 200)
        posted = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": purchase.get_json()["data"]["confirmationToken"]},
            headers=admin_headers,
        )
        self.assertEqual(posted.status_code, 200)

        manager_token = self.issue_token("manager", "ManagerPass123")
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        created = self.client.post(
            "/api/v1/assistant/internal/inventory-count-draft",
            json=count_payload,
            headers=manager_headers,
        )
        self.assertEqual(created.status_code, 200)
        data = created.get_json()["data"]
        self.assertTrue(data["created"])
        self.assertTrue(data["requiresConfirmation"])
        self.assertEqual(data["draft"]["status"], "DRAFT")
        count_id = data["draft"]["id"]

        repeated = self.client.post(
            "/api/v1/assistant/internal/inventory-count-draft",
            json=count_payload,
            headers=manager_headers,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertFalse(repeated.get_json()["data"]["created"])
        self.assertEqual(repeated.get_json()["data"]["draft"]["id"], count_id)

        confirmed = self.client.post(
            "/api/v1/assistant/internal/inventory-count-confirm",
            json={"confirmationToken": data["confirmationToken"]},
            headers=manager_headers,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.get_json()["data"]["confirmed"])
        self.assertEqual(confirmed.get_json()["data"]["inventoryCount"]["status"], "POSTED")

        repeated_confirm = self.client.post(
            "/api/v1/assistant/internal/inventory-count-confirm",
            json={"confirmationToken": data["confirmationToken"]},
            headers=manager_headers,
        )
        self.assertEqual(repeated_confirm.status_code, 200)
        self.assertTrue(repeated_confirm.get_json()["data"]["alreadyPosted"])

        with self.app.app_context():
            self.assertEqual(db.session.get(InventoryCount, count_id).status, "POSTED")
            audit_actions = db.session.scalars(
                select(AuditLog.action).where(
                    AuditLog.resource_type == "INVENTORY_COUNT",
                    AuditLog.resource_id == count_id,
                ).order_by(AuditLog.id)
            ).all()
            self.assertEqual(audit_actions, ["CREATE_DRAFT", "POST", "CONFIRM_WRITE", "CONFIRM_REPLAY"])

    def test_farm_manager_can_confirm_own_draft(self):
        token = self.issue_token("manager", "ManagerPass123")
        headers = {"Authorization": f"Bearer {token}"}
        draft = self.client.post(
            "/api/v1/assistant/internal/purchase-draft",
            json=self.purchase_payload() | {"orderNo": "AGENT-MANAGER-001"},
            headers=headers,
        )
        self.assertEqual(draft.status_code, 200)
        self.assertTrue(draft.get_json()["data"]["confirmationToken"])
        confirmed = self.client.post(
            "/api/v1/assistant/internal/purchase-confirm",
            json={"confirmationToken": draft.get_json()["data"]["confirmationToken"]},
            headers=headers,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.get_json()["data"]["confirmed"])

    def test_internal_current_user_returns_session_identity(self):
        token = self.issue_token()
        response = self.client.get(
            "/api/v1/assistant/internal/current-user",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["user"]["username"], "viewer")

    def test_user_list_is_admin_only(self):
        viewer_token = self.issue_token()
        denied = self.client.get(
            "/api/v1/assistant/internal/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "AGENT_TOOL_FORBIDDEN")

        admin_token = self.issue_token("admin", "123456")
        allowed = self.client.get(
            "/api/v1/assistant/internal/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertGreaterEqual(allowed.get_json()["data"]["pagination"]["total"], 3)

    def test_internal_summary_cannot_cross_farm_boundary(self):
        token = self.issue_token()
        allowed = self.client.get(
            f"/api/v1/assistant/internal/inventory-summary?farmId={self.farm_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        denied = self.client.get(
            f"/api/v1/assistant/internal/inventory-summary?farmId={self.other_farm_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["code"], "FARM_ACCESS_DENIED")

    def test_internal_routes_require_signed_session(self):
        missing = self.client.get("/api/v1/assistant/internal/farms")
        invalid = self.client.get(
            "/api/v1/assistant/internal/farms",
            headers={"Authorization": "Bearer invalid"},
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)

    def test_logout_revokes_agent_session_token(self):
        token = self.issue_token()
        logout = self.client.post("/api/v1/auth/logout", headers=self.csrf())
        self.assertEqual(logout.status_code, 200)
        revoked = self.client.get(
            "/api/v1/assistant/internal/context",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(revoked.status_code, 401)
        self.assertEqual(revoked.get_json()["code"], "AGENT_SESSION_REVOKED")


if __name__ == "__main__":
    unittest.main()
