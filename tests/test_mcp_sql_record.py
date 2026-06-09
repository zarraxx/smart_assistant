import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.webapp.mcp.mcp_app import execute_client_function


class McpSqlRecordTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_execute_client_function_records_sql_before_socket_emit(self):
        calls = []

        async def fake_put_socketio_message_record(session_id, payload):
            calls.append(("record", session_id, payload))

        async def fake_emit_session_event(session_id, payload):
            calls.append(("emit", session_id, payload))

        request = SimpleNamespace(query_params={"session": "sess_789", "conversionId": "conv_123"})

        with (
            patch("src.webapp.mcp.mcp_app.get_http_request", return_value=request),
            patch(
                "src.webapp.mcp.mcp_app.put_socketio_message_record",
                new=fake_put_socketio_message_record,
            ),
            patch("src.webapp.mcp.mcp_app.emit_session_event", new=fake_emit_session_event),
        ):
            result = await execute_client_function("showQueueModal", params=None)

        expected_payload = {
            "type": "function",
            "name": "showQueueModal",
            "params": {},
        }
        self.assertEqual(
            calls,
            [
                ("record", "sess_789", expected_payload),
                ("emit", "sess_789", expected_payload),
            ],
        )
        self.assertEqual(result["payload"], expected_payload)


if __name__ == "__main__":
    unittest.main()
