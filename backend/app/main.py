from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401  (регистрация моделей в metadata)
from app.api import board, call, chat, ingest, tasks
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.migrate import migrate
from app.services.tasks import Conflict, NotFound, seed_boards


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    migrate(engine, get_settings().default_boards[0])
    with SessionLocal() as db:
        settings = get_settings()
        seed_boards(db, settings.default_boards, settings.default_columns)
    yield


app = FastAPI(title="TaskGram Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFound)
async def _not_found(_: Request, exc: NotFound):
    return JSONResponse({"detail": f"Not found: {exc}"}, status_code=404)


@app.exception_handler(Conflict)
async def _conflict(_: Request, exc: Conflict):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(IntegrityError)
async def _integrity(_: Request, exc: IntegrityError):
    return JSONResponse({"detail": "Integrity error"}, status_code=409)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


API_PREFIX = "/api/v1"
app.include_router(ingest.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(board.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(call.router, prefix=API_PREFIX)
