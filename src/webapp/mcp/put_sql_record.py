import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.webapp.mcp.db_conn import get_async_session_factory


SESSION_BINDING_SQL = text(
    """
    SELECT c_app_id, c_dify_user_id
    FROM t_ai_chat_session
    WHERE c_session_id = :session_id
    """
)

INSERT_CHAT_HISTORY_SQL = text(
    """
    INSERT INTO ai_gateway.t_chat_history (
        c_id, c_assistant_content, c_completion_tokens, c_connect_cost, c_conversion_id,
        c_create_date, c_finish_time, c_message_cost, c_prompt_tokens, c_request_time,
        c_response_time, c_total_tokens, c_user_content, c_user_id, c_app,
        c_channel, c_session_id, c_message_id, c_page, c_message_type
    ) VALUES (
        :messageId, :ai_msg, NULL, NULL, NULL,
        :create_date, NULL, NULL, NULL, NULL,
        NULL, NULL, :user_msg, :c_dify_user_id, :app_id,
        NULL, :session_id, NULL, :page, 'NO_CHAT'
    )
    """
)

SOCKETIO_MESSAGE_PAGE = "socketio.message"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionBinding:
    app_id: Any
    dify_user_id: Any


async def put_socketio_message_record(
    session_id: str,
    payload: dict[str, Any],
    *,
    event: str = "message",
) -> str:
    logger.info(
        "Preparing to insert Socket.IO chat history record for session_id=%s event=%s payload_type=%s",
        session_id,
        event,
        payload.get("type"),
    )
    session_factory = get_async_session_factory()
    async with session_factory() as db_session:
        message_id = await insert_socketio_message_record(
            db_session,
            session_id=session_id,
            payload=payload,
            event=event,
        )
        await db_session.commit()
        logger.info(
            "Inserted Socket.IO chat history record message_id=%s session_id=%s",
            message_id,
            session_id,
        )
        return message_id


async def insert_socketio_message_record(
    db_session: AsyncSession,
    *,
    session_id: str,
    payload: dict[str, Any],
    event: str = "message",
) -> str:
    binding = await get_session_binding(db_session, session_id=session_id)
    message_id = str(uuid4())
    create_date = datetime.now()
    ai_msg = {
        "success": True,
        "session_id": session_id,
        "event": event,
        "payload": payload,
    }

    await db_session.execute(
        INSERT_CHAT_HISTORY_SQL,
        {
            "messageId": message_id,
            "ai_msg": _to_json(ai_msg),
            "create_date": create_date,
            "user_msg": "",
            "c_dify_user_id": binding.dify_user_id,
            "app_id": binding.app_id,
            "session_id": session_id,
            "page": SOCKETIO_MESSAGE_PAGE,
        },
    )
    return message_id


async def get_session_binding(db_session: AsyncSession, *, session_id: str) -> SessionBinding:
    result = await db_session.execute(SESSION_BINDING_SQL, {"session_id": session_id})
    row = result.mappings().first()
    if row is None:
        logger.warning("Chat session binding not found for session_id=%s", session_id)
        raise ValueError(f"Chat session binding not found for session_id={session_id}")

    logger.debug(
        "Loaded chat session binding for session_id=%s app_id=%s dify_user_id=%s",
        session_id,
        row["c_app_id"],
        row["c_dify_user_id"],
    )
    return SessionBinding(app_id=row["c_app_id"], dify_user_id=row["c_dify_user_id"])


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
