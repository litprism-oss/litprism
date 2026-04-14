from contextlib import asynccontextmanager
from typing import Any

from api.chat import router as chat_router
from api.criteria import router as criteria_router
from api.export import router as export_router
from api.projects import router as projects_router
from api.screening import router as screening_router
from api.search import router as search_router
from api.upload import router as upload_router
from db.engine import engine
from db.models import Base
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Any) -> None:
        for connection in self.active_connections:
            await connection.send_json(message)


ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="LitPrism API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(criteria_router)
app.include_router(search_router)
app.include_router(screening_router)
app.include_router(upload_router)
app.include_router(export_router)
app.include_router(chat_router)
