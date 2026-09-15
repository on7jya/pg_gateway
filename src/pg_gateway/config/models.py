from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FieldType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    UUID = "uuid"
    DATETIME = "datetime"
    DATE = "date"
    JSON = "json"
    DECIMAL = "decimal"


PYTHON_TYPES: dict[FieldType, type] = {
    FieldType.STRING: str,
    FieldType.INT: int,
    FieldType.FLOAT: float,
    FieldType.BOOL: bool,
    FieldType.UUID: UUID,
    FieldType.DATETIME: datetime,
    FieldType.DATE: date,
    FieldType.JSON: dict,
    FieldType.DECIMAL: Decimal,
}


class PaginationConfig(BaseModel):
    default_limit: int = 20
    max_limit: int = 100


class GatewayConfig(BaseModel):
    base_path: str = "/api/v1"
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    query_timeout_ms: int = 5000


class AuthzConfig(BaseModel):
    mode: str = "header_stub"
    tenant_header: str = "X-Tenant-Id"
    roles_header: str = "X-Roles"
    trust_header: str = "X-Gateway-Token"


class SoftDeleteConfig(BaseModel):
    enabled: bool = False
    field: str = "deleted_at"


class OperationsConfig(BaseModel):
    list: bool = True
    get: bool = True
    create: bool = True
    update: bool = True
    patch: bool = True
    delete: bool = True
    batch_create: bool = True
    bulk_delete: bool = True
    upsert: bool = True
    aggregate: bool = True


class RowFilterConfig(BaseModel):
    column: str
    from_context: str
    required: bool = True


class FieldConfig(BaseModel):
    type: FieldType
    read: bool = True
    write: bool = True
    required: bool = False
    nullable: bool = True
    primary_key: bool = False
    auto: bool = False  # server-generated / defaulted


class RoleFieldAccess(BaseModel):
    read: list[str] | None = None  # None = all readable fields
    write: list[str] | None = None


class RoleAccess(BaseModel):
    operations: list[str] | None = None  # None = all enabled ops
    fields: RoleFieldAccess | None = None


class RelationType(str, Enum):
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_ONE = "one_to_one"


class RelationConfig(BaseModel):
    resource: str
    type: RelationType
    local: str
    foreign: str


class AggregateConfig(BaseModel):
    allowed_functions: list[str] = Field(default_factory=lambda: ["count", "sum"])
    group_by: list[str] = Field(default_factory=list)
    sum_fields: list[str] = Field(default_factory=list)


class ResourceConfig(BaseModel):
    table: str
    pk: str = "id"
    soft_delete: SoftDeleteConfig = Field(default_factory=SoftDeleteConfig)
    operations: OperationsConfig = Field(default_factory=OperationsConfig)
    row_filters: list[RowFilterConfig] = Field(default_factory=list)
    fields: dict[str, FieldConfig]
    roles: dict[str, RoleAccess] = Field(default_factory=dict)
    relations: dict[str, RelationConfig] = Field(default_factory=dict)
    filterable: list[str] = Field(default_factory=list)
    sortable: list[str] = Field(default_factory=list)
    upsert_keys: list[str] = Field(default_factory=list)
    aggregate: AggregateConfig = Field(default_factory=AggregateConfig)

    @model_validator(mode="after")
    def validate_pk_in_fields(self) -> ResourceConfig:
        if self.pk not in self.fields:
            raise ValueError(f"pk '{self.pk}' must be declared in fields")
        return self


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    authz: AuthzConfig = Field(default_factory=AuthzConfig)
    resources: dict[str, ResourceConfig]

    @field_validator("resources")
    @classmethod
    def resources_non_empty(cls, v: dict[str, ResourceConfig]) -> dict[str, ResourceConfig]:
        if not v:
            raise ValueError("at least one resource is required")
        return v

    def resource(self, name: str) -> ResourceConfig:
        if name not in self.resources:
            raise KeyError(name)
        return self.resources[name]


class Settings(BaseModel):
    """Runtime settings from environment."""

    database_url: str = "postgresql://gateway:gateway@localhost:5432/gateway"
    config_path: str = "config/config.yaml"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    gateway_trust_token: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        import os

        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://gateway:gateway@localhost:5432/gateway",
            ),
            config_path=os.getenv("CONFIG_PATH", "config/config.yaml"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "info"),
            gateway_trust_token=os.getenv("GATEWAY_TRUST_TOKEN", ""),
        )
