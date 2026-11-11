from contextlib import asynccontextmanager

from api.chat import router as chat_router
from api.criteria import router as criteria_router
from api.export import router as export_router
from api.fulltext import router as fulltext_router
from api.me import router as me_router
from api.projects import router as projects_router
from api.screening import router as screening_router
from api.search import router as search_router
from api.search import ws_router as search_ws_router
from api.upload import router as upload_router
from config import settings
from db.engine import engine
from db.models import Base
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.auth import check_auth_config


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    check_auth_config()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="LitPrism API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me_router)
app.include_router(projects_router)
app.include_router(criteria_router)
app.include_router(search_router)
app.include_router(search_ws_router)
app.include_router(screening_router)
app.include_router(upload_router)
app.include_router(export_router)
app.include_router(fulltext_router)
app.include_router(chat_router)
