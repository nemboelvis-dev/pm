import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import router as auth_router
from app.board import router as board_router
from app.chat import router as chat_router
from app.database import initialize_database
from app.openrouter import router as openrouter_router


logger = logging.getLogger(__name__)

class Message(BaseModel):
    message: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    warn_if_static_directory_missing(static_directory)
    yield


def warn_if_static_directory_missing(directory: Path) -> None:
    if not directory.is_dir():
        logger.warning("Static frontend directory does not exist: %s", directory)


app = FastAPI(title="Project Management MVP", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(board_router)
app.include_router(chat_router)
app.include_router(openrouter_router)
default_static_directory = Path(__file__).resolve().parents[2] / "frontend" / "out"
static_directory = Path(os.getenv("STATIC_DIRECTORY", default_static_directory))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello", response_model=Message)
def hello() -> Message:
    return Message(message="Hello from FastAPI")


app.mount(
    "/",
    StaticFiles(directory=static_directory, html=True, check_dir=False),
    name="frontend",
)
