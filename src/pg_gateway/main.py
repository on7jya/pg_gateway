from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from pg_gateway.authz import CertDnAuthz
from pg_gateway.config import AppConfig, Settings, load_config
from pg_gateway.config.reloader import ConfigReloader
from pg_gateway.db import Database
from pg_gateway.errors import GatewayError, gateway_exception_handler, validation_exception_handler
from pg_gateway.middleware import RequestContextMiddleware
from pg_gateway.routers import build_api_router
from pg_gateway.service import ResourceService


def _account_tenants(config: AppConfig) -> dict[str, str]:
    return {dn: account.tenant_id for dn, account in config.accounts.items()}


def _require_accounts(config: AppConfig) -> None:
    if not config.accounts:
        raise RuntimeError(
            "at least one technical account (accounts) is required; "
            "set ACCOUNTS_CONFIG_PATH to the accounts overlay"
        )


def _resolve_config_path(path: str | Path) -> Path:
    config_path = Path(path)
    if not config_path.is_absolute() and not config_path.exists():
        alt = Path(__file__).resolve().parents[2] / path
        if alt.exists():
            return alt
    return config_path


def create_app(
    config: AppConfig | None = None,
    settings: Settings | None = None,
    *,
    connect_db: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    config_path: Path | None = None
    accounts_path: Path | None = None
    if config is None:
        config_path = _resolve_config_path(settings.config_path)
        if settings.accounts_config_path:
            accounts_path = _resolve_config_path(settings.accounts_config_path)
        config = load_config(config_path, accounts_path=accounts_path)

    _require_accounts(config)
    db = Database(settings.database_url, statement_timeout_ms=config.gateway.query_timeout_ms)
    authz = CertDnAuthz(config)
    service = ResourceService(config, db, authz)
    # Mutable DN→tenant map, shared with middleware and updated on reload.
    account_tenants = _account_tenants(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.config = config
        app.state.settings = settings
        app.state.db = db
        app.state.service = service
        app.state.authz = authz
        if connect_db:
            await db.connect()

        def apply_config(new_cfg: AppConfig) -> None:
            service.app_config = new_cfg
            authz.config = new_cfg
            account_tenants.clear()
            account_tenants.update(_account_tenants(new_cfg))
            app.state.config = new_cfg

        app.state.account_tenants = account_tenants
        reloader: ConfigReloader | None = None
        reload_task: asyncio.Task | None = None
        if config_path is not None and accounts_path is not None:
            reloader = ConfigReloader(
                base_path=config_path,
                accounts_path=accounts_path,
                apply=apply_config,
                interval=settings.reload_interval,
            )
            reload_task = asyncio.create_task(reloader.run())
        app.state.reloader = reloader

        try:
            yield
        finally:
            if reload_task is not None:
                reload_task.cancel()
                try:
                    await reload_task
                except asyncio.CancelledError:
                    pass
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
        account_tenants=account_tenants,
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
        schemes["ClientCertDN"] = {
            "type": "apiKey",
            "in": "header",
            "name": config.authz.client_dn_header,
            "description": (
                "Subject DN клиентского сертификата (mTLS на ingress). "
                "Права — из accounts.grants."
            ),
        }
        schema["security"] = [{"ClientCertDN": []}]
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
