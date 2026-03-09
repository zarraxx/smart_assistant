from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import os, sys

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import contextlib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.webapp.config import get_settings
from src.webapp.routes.chat import router as chat_router
from src.webapp.socketio_app import socket_asgi_app, socket_server
from src.webapp.mcp.mcp_app import mcp,mcp_app

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = Path(__file__).parent
logging.info(f"ROOT_PATH: {BASE_DIR}")
ROOT_PATH = get_settings().root_path



# @contextlib.asynccontextmanager
# async def lifespan(app: FastAPI):
#     async with contextlib.AsyncExitStack() as stack:
#         # Enter the FastMCP session manager's context
#         await stack.enter_async_context(mcp.session_manager.run())
#         yield

app = FastAPI(
    title="Smart Assistant Backend",
    description="A backend server providing a WebSocket connection and an OpenAI-compatible API.",
    version="1.0.0",
    root_path=ROOT_PATH,
    lifespan=mcp_app.lifespan
)
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/socket.io", socket_asgi_app, name="socket.io")
app.include_router(chat_router)
app.state.socketio_server = socket_server

app.mount("/mcp", mcp_app)

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    root_path = request.scope.get("root_path", "")
    normalized_root_path = "" if root_path == "/" else root_path.rstrip("/")
    return templates.TemplateResponse(request, "index.html", {"root_path": normalized_root_path})


if __name__ == "__main__":
    import uvicorn
    logging.info("Starting server... in main")
    uvicorn.run("src.webapp.assistant_app:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(PROJECT_ROOT))
