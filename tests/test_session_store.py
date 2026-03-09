import json
import unittest
from datetime import datetime, timezone

from src.webapp.services.session_store import RedisSessionStore


class FakeRedisClient:
    def __init__(self):
        self.calls = []
        self.values = {}
        self.ttl_values = {}

    async def set(self, key, value, ex=None):
        self.calls.append({"key": key, "value": value, "ex": ex})
        self.values[key] = value
        self.ttl_values[key] = ex

    async def get(self, key):
        return self.values.get(key)

    async def ttl(self, key):
        return self.ttl_values.get(key, -1)


class SessionStoreTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_save_session_serializes_datetime_payload(self):
        redis_client = FakeRedisClient()
        session_store = RedisSessionStore(redis_client=redis_client, key_prefix="smart-assistant:session")
        payload = {
            "session_id": "sess_123",
            "created_at": datetime(2026, 3, 9, 2, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 3, 9, 2, 20, 0, tzinfo=timezone.utc),
            "metadata": {"source": "test"},
        }

        await session_store.save_session(
            session_id="sess_123",
            payload=payload,
            expire_seconds=1200,
        )

        self.assertEqual(len(redis_client.calls), 1)
        redis_call = redis_client.calls[0]
        self.assertEqual(redis_call["key"], "smart-assistant:session:sess_123")
        self.assertEqual(redis_call["ex"], 1200)

        serialized_payload = json.loads(redis_call["value"])
        self.assertEqual(serialized_payload["session_id"], "sess_123")
        self.assertEqual(serialized_payload["created_at"], "2026-03-09T02:00:00+00:00")
        self.assertEqual(serialized_payload["expires_at"], "2026-03-09T02:20:00+00:00")
        self.assertEqual(serialized_payload["metadata"], {"source": "test"})

    async def test_get_session_returns_deserialized_payload(self):
        redis_client = FakeRedisClient()
        redis_client.values["smart-assistant:session:sess_123"] = json.dumps(
            {"session_id": "sess_123", "conversation_id": "conv_123"},
            ensure_ascii=False,
        )
        session_store = RedisSessionStore(redis_client=redis_client, key_prefix="smart-assistant:session")

        payload = await session_store.get_session(session_id="sess_123")

        self.assertEqual(payload, {"session_id": "sess_123", "conversation_id": "conv_123"})

    async def test_set_conversation_id_preserves_existing_ttl(self):
        redis_client = FakeRedisClient()
        redis_key = "smart-assistant:session:sess_123"
        redis_client.values[redis_key] = json.dumps(
            {"session_id": "sess_123", "expire_seconds": 1200},
            ensure_ascii=False,
        )
        redis_client.ttl_values[redis_key] = 900
        session_store = RedisSessionStore(redis_client=redis_client, key_prefix="smart-assistant:session")

        payload = await session_store.set_conversation_id(
            session_id="sess_123",
            conversation_id="conv_123",
        )

        self.assertEqual(payload["conversation_id"], "conv_123")
        self.assertEqual(redis_client.calls[-1]["ex"], 900)
        updated_payload = json.loads(redis_client.values[redis_key])
        self.assertEqual(updated_payload["conversation_id"], "conv_123")


if __name__ == "__main__":
    unittest.main()
