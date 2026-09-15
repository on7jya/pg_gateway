# pg_gateway

Конфигурируемый API-шлюз для PostgreSQL. Маршруты FastAPI и схемы Pydantic генерируются из YAML — без жёстко заданных ORM-моделей. SQL выполняется через **asyncpg** с параметризованными запросами; идентификаторы таблиц и колонок берутся только из whitelist конфига.

## Архитектура

```
Client → FastAPI (dynamic routers) → AuthzPort + ACL + row filters → QueryBuilder → asyncpg (SET LOCAL app.tenant_id) → Postgres RLS
                ↑
         config/config.yaml (startup load)
```

| Компонент | Роль |
|-----------|------|
| `config/config.yaml` | Ресурсы, поля, ACL, связи, фильтры, soft-delete |
| `RequestContext` middleware | Trust-токен + `X-Tenant-Id` / `X-Roles` → контекст |
| `AuthzPort` | Подключаемая авторизация (сейчас header stub; позже HTTP-сервис) |
| `ACLChecker` | Права на операции и поля по ролям |
| `QueryBuilder` | Безопасный SQL (quoted-идентификаторы из whitelist) |
| Postgres RLS | `FORCE ROW LEVEL SECURITY` на демо-таблицах по `app.tenant_id` |
| `openapi.yaml` | Экспортируемый артефакт (OpenAPI 3.1), не источник истины |
| `openspec/` | Поведенческие спецификации (маршрутизация, ACL, движок запросов, ошибки) |

## Требования

- **Python 3.11+** (для CI/локальных тестов на старых хостовых Python рекомендуется Docker)
- Docker Compose (для Postgres и полного стека)
- Переменная `GATEWAY_TRUST_TOKEN` **обязательна**, если `authz.mode=header_stub`

## Быстрый старт

```bash
# Поднять Postgres + gateway (демо trust-токен задан в compose)
make up

# Или локальный Python только против Postgres из compose:
docker compose up -d postgres
python -m venv .venv && source .venv/bin/activate
make install-dev
export DATABASE_URL=postgresql://gateway:gateway@localhost:5432/gateway
export CONFIG_PATH=config/config.yaml
export GATEWAY_TRUST_TOKEN=demo-trust-token
uvicorn pg_gateway.main:app --reload --port 8000
```

`GATEWAY_TRUST_TOKEN` **обязателен** при `authz.mode=header_stub`. Процесс не стартует, если переменная не задана или пуста.

Health (без токена): `GET http://localhost:8000/health`  
Ready (нужен токен): `GET http://localhost:8000/ready` с заголовком `X-Gateway-Token`

## Демо-заголовки

| Заголовок | Пример |
|-----------|--------|
| `X-Gateway-Token` | `demo-trust-token` (должен совпадать с `GATEWAY_TRUST_TOKEN`) |
| `X-Tenant-Id` | `11111111-1111-1111-1111-111111111111` (tenant A) |
| `X-Roles` | `admin` или `reader` (должны быть в `roles` ресурса) |

Seed tenant B: `22222222-2222-2222-2222-222222222222`

Заголовки tenant/roles принимаются **только после** успешной проверки trust-токена. Неизвестные роли отбрасываются; если валидных не осталось → 403.

## Демо curl-сценарии

```bash
TENANT=11111111-1111-1111-1111-111111111111
TOKEN=demo-trust-token
H=(-H "X-Gateway-Token: $TOKEN" -H "X-Tenant-Id: $TENANT" -H "X-Roles: admin")

# Список users
curl -s "http://localhost:8000/api/v1/users" "${H[@]}" | jq

# Фильтр + сортировка + пагинация
curl -s "http://localhost:8000/api/v1/users?filter[status][eq]=active&sort=-created_at&limit=10" "${H[@]}" | jq

# Получение по id с include (join глубины 1)
curl -s "http://localhost:8000/api/v1/users/a0000000-0000-0000-0000-000000000001?include=orders" "${H[@]}" | jq

# Создание
curl -s -X POST "http://localhost:8000/api/v1/users" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"email":"dave@acme.test","full_name":"Dave","status":"active"}' | jq

# PATCH
curl -s -X PATCH "http://localhost:8000/api/v1/users/<id>" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Dave Updated"}' | jq

# Soft-delete
curl -s -X DELETE "http://localhost:8000/api/v1/users/<id>" "${H[@]}" | jq
# По умолчанию скрыт; показать:
curl -s "http://localhost:8000/api/v1/users?include_deleted=true" "${H[@]}" | jq

# Пакетное создание
curl -s -X POST "http://localhost:8000/api/v1/users/batch" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"email":"e1@acme.test","full_name":"E1"},{"email":"e2@acme.test","full_name":"E2"}]}' | jq

# Upsert (конфликт по tenant_id + email)
curl -s -X POST "http://localhost:8000/api/v1/users/upsert" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"email":"alice@acme.test","full_name":"Alice Renamed","status":"active"}]}' | jq

# Агрегация orders
curl -s -X POST "http://localhost:8000/api/v1/orders/aggregate" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"function":"sum","field":"total_amount","group_by":["status"]}' | jq

# Массовое удаление по фильтру
curl -s -X POST "http://localhost:8000/api/v1/users/bulk-delete" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"filters":{"status":{"eq":"inactive"}}}' | jq

# Нет trust-токена → 401
curl -s "http://localhost:8000/api/v1/users" -H "X-Roles: admin" | jq

# Нет tenant → 403
curl -s "http://localhost:8000/api/v1/users" -H "X-Gateway-Token: $TOKEN" -H "X-Roles: admin" | jq
```

## Цели Makefile

| Цель | Описание |
|------|----------|
| `make up` | Сборка и запуск compose-стека |
| `make down` | Остановка стека |
| `make test` | Запуск pytest |
| `make lint` | Ruff |
| `make export-openapi` | Запись `openapi.yaml` |
| `make demo` | Подсказки по демо-заголовкам и curl |

## Тесты

Нужен **Python 3.11+** (в CI/локально через Docker рекомендуется на старых хостовых Python):

```bash
# Свежий volume БД, если обновляли init.sql / bootstrap-пользователя Postgres:
docker compose down -v
make test
```

Интеграционные тесты ожидают Postgres по `DATABASE_URL` (по умолчанию `postgresql://gateway:gateway@localhost:5432/gateway`).

## Обзор конфигурации

См. `config/config.yaml`. Типы полей: `string`, `int`, `float`, `bool`, `uuid`, `datetime`, `date`, `json`, `decimal`.

Переменные окружения — в `.env.example` (`DATABASE_URL`, `CONFIG_PATH`, `GATEWAY_TRUST_TOKEN` и др.).

## OpenSpec

Поведенческие спецификации лежат в `openspec/specs/` (`gateway-routing`, `access-control`, `query-engine`, `errors`). Дополняют экспорт OpenAPI.

## Ограничения (v1)

Вне scope: GraphQL, WebSockets, миграции схемы, admin UI, multi-DB, Redis, полноценная JWT-аутентификация (внешний AuthzPort — позже).
