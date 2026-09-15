# Gateway Routing

## Purpose

Define how HTTP routes are generated from YAML configuration and exposed under the gateway base path.

## Requirements

### Requirement: Config is the route source of truth

The gateway SHALL generate FastAPI routes exclusively from the `resources` section of the YAML config. Hardcoded table/column ORM models MUST NOT be used as the schema source.

#### Scenario: Resource appears in config

- **WHEN** a resource named `users` is declared with `operations.list: true`
- **THEN** the gateway exposes `GET /api/v1/users`

#### Scenario: Operation disabled

- **WHEN** `operations.create` is `false` for a resource
- **THEN** `POST /api/v1/{resource}` is not registered

### Requirement: Approved path contract

The gateway SHALL expose these paths for each enabled operation:

- `GET/POST /api/v1/{resource}`
- `GET/PUT/PATCH/DELETE /api/v1/{resource}/{id}`
- `POST /api/v1/{resource}/batch`
- `POST /api/v1/{resource}/upsert`
- `POST /api/v1/{resource}/bulk-delete`
- `POST /api/v1/{resource}/aggregate`
- `GET /health`, `GET /ready`

#### Scenario: Batch path is not captured as id

- **WHEN** a client calls `POST /api/v1/users/batch`
- **THEN** the batch handler runs (not get-by-id)

### Requirement: OpenAPI is an artifact

OpenAPI 3.1 SHALL be exportable from the FastAPI app and MUST NOT be the route source of truth.

#### Scenario: Export

- **WHEN** `make export-openapi` is run
- **THEN** `openapi.yaml` is written reflecting generated routes and schemas
