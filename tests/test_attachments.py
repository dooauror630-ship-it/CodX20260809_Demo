import io
import tempfile
import unittest
from pathlib import Path
from backend.app import create_app, db
from backend.app.modules.auth.service import ensure_admin_user

class AttachmentTestCase(unittest.TestCase):
    def test_upload_list_download_and_reject_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app({"TESTING": True, "DATABASE_ENGINE": "sqlite", "DATABASE": str(Path(folder) / "test.db"), "SECRET_KEY": "test", "INSTANCE_PATH": folder})
            client = app.test_client()
            with app.app_context():
                ensure_admin_user("admin", "123456")
            def csrf():
                return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").get_json()["csrfToken"]}
            client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}, headers=csrf())
            farm = client.post("/api/v1/farms", json={"code": "AT-01", "name": "附件农场", "ownerName": "负责人"}, headers=csrf()).get_json()["data"]["farm"]
            response = client.post("/api/v1/attachments", data={"farmId": str(farm["id"]), "resourceType": "FARM", "resourceId": str(farm["id"]), "file": (io.BytesIO(b"hello"), "note.txt")}, headers=csrf(), content_type="multipart/form-data")
            self.assertEqual(response.status_code, 201)
            attachment_id = response.get_json()["data"]["attachment"]["id"]
            self.assertEqual(client.get(f"/api/v1/attachments/{attachment_id}/download").data, b"hello")
            bad = client.post("/api/v1/attachments", data={"farmId": str(farm["id"]), "file": (io.BytesIO(b"x"), "bad.exe")}, headers=csrf(), content_type="multipart/form-data")
            self.assertEqual(bad.get_json()["code"], "ATTACHMENT_TYPE_INVALID")
            with app.app_context():
                db.session.remove()
                db.engine.dispose()

if __name__ == "__main__":
    unittest.main()
