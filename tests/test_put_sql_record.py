import json
import unittest
from unittest.mock import patch
from uuid import UUID

from src.webapp.mcp.put_sql_record import (
    SOCKETIO_MESSAGE_PAGE,
    insert_socketio_message_record,
    put_socketio_message_record,
)


class FakeMappingResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class FakeDbSession:
    def __init__(self, row=None):
        self.row = row or {"c_app_id": "app_123", "c_dify_user_id": "user_456"}
        self.execute_calls = []
        self.committed = False

    async def execute(self, sql, params):
        self.execute_calls.append((sql, params))
        if len(self.execute_calls) == 1:
            return FakeMappingResult(self.row)
        return FakeMappingResult(None)

    async def commit(self):
        self.committed = True


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class PutSqlRecordTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_insert_socketio_message_record_builds_chat_history_row(self):
        db_session = FakeDbSession()
        payload = {
            "type": "function",
            "name": "showQueueModal",
            "params": {},
        }

        message_id = await insert_socketio_message_record(
            db_session,
            session_id="sess_789",
            payload=payload,
        )

        UUID(message_id)
        self.assertEqual(len(db_session.execute_calls), 2)
        select_sql, select_params = db_session.execute_calls[0]
        insert_sql, insert_params = db_session.execute_calls[1]

        self.assertIn("FROM t_ai_chat_session", str(select_sql))
        self.assertEqual(select_params, {"session_id": "sess_789"})
        self.assertIn("INSERT INTO ai_gateway.t_chat_history", str(insert_sql))
        self.assertEqual(insert_params["messageId"], message_id)
        self.assertEqual(insert_params["user_msg"], "")
        self.assertEqual(insert_params["c_dify_user_id"], "user_456")
        self.assertEqual(insert_params["app_id"], "app_123")
        self.assertEqual(insert_params["session_id"], "sess_789")
        self.assertEqual(insert_params["page"], SOCKETIO_MESSAGE_PAGE)

        ai_msg = json.loads(insert_params["ai_msg"])
        self.assertEqual(
            ai_msg,
            {
                "success": True,
                "session_id": "sess_789",
                "event": "message",
                "payload": payload,
            },
        )

    async def test_put_socketio_message_record_commits_insert(self):
        db_session = FakeDbSession()
        session_factory = lambda: FakeSessionContext(db_session)

        with patch(
            "src.webapp.mcp.put_sql_record.get_async_session_factory",
            return_value=session_factory,
        ):
            await put_socketio_message_record(
                "sess_789",
                {"type": "function", "name": "showQueueModal", "params": {}},
            )

        self.assertTrue(db_session.committed)

    async def test_insert_socketio_message_record_rejects_unknown_session(self):
        db_session = FakeDbSession(row=None)
        db_session.row = None

        with self.assertRaisesRegex(ValueError, "Chat session binding not found"):
            await insert_socketio_message_record(
                db_session,
                session_id="sess_missing",
                payload={"type": "function", "name": "showQueueModal", "params": {}},
            )


if __name__ == "__main__":
    unittest.main()
