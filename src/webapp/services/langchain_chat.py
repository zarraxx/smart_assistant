from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Protocol

from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field

from src.webapp.socketio_app import emit_session_event


logger = logging.getLogger(__name__)


class LangchainGatewayError(Exception):
    def __init__(self, *, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class LangchainChatGateway(Protocol):
    async def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def open_stream_chat_message(self, payload: dict[str, Any]) -> AsyncIterator[str]: ...


@dataclass(slots=True)
class Context:
    user_id: str


async def _show_client_modal(
    session_id: str,
    function_name: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "type": "function",
        "name": function_name,
        "params": params or {},
    }
    logger.info("Emitting Socket.IO event for session_id=%s with payload=%s", session_id, payload)
    await emit_session_event(session_id, payload)
    return {
        "success": True,
        "session_id": session_id,
        "event": "message",
        "payload": payload,
    }


@tool
def add_number(a: int, b: int, runtime: ToolRuntime[Context]) -> int:
    """计算两个整数之和。"""
    logger.info("call add_number for session_id=%s", runtime.context.user_id)
    return a + b


#@tool
async def showDepartmentAppointmentModal(
    department_name: Annotated[str, Field(description="科室名称")],
    runtime: ToolRuntime[Context],
) -> dict[str, Any]:
    """打开科室预约弹窗。"""
    logger.info("call showDepartmentAppointment session id:%s", runtime.context.user_id)
    if not department_name.strip():
        return {
            "success": False,
            "error_msg": "department_name must not be empty",
            "session_id": runtime.context.user_id,
        }

    if "挂号" in department_name:
        return {
            "success": False,
            "error_msg": f"${department_name} is not a valid department name",
            "session_id": runtime.context.user_id,
        }

    return await _show_client_modal(
        runtime.context.user_id,
        "showDepartmentAppointment",
        params={"department_name": department_name.strip()},
    )


#@tool
async def showPatientReportModal(runtime: ToolRuntime[Context]) -> dict[str, Any]:
    """打开报告弹窗。"""
    logger.info("call showPatientReportModal session id:%s", runtime.context.user_id)
    return await _show_client_modal(runtime.context.user_id, "showPatientReportModal")


#@tool
async def showQueueModal(runtime: ToolRuntime[Context]) -> dict[str, Any]:
    """打开排队弹窗。"""
    logger.info("call showQueueModal session id:%s", runtime.context.user_id)
    return await _show_client_modal(runtime.context.user_id, "showQueueModal")


CHECKPOINTER = InMemorySaver()


class AsyncLangchainChatGateway:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: int = 300):
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.agent = create_agent(
            model=ChatOpenAI(
                model=model,
                temperature=0.0,
                max_tokens=8192,
                timeout=timeout_seconds,
                api_key=api_key,
                base_url=self.base_url,
                stream_usage=True,
                extra_body={"enable_thinking": True},
            ),
            tools=[
                add_number,
                showDepartmentAppointmentModal,
                showPatientReportModal,
                showQueueModal,
            ],
            system_prompt=self._load_prompt(),
            checkpointer=CHECKPOINTER,
        )

    async def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        answer_parts: list[str] = []
        async for chunk in self.open_stream_chat_message(payload):
            answer_parts.append(chunk)

        return {
            "event": "message",
            "answer": "".join(answer_parts),
            "session_id": payload["session_id"],
        }

    async def open_stream_chat_message(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        session_id = _require_non_empty_string(payload.get("session_id"), field_name="session_id")
        query = _extract_query(payload)
        config = {"configurable": {"thread_id": session_id}}

        try:
            async for chunk in self.agent.astream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                stream_mode="messages",
                context=Context(user_id=session_id),
            ):
                text = _extract_stream_text(chunk)
                if text:
                    yield text
        except LangchainGatewayError:
            raise
        except Exception as exc:
            logger.exception("LangChain chat request failed for session_id=%s", session_id)
            raise LangchainGatewayError(status_code=502, detail=str(exc)) from exc

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent / "prompt.md"
        if not prompt_path.exists():
            return "You are a helpful assistant."
        return prompt_path.read_text(encoding="utf-8")


def _extract_query(payload: dict[str, Any]) -> str:
    query = payload.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()

    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    raise LangchainGatewayError(status_code=400, detail="query is required")


def _extract_stream_text(chunk: Any) -> str:
    if isinstance(chunk, tuple):
        for item in chunk:
            text = _extract_stream_text(item)
            if text:
                return text
        return ""

    if isinstance(chunk, AIMessageChunk):
        return _normalize_message_content(chunk.content)
    return ""
    #content = getattr(chunk, "content", None)
    #return _normalize_message_content(content)


def _normalize_message_content(content: Any) -> str:
    logger.debug("Normalizing message content: %s", content)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

        return "".join(text_parts)

    return ""


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise LangchainGatewayError(status_code=400, detail=f"{field_name} is required")


def _normalize_base_url(base_url: str) -> str:
    normalized_url = (base_url or "").strip().rstrip("/")
    if not normalized_url:
        return "https://api.openai.com/v1"
    if normalized_url.endswith("/v1"):
        return normalized_url
    return f"{normalized_url}/v1"
