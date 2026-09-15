from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from pg_gateway.authz import HeaderStubAuthz
from pg_gateway.config import AppConfig, Settings, load_config
from pg_gateway.db import Database
from pg_gateway.errors import GatewayError, gateway_exception_handler, validation_exception_handler
from pg_gateway.middleware import RequestContextMiddleware
from pg_gateway.routers import build_api_router
from pg_gateway.service import ResourceService


def _require_trust_token(config: AppConfig, settings: Settings) -> str:
    token = (settings.gateway_trust_token or "").strip()
    if config.authz.mode == "header_stub" and not token:
        raise RuntimeError(
            "GATEWAY_TRUST_TOKEN is required when authz.mode=header_stub "
            "(set a non-empty shared secret; clients must send it as X-Gateway-Token)"
        )
    return token


def _known_roles(config: AppConfig) -> frozenset[str]:
    roles: set[str] = set()
    for resource in config.resources.values():
        roles.update(resource.roles.keys())
    return frozenset(roles)


def create_app(
    config: AppConfig | None = None,
    settings: Settings | None = None,
    *,
    connect_db: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if config is None:
        config_path = Path(settings.config_path)
        if not config_path.is_absolute():
            # resolve relative to CWD first, then project root heuristics
            if not config_path.exists():
                alt = Path(__file__).resolve().parents[2] / settings.config_path
                if alt.exists():
                    config_path = alt
        config = load_config(config_path)

    trust_token = _require_trust_token(config, settings)
    db = Database(settings.database_url, statement_timeout_ms=config.gateway.query_timeout_ms)
    authz = HeaderStubAuthz(config)
    service = ResourceService(config, db, authz)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.config = config
        app.state.settings = settings
        app.state.db = db
        app.state.service = service
        app.state.authz = authz
        if connect_db:
            await db.connect()
        try:
            yield
        finally:
            if connect_db:
                await db.disconnect()

    app = FastAPI(
        title="PostgreSQL API Gateway",
        version="0.1.0",
        description="Конфигурируемый API-шлюз для PostgreSQL",
        lifespan=lifespan,
        openapi_version="3.1.0",
    )

    app.add_exception_handler(GatewayError, gateway_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.add_middleware(
        RequestContextMiddleware,
        authz=config.authz,
        trust_token=trust_token,
        known_roles=_known_roles(config),
    )

    @app.get("/health", tags=["system"], summary="Проверка живости")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["system"], summary="Готовность")
    async def ready(request: Request) -> JSONResponse:
        database: Database = request.app.state.db
        try:
            if database.pool is None:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "database not connected", "code": "NOT_READY"},
                )
            await database.fetchval("SELECT 1")
            return JSONResponse({"status": "ready"})
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                status_code=503,
                content={"detail": str(exc), "code": "NOT_READY"},
            )

    api = build_api_router(config, service)
    app.include_router(api, prefix=config.gateway.base_path.rstrip("/"))

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["openapi"] = "3.1.0"
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["GatewayToken"] = {
            "type": "apiKey",
            "in": "header",
            "name": config.authz.trust_header,
            "description": "Общий секрет (GATEWAY_TRUST_TOKEN). Обязателен для всех API-маршрутов.",
        }
        schemes["TenantId"] = {
            "type": "apiKey",
            "in": "header",
            "name": config.authz.tenant_header,
        }
        schemes["Roles"] = {
            "type": "apiKey",
            "in": "header",
            "name": config.authz.roles_header,
            "description": "Роли через запятую из реестра ACL ресурса.",
        }
        schema["security"] = [{"GatewayToken": [], "TenantId": [], "Roles": []}]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


def run() -> None:
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(
        "pg_gateway.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


def __getattr__(name: str):
    """Lazy ASGI app for `uvicorn pg_gateway.main:app`."""
    if name == "app":
        return create_app(connect_db=True)
    raise AttributeError(name)
