import tempfile
import unittest
from datetime import date
from pathlib import Path

from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class TradeTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_ENGINE": "sqlite",
                "DATABASE": str(Path(self.temp.name) / "test.db"),
                "SECRET_KEY": "test",
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            ensure_admin_user("admin", "123456")
        self.post("/auth/login", {"username": "admin", "password": "123456"})
        self.farm = self.post("/farms", {"code": "TRADE-001", "name": "销售测试农场", "ownerName": "测试负责人"}).get_json()["data"]["farm"]
        self.warehouse = self.post("/warehouses", {"farmId": self.farm["id"], "code": "WH", "name": "主仓"}).get_json()[
            "data"
        ]["warehouse"]
        category = self.post(
            "/item-categories", {"farmId": self.farm["id"], "code": "FEED", "name": "物料"}
        ).get_json()["data"]["category"]
        catalogs = self.client.get("/api/v1/catalogs").get_json()["data"]
        unit = next(item for item in catalogs["units"] if item["code"] == "KG")
        self.item = self.post(
            "/items",
            {
                "farmId": self.farm["id"],
                "categoryId": category["id"],
                "unitId": unit["id"],
                "code": "SELL-ITEM",
                "name": "商品",
                "itemType": "other",
            },
        ).get_json()["data"]["item"]
        supplier = self.post("/suppliers", {"farmId": self.farm["id"], "code": "SUP", "name": "供应商"}).get_json()[
            "data"
        ]["supplier"]
        self.post(
            "/purchases",
            {
                "farmId": self.farm["id"],
                "orderNo": "PO-TRADE",
                "supplierId": supplier["id"],
                "warehouseId": self.warehouse["id"],
                "orderDate": date.today().isoformat(),
                "lines": [{"itemId": self.item["id"], "quantity": 100, "unitPrice": 2}],
            },
        )
        purchase = self.client.get("/api/v1/purchases", query_string={"farmId": self.farm["id"]}).get_json()["data"][
            "items"
        ][0]
        self.post(f"/purchases/{purchase['id']}/post", {"version": purchase["version"]})

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp.cleanup()

    def headers(self):
        return {"X-CSRF-Token": self.client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}

    def post(self, path, payload):
        return self.client.post(f"/api/v1{path}", json=payload, headers=self.headers())

    def test_customer_sales_post_payment_and_summary(self):
        customer = self.post(
            "/customers", {"farmId": self.farm["id"], "code": "CUST-01", "name": "销售客户"}
        ).get_json()["data"]["customer"]
        order = self.post(
            "/sales-orders",
            {
                "farmId": self.farm["id"],
                "orderNo": "SO-01",
                "customerId": customer["id"],
                "warehouseId": self.warehouse["id"],
                "saleDate": date.today().isoformat(),
                "lines": [{"itemId": self.item["id"], "quantity": 20, "unitPrice": 5}],
            },
        ).get_json()["data"]["order"]
        posted = self.post(f"/sales-orders/{order['id']}/post", {})
        self.assertEqual(posted.status_code, 200)
        payment = self.post(
            "/payments",
            {
                "farmId": self.farm["id"],
                "paymentNo": "PAY-01",
                "businessDate": date.today().isoformat(),
                "amount": 100,
                "method": "转账",
                "customerId": customer["id"],
                "salesOrderId": order["id"],
            },
        )
        self.assertEqual(payment.status_code, 201)
        summary = self.client.get("/api/v1/trade-summary", query_string={"farmId": self.farm["id"]}).get_json()["data"]
        self.assertEqual(
            summary, {"postedSalesAmount": "100.00", "salesCost": "40.00", "grossProfit": "60.00", "receivedAmount": "100.00", "cashNetInflow": "100.00", "receivableAmount": "0.00"}
        )
        insufficient = self.post(
            "/sales-orders",
            {
                "farmId": self.farm["id"],
                "orderNo": "SO-02",
                "customerId": customer["id"],
                "warehouseId": self.warehouse["id"],
                "saleDate": date.today().isoformat(),
                "lines": [{"itemId": self.item["id"], "quantity": 90, "unitPrice": 5}],
            },
        ).get_json()["data"]["order"]
        self.assertEqual(
            self.post(f"/sales-orders/{insufficient['id']}/post", {}).get_json()["code"], "SALES_STOCK_INSUFFICIENT"
        )


if __name__ == "__main__":
    unittest.main()
