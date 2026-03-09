from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

import logging
from src.webapp.socketio_app import emit_session_event


mcp = FastMCP("Smart Tools")

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
    session_id: Annotated[str, Field(description="The Dify session_id used to route the Socket.IO event to the correct client session.")],
) -> dict:
    """Trigger the department appointment modal on the client bound to the given session.

    Args:
        session_id: The Dify session_id used to route the Socket.IO event to the correct client session.
    """
    payload = {
        "type": "function",
        "name": "showDepartmentAppointment",
        "params": {},
    }
    logging.info(f"Emitting Socket.IO event for session_id={session_id} with payload={payload}")
    await emit_session_event(session_id, payload)
    return {
        "success": True,
        "session_id": session_id,
        "event": "message",
        "payload": payload,
    }


mcp_app = mcp.http_app(path='/smart-tools')