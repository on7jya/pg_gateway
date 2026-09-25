# pg_gateway

Конфигурируемый API-шлюз для PostgreSQL. Маршруты FastAPI и схемы Pydantic генерируются из YAML — без жёстко заданных ORM-моделей. SQL выполняется через **asyncpg** с параметризованными запросами; идентификаторы таблиц и колонок берутся только из whitelist конфига.

Аутентификация — **mTLS по DN сертификата** (`cert_dn`): техническая учётная запись (ТУЗ) идентифицируется по Subject DN клиентского сертификата, права берутся из `accounts.<DN>.grants`.

## Архитектура

```
Client → FastAPI (dynamic routers) → AuthzPort + ACL (grants) → QueryBuilder → asyncpg (SET LOCAL app.tenant_id) → Postgres RLS
                ↑
         config/config.yaml + config/accounts.example.yaml (startup load)
```

| Компонент | Роль |
|-----------|------|
| `config/config.yaml` | Ресурсы, поля, связи, фильтры, soft-delete |
| `config/accounts.example.yaml` | ТУЗ: `accounts.<DN>.grants` (операции и поля) |
| `RequestContext` middleware | `X-Client-Cert-DN` → ТУЗ; опциональные `X-Session-Id`/`X-User-Id` |
| `AuthzPort` | `CertDnAuthz` — ресурс доступен iff у аккаунта есть grant |
| `ACLChecker` | Права на операции и поля из `accounts.grants` |
| `QueryBuilder` | Безопасный SQL (quoted-идентификаторы из whitelist) |
| Postgres RLS | `FORCE ROW LEVEL SECURITY` на демо-таблицах по `app.tenant_id` |
| `openapi.yaml` | Экспортируемый артефакт (OpenAPI 3.1), не источник истины |
| `openspec/` | Поведенческие спецификации (маршрутизация, ACL, движок запросов, ошибки) |

## Требования

- **Python 3.11+** (для CI/локальных тестов на старых хостовых Python рекомендуется Docker)
- Docker Compose (для Postgres и полного стека)
- Реестр ТУЗ: `ACCOUNTS_CONFIG_PATH` (overlay с `accounts`), mTLS на ingress, заголовок `X-Client-Cert-DN` — см. `config/accounts.example.yaml` и `deploy/k8s/`

## Быстрый старт

```bash
# Поднять Postgres + gateway (accounts задан в compose)
make up

# Или локальный Python только против Postgres из compose:
docker compose up -d postgres
python -m venv .venv && source .venv/bin/activate
make install-dev
export DATABASE_URL=postgresql://gateway:gateway@localhost:5432/gateway
export CONFIG_PATH=config/config.yaml
export ACCOUNTS_CONFIG_PATH=config/accounts.example.yaml
uvicorn pg_gateway.main:app --reload --port 8000
```

Health (без DN): `GET http://localhost:8000/health`  
Ready (нужен DN): `GET http://localhost:8000/ready` с заголовком `X-Client-Cert-DN`

## Заголовки

| Заголовок | Пример | Описание |
|-----------|--------|----------|
| `X-Client-Cert-DN` | `CN=orders-reader,OU=tuz,O=Acme,C=RU` | Subject DN клиентского сертификата (mTLS на ingress) — обязателен |
| `X-Session-Id` | `sess-123` | (необязательно) сквозной id сессии для трассировки |
| `X-User-Id` | `user-456` | (необязательно) id пользователя/клиента |

`X-Session-Id` и `X-User-Id` опциональны и не влияют на авторизацию: можно не передавать
оба, передать только один или оба. Пустые значения игнорируются (`None` в контексте).

Права берутся из `accounts.<DN>.grants`. K8s: `deploy/k8s/`.

## Демо curl-сценарии

```bash
DN="CN=admin,OU=tuz,O=Acme,C=RU"
H=(-H "X-Client-Cert-DN: $DN")

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

# Upsert
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

# Нет DN → 401
curl -s "http://localhost:8000/api/v1/users" | jq

# Неизвестный DN → 401
curl -s "http://localhost:8000/api/v1/users" -H "X-Client-Cert-DN: CN=ghost,O=Acme,C=RU" | jq
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

См. `config/config.yaml` (ресурсы и схема) и `config/accounts.example.yaml` (ТУЗ/grants).
Типы полей: `string`, `int`, `float`, `bool`, `uuid`, `datetime`, `date`, `json`, `decimal`.

Переменные окружения — в `.env.example` (`DATABASE_URL`, `CONFIG_PATH`, `ACCOUNTS_CONFIG_PATH`, `RELOAD_INTERVAL` и др.).

### Hot reload реестра accounts

Реестр `accounts` (`ACCOUNTS_CONFIG_PATH`) опрашивается на изменения (по умолчанию раз в 2 сек,
`RELOAD_INTERVAL`). При валидном обновлении новые grants/tenant применяются без рестарта; при
невалидном файле сохраняется прежняя конфигурация и пишется предупреждение в лог.

## OpenSpec

Поведенческие спецификации лежат в `openspec/specs/` (`gateway-routing`, `access-control`, `query-engine`, `errors`, `versioning`). Дополняют экспорт OpenAPI.

## Версионирование и депрекация

- API версионируется через префикс пути (по умолчанию `/api/v1`); смена мажорной версии → новый префикс `/api/v2` параллельно со старым.
- Релизы следуют SemVer; ломающее изменение контракта → major.
- Депрекация: объявление в `CHANGELOG.md` → период депрекации (минимум один релиз) → удаление.
- Изменения контракта фиксируются в [`CHANGELOG.md`](CHANGELOG.md); потребители уведомляются до релиза.

Подробнее — `openspec/specs/versioning/spec.md`.

## Ограничения (v1)

Вне scope: GraphQL, WebSockets, миграции схемы, admin UI, multi-DB, Redis, полноценная JWT-аутентификация (внешний AuthzPort — позже).
