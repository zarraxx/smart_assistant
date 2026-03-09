import codecs
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis, from_url

from src.webapp.config import Settings, get_settings
from src.webapp.schemas.chat import (
    ChatCompletionRequest,
    CreateChatRequest,
    CreateChatResponse,
    CreateChatResponseData,
)
from src.webapp.services.dify_chat import (
    AsyncDifyChatGateway,
    DifyGatewayError,
)
from src.webapp.services.session_store import RedisSessionStore, SessionStore


router = APIRouter(prefix="/chat", tags=["chat"])


@lru_cache
def get_redis_client() -> Redis:
    settings = get_settings()
    return from_url(settings.redis_url, decode_responses=True)


def get_session_store(
    settings: Settings = Depends(get_settings),
    redis_client: Redis = Depends(get_redis_client),
) -> SessionStore:
    return RedisSessionStore(redis_client=redis_client, key_prefix=settings.session_key_prefix)


def get_dify_chat_gateway(settings: Settings = Depends(get_settings)):
    return AsyncDifyChatGateway(
        base_url=settings.default_dify_url,
        api_key=settings.default_dify_api_key,
    )


@router.post("/create", response_model=CreateChatResponse)
async def create_chat_session(
    request: CreateChatRequest,
    session_store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings),
):
    expire_seconds = request.expire_seconds or settings.session_default_expire_seconds
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(seconds=expire_seconds)
    session_id = _generate_session_id()

    session_payload = _build_session_payload(
        request=request,
        session_id=session_id,
        expire_seconds=expire_seconds,
        created_at=created_at,
        expires_at=expires_at,
    )
    await session_store.save_session(
        session_id=session_id,
        payload=session_payload,
        expire_seconds=expire_seconds,
    )

    return CreateChatResponse(data=CreateChatResponseData.model_validate(session_payload))


@router.post("/completion")
async def create_chat_completion(
    request: ChatCompletionRequest,
    session_store: SessionStore = Depends(get_session_store),
    dify_chat_gateway=Depends(get_dify_chat_gateway),
):
    session_payload = await session_store.get_session(session_id=request.session_id)
    if session_payload is None:
        raise HTTPException(status_code=404, detail="session not found")

    payload = request.model_dump(exclude_none=True, exclude={"session_id"})
    conversation_id = session_payload.get("conversation_id")
    if isinstance(conversation_id, str) and conversation_id.strip():
        payload["conversation_id"] = conversation_id.strip()

    inputs = payload.get("inputs", {})
    inputs["__session_id__"] = request.session_id
    payload["inputs"] = inputs

    try:
        if request.response_mode == "blocking":
            response_payload = await dify_chat_gateway.create_blocking_chat_message(payload)
            await _bind_conversation_id_if_missing(
                session_store=session_store,
                session_payload=session_payload,
                session_id=request.session_id,
                response_payload=response_payload,
            )
            return JSONResponse(content=response_payload)

        stream_response = await dify_chat_gateway.open_stream_chat_message(payload)
    except DifyGatewayError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    media_type = stream_response.headers.get("content-type", "text/event-stream; charset=utf-8")
    return StreamingResponse(
        _iter_streaming_content_and_bind_conversation_id(
            response=stream_response,
            session_store=session_store,
            session_payload=session_payload,
            session_id=request.session_id,
        ),
        media_type=media_type,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _generate_session_id() -> str:
    return f"sess_{uuid4().hex}"


def _build_session_payload(
    *,
    request: CreateChatRequest,
    session_id: str,
    expire_seconds: int,
    created_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "user_id": request.user_id,
        "title": request.title,
        "expire_seconds": expire_seconds,
        "client_capabilities": request.client_capabilities,
        "metadata": request.metadata,
        "created_at": created_at,
        "expires_at": expires_at,
    }


async def _bind_conversation_id_if_missing(
    *,
    session_store: SessionStore,
    session_payload: dict[str, Any],
    session_id: str,
    response_payload: dict[str, Any],
) -> None:
    if session_payload.get("conversation_id"):
        return

    conversation_id = response_payload.get("conversation_id")
    if isinstance(conversation_id, str) and conversation_id.strip():
        await session_store.set_conversation_id(
            session_id=session_id,
            conversation_id=conversation_id.strip(),
        )


async def _iter_streaming_content_and_bind_conversation_id(
    *,
    response,
    session_store: SessionStore,
    session_payload: dict[str, Any],
    session_id: str,
    chunk_size: int = 8192,
):
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    conversation_bound = bool(session_payload.get("conversation_id"))

    try:
        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
            if not chunk:
                continue

            if not conversation_bound:
                buffer += decoder.decode(chunk)
                buffer, conversation_bound = await _process_sse_buffer(
                    buffer=buffer,
                    session_store=session_store,
                    session_id=session_id,
                    conversation_bound=conversation_bound,
                )

            yield chunk

        if not conversation_bound:
            buffer += decoder.decode(b"", final=True)
            _, _ = await _process_sse_buffer(
                buffer=buffer,
                session_store=session_store,
                session_id=session_id,
                conversation_bound=conversation_bound,
                flush=True,
            )
    finally:
        await response.aclose()


async def _process_sse_buffer(
    *,
    buffer: str,
    session_store: SessionStore,
    session_id: str,
    conversation_bound: bool,
    flush: bool = False,
) -> tuple[str, bool]:
    events = buffer.split("\n\n")
    remainder = "" if flush else (events.pop() if events else "")

    for event_block in events:
        for line in event_block.splitlines():
            stripped_line = line.strip()
            if not stripped_line.startswith("data:"):
                continue

            raw_data = stripped_line[5:].strip()
            if not raw_data or raw_data == "[DONE]":
                continue

            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            conversation_id = payload.get("conversation_id")
            if conversation_bound:
                continue

            if isinstance(conversation_id, str) and conversation_id.strip():
                await session_store.set_conversation_id(
                    session_id=session_id,
                    conversation_id=conversation_id.strip(),
                )
                conversation_bound = True

    return remainder, conversation_bound
