from pathlib import Path

from typing import Annotated,Any, AsyncIterator, Protocol
from pydantic import Field

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI
from dataclasses import dataclass
import logging
from asgiref.sync import async_to_sync

from src.webapp.socketio_app import emit_session_event

class LangchainChatGateway(Protocol):
    async def open_stream_chat_message(self, payload: dict[str, Any]): ...

@dataclass
class Context:
    """Custom runtime context schema."""
    user_id: str


async def _show_client_modal(session_id: str, function_name: str,params = {}) -> dict[str, Any]:
    payload = {
        "type": "function",
        "name": function_name,
        "params": params,
    }
    logging.info("Emitting Socket.IO event for session_id=%s with payload=%s", session_id, payload)
    await emit_session_event(session_id, payload)
    return {
        "success": True,
        "session_id": session_id,
        "event": "message",
        "payload": payload,
    }


@tool
def add_number(a: int, b: int, runtime: ToolRuntime[Context]) -> int:
    '''得到两个整数相加后的值'''
    logging.info("call add_number")
    user_id = runtime.context.user_id
    logging.info(f"user_id:{user_id}")
    return a + b

# @tool
# def showDepartmentAppointmentModal(
#     department_name: Annotated[str, Field(description="科室名称")],
#     runtime: ToolRuntime[Context],
# ) -> dict:
#     """打开科室预约界面.
#     """
#     #return await _show_client_modal(runtime.context.user_id, "showDepartmentAppointment")
#
#
#     logging.info(f"call showDepartmentAppointment session id:{runtime.context.user_id}")
#     result = async_to_sync(_show_client_modal)(
#     runtime.context.user_id,
#     "showDepartmentAppointment"
#     )
#     logging.info(result)
#     return result

async def showDepartmentAppointmentModal(
    department_name: Annotated[str, Field(description="科室名称")],
    runtime: ToolRuntime[Context],
) -> dict:
    """打开科室预约界面.
    """
    logging.info(f"call showDepartmentAppointment session id:{runtime.context.user_id}")
    return await _show_client_modal(runtime.context.user_id, "showDepartmentAppointment",params={"department_name": department_name})


# @tool
# def showPatientReportModal(
#     runtime: ToolRuntime[Context],
# ) -> dict:
#     """打开客户端的报告界面.
#     """
#     logging.info(f"call showPatientReportModal session id:{runtime.context.user_id}")
#     result = async_to_sync(_show_client_modal)(
#         runtime.context.user_id,
#         "showPatientReportModal"
#     )
#     logging.info(result)
#     return result
#     #return await _show_client_modal(runtime.context.user_id, "showPatientReportModal")



async def showPatientReportModal(
    runtime: ToolRuntime[Context],
) -> dict:
    """打开客户端的报告界面.
    """
    logging.info(f"call showPatientReportModal session id:{runtime.context.user_id}")
    return await _show_client_modal(runtime.context.user_id, "showPatientReportModal")


# @tool
# def showQueueModal(
#     runtime: ToolRuntime[Context],
# ) -> dict:
#     """Trigger the queue modal on the client bound to the given session.
#     """
#     #return await _show_client_modal(runtime.context.user_id, "showQueueModal")
#     logging.info(f"call showQueueModal session id:{runtime.context.user_id}")
#     result = async_to_sync(_show_client_modal)(
#         runtime.context.user_id,
#         "showQueueModal"
#     )
#     logging.info(result)
#     return result

async def showQueueModal(
    runtime: ToolRuntime[Context],
) -> dict:
    """Trigger the queue modal on the client bound to the given session.
    """

    logging.info(f"call showQueueModal session id:{runtime.context.user_id}")
    return await _show_client_modal(runtime.context.user_id, "showQueueModal")

checkpointer=InMemorySaver()
class AsyncLangchainChatGateway:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: int = 300):
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.checkpointer = checkpointer

        model = ChatOpenAI(
            model=model,
            temperature=0.3,
            max_tokens=8192,
            timeout=timeout_seconds,
            api_key = self.api_key,
            base_url = self.base_url,
            stream_usage=True,
            # ... (other params)
        )

        self.agent = create_agent(
            model= model,
            tools=[add_number,showDepartmentAppointmentModal,
                   showPatientReportModal,
                   showQueueModal],
            system_prompt=self._load_prompt(),
            checkpointer=self.checkpointer
        )

    def _load_prompt(self) -> str:
        # 获取当前 py 文件同目录下的 prompt.md
        prompt_path = Path(__file__).parent / "prompt.md"

        if not prompt_path.exists():
            # 给出友好的报错或默认值
            return "You are a helpful assistant."

        return prompt_path.read_text(encoding="utf-8")

    async def open_stream_chat_message(self, payload: dict[str, Any]):
        session_id = payload["session_id"]
        config = {"configurable": {"thread_id": session_id}}
        async for chunk in   self.agent.astream(
            {"messages": [{"role": payload["role"], "content": payload["content"]}]},
                {"configurable": {"thread_id": session_id}},
            stream_mode="messages",
            context=Context(user_id=session_id),
        ):
            if isinstance(chunk, tuple):
                message_chunk = next((x for x in chunk if isinstance(x, AIMessageChunk)), None)
                logging.info(message_chunk)
                if message_chunk:
                    yield message_chunk
            else:
                if isinstance(chunk, AIMessageChunk):
                    yield chunk



def _normalize_base_url(base_url: str) -> str:
    normalized_url = base_url.rstrip("/")
    if normalized_url.endswith("/v1"):
        return normalized_url
    return f"{normalized_url}/v1"


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    import os, sys
    import asyncio

    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    async def main() -> None:
        model_name = os.environ.get("OPENAI_MODEL")
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = ChatOpenAI(
            model=model_name,
            temperature=0.3,
            max_tokens=8192,
            timeout=30,
            api_key=api_key,
            base_url=_normalize_base_url(base_url),
            stream_usage=True,

        )


        checkpointer = InMemorySaver()

        async def add_number_async(a: int, b: int, runtime: ToolRuntime[Context]) -> int:
            '''得到两个整数相加后的值'''
            logging.info("call add_number")
            user_id = runtime.context.user_id
            logging.info(f"user_id:{user_id}")
            return a + b

        agent = create_agent(
            model=model,
            tools=[add_number_async],
            system_prompt="You are a helpful assistant",
            checkpointer=checkpointer
        )
        config = {"configurable": {"thread_id": "1"}}

        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": "你好介绍一下你自己! 算一下 5+12等于多少"}]},
                stream_mode="messages",
                config=config,
                context=Context(user_id="1"),
        ):
            message_chunk = chunk
            if isinstance(chunk,tuple):
                message_chunk = next((x for x in chunk if isinstance(x,AIMessageChunk)), None)

            if message_chunk:
                print(message_chunk)
            # if hasattr(message_chunk, "content"):
            #     print(message_chunk.content, end="", flush=True)

    asyncio.run(main())