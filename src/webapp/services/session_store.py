import json
from typing import Any, Protocol

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis


class SessionStore(Protocol):
    async def save_session(self, *, session_id: str, payload: dict[str, Any], expire_seconds: int) -> None: ...

    async def get_session(self, *, session_id: str) -> dict[str, Any] | None: ...

    async def set_conversation_id(self, *, session_id: str, conversation_id: str) -> dict[str, Any] | None: ...


class RedisSessionStore:
    def __init__(self, redis_client: Redis, key_prefix: str):
        self.redis_client = redis_client
        self.key_prefix = key_prefix

    async def save_session(self, *, session_id: str, payload: dict[str, Any], expire_seconds: int) -> None:
        await self._write_session(session_id=session_id, payload=payload, expire_seconds=expire_seconds)

    async def get_session(self, *, session_id: str) -> dict[str, Any] | None:
        redis_key = self._build_session_key(session_id)
        serialized_payload = await self.redis_client.get(redis_key)
        if not serialized_payload:
            return None

        return json.loads(serialized_payload)

    async def set_conversation_id(self, *, session_id: str, conversation_id: str) -> dict[str, Any] | None:
        session_payload = await self.get_session(session_id=session_id)
        if session_payload is None:
            return None

        if session_payload.get("conversation_id"):
            return session_payload

        session_payload["conversation_id"] = conversation_id
        redis_key = self._build_session_key(session_id)
        ttl_seconds = await self.redis_client.ttl(redis_key)
        expire_seconds = ttl_seconds if ttl_seconds and ttl_seconds > 0 else session_payload.get("expire_seconds")
        await self._write_session(
            session_id=session_id,
            payload=session_payload,
            expire_seconds=expire_seconds if isinstance(expire_seconds, int) else None,
        )
        return session_payload

    async def _write_session(
        self,
        *,
        session_id: str,
        payload: dict[str, Any],
        expire_seconds: int | None,
    ) -> None:
        redis_key = self._build_session_key(session_id)
        serialized_payload = json.dumps(jsonable_encoder(payload), ensure_ascii=False)
        await self.redis_client.set(redis_key, serialized_payload, ex=expire_seconds)

    def _build_session_key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{session_id}"
