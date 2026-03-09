import logging
from typing import Any
from urllib.parse import parse_qs

import socketio


logger = logging.getLogger(__name__)

socket_server = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_asgi_app = socketio.ASGIApp(socket_server, socketio_path=None)


def resolve_session_id(auth: Any, environ: dict[str, Any] | None) -> str | None:
    session_id = _normalize_session_id(_get_mapping_value(auth, "sessionId", "session_id"))
    if session_id:
        return session_id

    query_values = _get_query_values(environ)
    return _normalize_session_id(query_values.get("sessionId") or query_values.get("session_id"))


@socket_server.event
async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool | None:
    session_id = resolve_session_id(auth, environ)
    if not session_id:
        logger.warning("Socket.IO connection rejected because sessionId is missing")
        return False

    await socket_server.enter_room(sid, session_id)
    logger.info("Socket.IO client connected: sid=%s session_id=%s", sid, session_id)
    return None


@socket_server.event
async def disconnect(sid: str) -> None:
    logger.info("Socket.IO client disconnected: sid=%s", sid)


@socket_server.event
async def message(sid: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        return

    if payload.get("type") == "echo" and payload.get("name") == "debug":
        params = payload.get("params")
        if isinstance(params, dict):
            await socket_server.emit("message", params, to=sid)


async def emit_session_event(session_id: str, payload: dict[str, Any], event: str = "message") -> None:
    await socket_server.emit(event, payload, to=session_id)


def _get_mapping_value(source: Any, *keys: str) -> Any:
    if not isinstance(source, dict):
        return None

    for key in keys:
        if key in source:
            return source[key]

    return None


def _get_query_values(environ: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(environ, dict):
        return {}

    scope = environ.get("asgi.scope") if isinstance(environ.get("asgi.scope"), dict) else {}
    raw_query_string = scope.get("query_string", b"")

    if isinstance(raw_query_string, bytes):
        query_string = raw_query_string.decode("utf-8")
    elif isinstance(raw_query_string, str):
        query_string = raw_query_string
    else:
        query_string = ""

    parsed_query = parse_qs(query_string, keep_blank_values=False)
    return {key: values[0] for key, values in parsed_query.items() if values}


def _normalize_session_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    normalized_value = value.strip()
    return normalized_value or None
