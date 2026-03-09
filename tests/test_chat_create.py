import os
import unittest

from fastapi.testclient import TestClient

from src.webapp.assistant_app import app
from src.webapp.config import get_settings
from src.webapp.routes.chat import get_session_store


class FakeSessionStore:
    def __init__(self):
        self.saved_sessions = []

    async def save_session(self, *, session_id, payload, expire_seconds):
        self.saved_sessions.append(
            {
                "session_id": session_id,
                "payload": payload,
                "expire_seconds": expire_seconds,
            }
        )


class ChatCreateApiTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["SESSION_DEFAULT_EXPIRE_SECONDS"] = "1200"
        get_settings.cache_clear()

        self.fake_store = FakeSessionStore()
        app.dependency_overrides[get_session_store] = lambda: self.fake_store
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    def test_create_chat_uses_default_expire_seconds(self):
        response = self.client.post(
            "/chat/create",
            json={
                "user_id": "u10001",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["code"], 0)
        self.assertEqual(body["message"], "success")
        self.assertTrue(body["data"]["session_id"].startswith("sess_"))
        self.assertEqual(body["data"]["user_id"], "u10001")
        self.assertEqual(body["data"]["expire_seconds"], 1200)
        self.assertEqual(body["data"]["client_capabilities"], [])
        self.assertIn("created_at", body["data"])
        self.assertIn("expires_at", body["data"])

        self.assertEqual(len(self.fake_store.saved_sessions), 1)
        saved_session = self.fake_store.saved_sessions[0]
        self.assertEqual(saved_session["expire_seconds"], 1200)
        self.assertEqual(saved_session["payload"]["user_id"], "u10001")
        self.assertEqual(saved_session["payload"]["client_capabilities"], [])

    def test_create_chat_persists_client_capabilities_and_custom_expire_seconds(self):
        response = self.client.post(
            "/chat/create",
            json={
                "user_id": "u10001",
                "expire_seconds": 90,
                "client_capabilities": ["web_search", "vision", "web_search"],
                "metadata": {"source": "web"},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["data"]["expire_seconds"], 90)
        self.assertEqual(body["data"]["client_capabilities"], ["web_search", "vision"])
        self.assertEqual(body["data"]["metadata"], {"source": "web"})

        saved_session = self.fake_store.saved_sessions[0]
        self.assertEqual(saved_session["expire_seconds"], 90)
        self.assertEqual(saved_session["payload"]["client_capabilities"], ["web_search", "vision"])
        self.assertEqual(saved_session["payload"]["metadata"], {"source": "web"})

    def test_create_chat_requires_user_id(self):
        response = self.client.post(
            "/chat/create",
            json={
                "client_capabilities": ["web_search"],
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
