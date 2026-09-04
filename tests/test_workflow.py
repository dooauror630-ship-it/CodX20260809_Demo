import tempfile
import unittest
from datetime import date
from pathlib import Path
from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user


class WorkflowTestCase(unittest.TestCase):
    def test_task_idempotency_completion_and_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app({"TESTING": True, "DATABASE_ENGINE": "sqlite", "DATABASE": str(Path(folder) / "test.db"), "SECRET_KEY": "test"})
            client = app.test_client()
            with app.app_context():
                ensure_admin_user("admin", "123456")
            def csrf():
                return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}
            self.assertEqual(client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}, headers=csrf()).status_code, 200)
            farm = client.post("/api/v1/farms", json={"code": "WF-01", "name": "任务农场", "ownerName": "负责人"}, headers=csrf()).get_json()["data"]["farm"]
            payload = {"farmId": farm["id"], "taskNo": "TASK-01", "title": "检查仓库", "dueDate": date.today().isoformat()}
            created = client.post("/api/v1/tasks", json=payload, headers=csrf())
            self.assertEqual(created.status_code, 201)
            duplicate = client.post("/api/v1/tasks", json=payload, headers=csrf())
            self.assertEqual(duplicate.status_code, 200)
            task_id = created.get_json()["data"]["task"]["id"]
            self.assertEqual(client.post(f"/api/v1/tasks/{task_id}/complete", json={}, headers=csrf()).status_code, 200)
            audits = client.get("/api/v1/audit-logs", query_string={"farmId": farm["id"]})
            self.assertEqual(len(audits.get_json()["data"]["items"]), 2)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
