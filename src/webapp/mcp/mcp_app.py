from typing import Annotated
from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request
from src.webapp.socketio_app import emit_session_event

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

mcp = FastMCP("Smart Tools")


async def _show_client_modal(function_name: str) -> dict[str, Any]:

    request: Request = get_http_request()
    session_id = request.query_params.get("session", "unknown_session")
    dify_conversion_id = request.query_params.get("dify_conversion_id", "unknown_dify_conversion_id")
    logging.info("Preparing to emit Socket.IO event for session_id=%s (Dify conversion_id=%s) with function_name=%s", session_id, dify_conversion_id, function_name)    
    

    payload = {
        "type": "function",
        "name": function_name,
        "params": {},
    }
    logging.info("Emitting Socket.IO event for session_id=%s with payload=%s", session_id, payload)
    await emit_session_event(session_id, payload)
    return {
        "success": True,
        "session_id": session_id,
        "event": "message",
        "payload": payload,
    }

@mcp.tool
def echo(
    p_input: Annotated[str, Field(description="The plain text content to echo back.")],
    session_id: Annotated[str, Field(description="The Dify session_id used to identify the current chat session.")],
) -> dict:
    """Echo the input string for testing purposes.

    Args:
        p_input: The plain text content to echo back.
        session_id: The Dify session_id used to identify the current chat session.
    """
    return {"echo": p_input, "session_id": session_id}

@mcp.tool
async def showDepartmentAppointmentModal(
    #session_id: Annotated[str, Field(description="The Dify session_id used to route the Socket.IO event to the correct client session.")],
) -> dict:
    """Trigger the department appointment modal on the client bound to the given session.
    """
    return await _show_client_modal( "showDepartmentAppointment")


@mcp.tool
async def showPatientReportModal(
    #session_id: Annotated[str, Field(description="The Dify session_id used to route the Socket.IO event to the correct client session.")],
) -> dict:
    """Trigger the patient report modal on the client bound to the given session.
    """
    return await _show_client_modal( "showPatientReportModal")


@mcp.tool
async def showQueueModal(
    #session_id: Annotated[str, Field(description="The Dify session_id used to route the Socket.IO event to the correct client session.")],
) -> dict:
    """Trigger the queue modal on the client bound to the given session.
    """
    return await _show_client_modal( "showQueueModal")


mcp_app = mcp.http_app(path='/smart-tools',transport="streamable-http")
