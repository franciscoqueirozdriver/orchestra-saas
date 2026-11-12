import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware import MaxBodySizeMiddleware
from app.routes_agents import router as agents_router
from app.routes_auth import router as auth_router
from app.routes_business import router as business_router
from app.routes_conversations import router as conversations_router
from app.routes_knowledge import router as knowledge_router
from app.routes_llm import router as llm_router
from app.routes_tenants import router as tenants_router
from app.routes_zapi import router as zapi_router
from app.routes_users import router as users_router
from app.routes_settings import router as settings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings.ensure_runtime_secrets()

app = FastAPI(
    title="diBBerDesk API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.environment != "production" else None,
)
app.add_middleware(
    MaxBodySizeMiddleware,
    upload_limit_bytes=(settings.upload_max_mb + 2) * 1024 * 1024,
    default_limit_bytes=1024 * 1024,
)


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "orquestra-api"})


@app.get("/api/health", include_in_schema=False)
def api_health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "orquestra-api"})


for router in (auth_router, tenants_router, agents_router, business_router, zapi_router, conversations_router, llm_router, knowledge_router, users_router, settings_router):
    app.include_router(router)
