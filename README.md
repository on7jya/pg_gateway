# pg_gateway

Config-driven PostgreSQL API Gateway. FastAPI routes and Pydantic schemas are generated from YAML — no hardcoded ORM models. SQL uses **asyncpg** with parameterized queries; table/column identifiers come only from a config whitelist.

## Architecture

```
Client → FastAPI (dynamic routers) → ACL + row filters → QueryBuilder → asyncpg → Postgres
                ↑
         config/config.yaml (startup load)
```

| Piece | Role |
|-------|------|
| `config/config.yaml` | Resources, fields, ACL, relations, filters, soft-delete |
| `RequestContext` middleware | `X-Tenant-Id`, `X-Roles` → context |
| `ACLChecker` | Operation + field permissions by role |
| `QueryBuilder` | Safe SQL (quoted identifiers from whitelist) |
| `AuthzPort` | Stub for future external authz |
| `openapi.yaml` | Export artifact (OpenAPI 3.1), not the source of truth |
| `openspec/` | Behavioral specs (routing, ACL, query engine, errors) |

## Quick start

```bash
# Start Postgres + gateway
make up

# Or local Python against compose Postgres only:
docker compose up -d postgres
python -m venv .venv && source .venv/bin/activate
make install-dev
export DATABASE_URL=postgresql://gateway:gateway@localhost:5432/gateway
export CONFIG_PATH=config/config.yaml
uvicorn pg_gateway.main:app --reload --port 8000
```

Health: `GET http://localhost:8000/health`  
Ready: `GET http://localhost:8000/ready`

## Demo headers

| Header | Example |
|--------|---------|
| `X-Tenant-Id` | `11111111-1111-1111-1111-111111111111` (tenant A) |
| `X-Roles` | `admin` or `reader` |

Tenant B seed: `22222222-2222-2222-2222-222222222222`

## Demo curl scenarios

```bash
TENANT=11111111-1111-1111-1111-111111111111
H=(-H "X-Tenant-Id: $TENANT" -H "X-Roles: admin")

# List users
curl -s "http://localhost:8000/api/v1/users" "${H[@]}" | jq

# Filter + sort + pagination
curl -s "http://localhost:8000/api/v1/users?filter[status][eq]=active&sort=-created_at&limit=10" "${H[@]}" | jq

# Get by id with include (join depth 1)
curl -s "http://localhost:8000/api/v1/users/a0000000-0000-0000-0000-000000000001?include=orders" "${H[@]}" | jq

# Create
curl -s -X POST "http://localhost:8000/api/v1/users" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"email":"dave@acme.test","full_name":"Dave","status":"active"}' | jq

# PATCH
curl -s -X PATCH "http://localhost:8000/api/v1/users/<id>" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Dave Updated"}' | jq

# Soft-delete
curl -s -X DELETE "http://localhost:8000/api/v1/users/<id>" "${H[@]}" | jq
# Hidden by default; show with:
curl -s "http://localhost:8000/api/v1/users?include_deleted=true" "${H[@]}" | jq

# Batch create
curl -s -X POST "http://localhost:8000/api/v1/users/batch" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"email":"e1@acme.test","full_name":"E1"},{"email":"e2@acme.test","full_name":"E2"}]}' | jq

# Upsert (conflict on tenant_id + email)
curl -s -X POST "http://localhost:8000/api/v1/users/upsert" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"email":"alice@acme.test","full_name":"Alice Renamed","status":"active"}]}' | jq

# Aggregate orders
curl -s -X POST "http://localhost:8000/api/v1/orders/aggregate" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"function":"sum","field":"total_amount","group_by":["status"]}' | jq

# Bulk delete by filter
curl -s -X POST "http://localhost:8000/api/v1/users/bulk-delete" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"filters":{"status":{"eq":"inactive"}}}' | jq

# Missing tenant → 403
curl -s "http://localhost:8000/api/v1/users" -H "X-Roles: admin" | jq
```

## Makefile targets

| Target | Description |
|--------|-------------|
| `make up` | Build & start compose stack |
| `make down` | Stop stack |
| `make test` | Run pytest |
| `make lint` | Ruff |
| `make export-openapi` | Write `openapi.yaml` |
| `make demo` | Print demo hints |

## Tests

Requires **Python 3.11+** (CI/local via Docker recommended on older host Pythons):

```bash
make test
# equivalent:
docker compose up -d postgres
docker build -f Dockerfile.test -t pg_gateway_test .
docker run --rm --network pg_gateway_default \
  -v "$PWD":/app -w /app \
  -e DATABASE_URL=postgresql://gateway:gateway@postgres:5432/gateway \
  -e CONFIG_PATH=/app/config/config.yaml \
  -e PYTHONPATH=/app:/app/src \
  pg_gateway_test pytest -q
```

Integration tests expect Postgres at `DATABASE_URL` (default `postgresql://gateway:gateway@localhost:5432/gateway`).

## Config shape

See `config/config.yaml`. Field types: `string`, `int`, `float`, `bool`, `uuid`, `datetime`, `date`, `json`, `decimal`.

## OpenSpec

Behavioral specs live under `openspec/specs/` (`gateway-routing`, `access-control`, `query-engine`, `errors`). Complementary to the OpenAPI export.

## Out of scope (v1)

GraphQL, WebSockets, schema migrations, admin UI, multi-DB, Redis, real authentication.
