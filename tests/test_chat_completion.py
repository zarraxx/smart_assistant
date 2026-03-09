import unittest

from fastapi.testclient import TestClient

from src.webapp.assistant_app import app
from src.webapp.routes.chat import get_dify_chat_gateway, get_session_store


class FakeStreamResponse:
    def __init__(self, *, status_code=200, chunks=None, headers=None, text=""):
        self.status_code = status_code
        self._chunks = chunks or []
        self.headers = headers or {"content-type": "text/event-stream; charset=utf-8"}
        self.text = text
        self.closed = False

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeDifyChatGateway:
    def __init__(self):
        self.blocking_payloads = []
        self.streaming_payloads = []

    def create_blocking_chat_message(self, payload):
        self.blocking_payloads.append(payload)
        return {
            "event": "message",
            "answer": "hello from dify",
            "conversation_id": "conv_123",
        }

    def open_stream_chat_message(self, payload):
        self.streaming_payloads.append(payload)
        return FakeStreamResponse(
            chunks=[
                b'data: {"event":"message","answer":"hello","conversation_id":"conv_stream_123"}\n\n',
                b'data: [DONE]\n\n',
            ]
        )


class FakeSessionStore:
    def __init__(self):
        self.sessions = {}
        self.updated_conversation_ids = []

    async def save_session(self, *, session_id, payload, expire_seconds):
        stored_payload = dict(payload)
        stored_payload["expire_seconds"] = expire_seconds
        self.sessions[session_id] = stored_payload

    async def get_session(self, *, session_id):
        session = self.sessions.get(session_id)
        return dict(session) if session else None

    async def set_conversation_id(self, *, session_id, conversation_id):
        session = self.sessions.get(session_id)
        if session is None:
            return None

        if not session.get("conversation_id"):
            session["conversation_id"] = conversation_id
            self.updated_conversation_ids.append(
                {"session_id": session_id, "conversation_id": conversation_id}
            )

        return dict(session)


class ChatCompletionApiTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_gateway = FakeDifyChatGateway()
        self.fake_store = FakeSessionStore()
        self.fake_store.sessions["sess_123"] = {
            "session_id": "sess_123",
            "user_id": "u10001",
            "expire_seconds": 1200,
        }
        app.dependency_overrides[get_dify_chat_gateway] = lambda: self.fake_gateway
        app.dependency_overrides[get_session_store] = lambda: self.fake_store
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_completion_supports_blocking_mode_and_binds_conversation_id(self):
        response = self.client.post(
            "/chat/completion",
            json={
                "session_id": "sess_123",
                "inputs": {"topic": "weather"},
                "query": "What's the weather?",
                "user": "u10001",
                "response_mode": "blocking",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "hello from dify")
        self.assertEqual(len(self.fake_gateway.blocking_payloads), 1)
        self.assertEqual(self.fake_gateway.blocking_payloads[0]["query"], "What's the weather?")
        self.assertEqual(self.fake_gateway.blocking_payloads[0]["user"], "u10001")
        self.assertEqual(self.fake_gateway.blocking_payloads[0]["inputs"], {"topic": "weather"})
        self.assertEqual(self.fake_store.sessions["sess_123"]["conversation_id"], "conv_123")

    def test_completion_reuses_stored_conversation_id(self):
        self.fake_store.sessions["sess_123"]["conversation_id"] = "conv_existing"

        response = self.client.post(
            "/chat/completion",
            json={
                "session_id": "sess_123",
                "inputs": {},
                "query": "Hello again",
                "user": "u10001",
                "response_mode": "blocking",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake_gateway.blocking_payloads[0]["conversation_id"], "conv_existing")
        self.assertEqual(self.fake_store.updated_conversation_ids, [])

    def test_completion_supports_streaming_mode_and_binds_conversation_id(self):
        response = self.client.post(
            "/chat/completion",
            json={
                "session_id": "sess_123",
                "inputs": {},
                "query": "Hello",
                "user": "u10001",
                "response_mode": "streaming",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        self.assertIn('data: {"event":"message","answer":"hello","conversation_id":"conv_stream_123"}', response.text)
        self.assertIn('data: [DONE]', response.text)
        self.assertEqual(len(self.fake_gateway.streaming_payloads), 1)
        self.assertEqual(self.fake_gateway.streaming_payloads[0]["query"], "Hello")
        self.assertEqual(self.fake_store.sessions["sess_123"]["conversation_id"], "conv_stream_123")

    def test_completion_rejects_removed_conversation_id_parameter(self):
        response = self.client.post(
            "/chat/completion",
            json={
                "session_id": "sess_123",
                "inputs": {},
                "query": "Hello",
                "user": "u10001",
                "response_mode": "streaming",
                "conversation_id": "conv_should_be_rejected",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_completion_requires_query_user_and_session_id(self):
        response = self.client.post(
            "/chat/completion",
            json={
                "inputs": {},
                "response_mode": "streaming",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_completion_returns_404_when_session_is_missing(self):
        response = self.client.post(
            "/chat/completion",
            json={
                "session_id": "sess_missing",
                "inputs": {},
                "query": "Hello",
                "user": "u10001",
                "response_mode": "streaming",
            },
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
