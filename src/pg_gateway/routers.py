"""Dynamic FastAPI routers generated from YAML resource config."""

from typing import Any

from fastapi import APIRouter, Query, Request

from pg_gateway.config.models import AppConfig
from pg_gateway.schemas import (
    create_aggregate_request_model,
    create_batch_model,
    create_bulk_delete_model,
    create_create_model,
    create_patch_model,
    create_update_model,
    create_upsert_model,
)
from pg_gateway.service import ResourceService, parse_filter_query_params


def build_resource_router(
    resource_name: str,
    app_config: AppConfig,
    service: ResourceService,
) -> APIRouter:
    config = app_config.resource(resource_name)
    ops = config.operations
    pagination = app_config.gateway.pagination

    CreateModel = create_create_model(resource_name, config)
    UpdateModel = create_update_model(resource_name, config)
    PatchModel = create_patch_model(resource_name, config)
    BatchModel = create_batch_model(resource_name, CreateModel)
    UpsertModel = create_upsert_model(resource_name, CreateModel)
    BulkDeleteModel = create_bulk_delete_model(resource_name)
    AggregateModel = create_aggregate_request_model(resource_name)

    router = APIRouter(tags=[resource_name])

    def _clamp_limit(limit: int | None) -> int:
        lim = pagination.default_limit if limit is None else limit
        if lim < 1:
            lim = 1
        return min(lim, pagination.max_limit)

    if ops.list:

        async def list_items(
            request: Request,
            limit: int | None = Query(None, ge=1),
            offset: int = Query(0, ge=0),
            sort: str | None = Query(None),
            include: str | None = Query(None),
            include_deleted: bool = Query(False),
        ) -> dict[str, Any]:
            filters = parse_filter_query_params(request.query_params)
            includes = [p.strip() for p in include.split(",") if p.strip()] if include else None
            return await service.list_resources(
                resource_name,
                limit=_clamp_limit(limit),
                offset=offset,
                sort=sort,
                filters=filters or None,
                include=includes,
                include_deleted=include_deleted,
            )

        router.add_api_route(f"/{resource_name}", list_items, methods=["GET"])

    if ops.create:

        async def create_item(payload: CreateModel) -> dict[str, Any]:  # type: ignore[valid-type]
            return await service.create(resource_name, payload.model_dump(exclude_unset=True))

        router.add_api_route(
            f"/{resource_name}", create_item, methods=["POST"], status_code=201
        )

    if ops.batch_create:

        async def batch_create(payload: BatchModel) -> list[dict[str, Any]]:  # type: ignore[valid-type]
            items = [i.model_dump(exclude_unset=True) for i in payload.items]
            return await service.batch_create(resource_name, items)

        router.add_api_route(
            f"/{resource_name}/batch", batch_create, methods=["POST"], status_code=201
        )

    if ops.upsert:

        async def upsert_items(payload: UpsertModel) -> list[dict[str, Any]]:  # type: ignore[valid-type]
            items = [i.model_dump(exclude_unset=True) for i in payload.items]
            return await service.upsert(resource_name, items)

        router.add_api_route(f"/{resource_name}/upsert", upsert_items, methods=["POST"])

    if ops.bulk_delete:

        async def bulk_delete(payload: BulkDeleteModel) -> dict[str, Any]:  # type: ignore[valid-type]
            data = payload.model_dump(exclude_unset=True)
            return await service.bulk_delete(
                resource_name,
                ids=data.get("ids"),
                filters=data.get("filters"),
            )

        router.add_api_route(
            f"/{resource_name}/bulk-delete", bulk_delete, methods=["POST"]
        )

    if ops.aggregate:

        async def aggregate(payload: AggregateModel) -> dict[str, Any]:  # type: ignore[valid-type]
            data = payload.model_dump(exclude_unset=True)
            return await service.aggregate(
                resource_name,
                function=data["function"],
                field=data.get("field"),
                group_by=data.get("group_by"),
                filters=data.get("filters"),
                include_deleted=data.get("include_deleted", False),
            )

        router.add_api_route(f"/{resource_name}/aggregate", aggregate, methods=["POST"])

    if ops.get:

        async def get_item(
            item_id: str,
            include: str | None = Query(None),
            include_deleted: bool = Query(False),
        ) -> dict[str, Any]:
            includes = [p.strip() for p in include.split(",") if p.strip()] if include else None
            return await service.get(
                resource_name,
                item_id,
                include=includes,
                include_deleted=include_deleted,
            )

        router.add_api_route(f"/{resource_name}/{{item_id}}", get_item, methods=["GET"])

    if ops.update:

        async def put_item(item_id: str, payload: UpdateModel) -> dict[str, Any]:  # type: ignore[valid-type]
            return await service.update(
                resource_name, item_id, payload.model_dump(exclude_unset=True)
            )

        router.add_api_route(f"/{resource_name}/{{item_id}}", put_item, methods=["PUT"])

    if ops.patch:

        async def patch_item(item_id: str, payload: PatchModel) -> dict[str, Any]:  # type: ignore[valid-type]
            return await service.patch(
                resource_name, item_id, payload.model_dump(exclude_unset=True)
            )

        router.add_api_route(f"/{resource_name}/{{item_id}}", patch_item, methods=["PATCH"])

    if ops.delete:

        async def delete_item(item_id: str) -> dict[str, Any]:
            return await service.delete(resource_name, item_id)

        router.add_api_route(f"/{resource_name}/{{item_id}}", delete_item, methods=["DELETE"])

    return router


def build_api_router(app_config: AppConfig, service: ResourceService) -> APIRouter:
    api = APIRouter()
    for name in app_config.resources:
        api.include_router(build_resource_router(name, app_config, service))
    return api
