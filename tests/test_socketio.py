import unittest
from unittest.mock import AsyncMock, patch

from src.webapp.assistant_app import app
from src.webapp.socketio_app import emit_session_event, resolve_session_id, connect, message, socket_server


class SocketIoMountTestCase(unittest.TestCase):
    def test_app_mounts_socketio_asgi_app(self):
        self.assertTrue(any(getattr(route, "path", None) == "/socket.io" for route in app.routes))


class SocketIoSessionBindingTestCase(unittest.IsolatedAsyncioTestCase):
    def test_resolve_session_id_prefers_auth_payload(self):
        session_id = resolve_session_id(
            auth={"sessionId": "sess_123"},
            environ={"asgi.scope": {"query_string": b"sessionId=sess_other"}},
        )

        self.assertEqual(session_id, "sess_123")

    def test_resolve_session_id_supports_query_string(self):
        session_id = resolve_session_id(
            auth=None,
            environ={"asgi.scope": {"query_string": b"sessionId=sess_456"}},
        )

        self.assertEqual(session_id, "sess_456")

    async def test_connect_rejects_missing_session_id(self):
        self.assertFalse(await connect("socket_sid", {}, None))

    async def test_connect_joins_session_room(self):
        with patch.object(socket_server, "enter_room", new=AsyncMock()) as mock_enter_room:
            await connect("socket_sid", {}, {"sessionId": "sess_789"})

        mock_enter_room.assert_awaited_once_with("socket_sid", "sess_789")

    async def test_emit_session_event_uses_session_room(self):
        payload = {"type": "function", "name": "showQueueModal", "params": {}}

        with patch.object(socket_server, "emit", new=AsyncMock()) as mock_emit:
            await emit_session_event("sess_789", payload)

        mock_emit.assert_awaited_once_with("message", payload, to="sess_789")

    async def test_message_echoes_debug_params_back_to_sender(self):
        payload = {
            "type": "echo",
            "name": "debug",
            "params": {
                "type": "function",
                "name": "showPatientReportModal",
                "params": {},
            },
        }

        with patch.object(socket_server, "emit", new=AsyncMock()) as mock_emit:
            await message("socket_sid", payload)

        mock_emit.assert_awaited_once_with("message", payload["params"], to="socket_sid")


if __name__ == "__main__":
    unittest.main()
