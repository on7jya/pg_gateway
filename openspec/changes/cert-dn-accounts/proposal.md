# Change: Tenant-изоляция ТУЗ (1:1) + эксплуатация cert_dn

## Why

Режим `authz.mode: cert_dn` смержен в master с **отсутствием tenant-изоляции**:
у `AccountConfig` нет поля tenant, `row_filters` сняты, `ctx.tenant_id` в режиме
`cert_dn` остаётся `None`. Две ТУЗ с разными DN работают с одними и теми же
данными — ось «кто звонит» определена, ось «чьи данные» отсутствует. Это
**неправильно** для мультитенантного доступа.

Данный change исправляет это, закрепляя модель **ТУЗ = ровно один tenant**, и
дополнительно закрывает операционные пробелы для 50+ сервисов.

## What Changes

1. **Tenant-изоляция ТУЗ (1:1)**: `tenant_id` зашит в аккаунте; клиент его не
   передаёт и не может подделать. `row_filters` + Postgres RLS снова активны.
2. **Hot reload** реестра `accounts` без рестарта (fail-safe при невалидном файле).
3. ~~**Жизненный цикл сертификатов** (CRL/OCSP + короткие сроки)~~ — **ПРОПУЩЕНО** (вне scope).
4. **Governance контракта**: процесс версионирования/депрекации схемы.
5. **Опциональные корреляционные заголовки** `X-Session-Id` / `X-User-Id` — сервис
   может передать оба, один или ни одного; попадают в `RequestContext` (реализовано).

## Impact

| Область | Влияние |
|---------|---------|
| `src/pg_gateway/config/models.py` | `AccountConfig.tenant_id` (обязателен в `cert_dn`) + валидация; `session_id_header`/`user_id_header` |
| `src/pg_gateway/middleware.py` | `ctx.tenant_id = account.tenant_id`; DN→tenant map вместо `known_accounts`; разбор `X-Session-Id`/`X-User-Id` |
| `src/pg_gateway/context.py` | `session_id`, `user_id` (опциональные) |
| `src/pg_gateway/main.py` | проброс `account_tenants` в middleware |
| `config/accounts.example.yaml` | убрать `row_filters: []`, добавить `tenant_id` в каждый аккаунт |
| `deploy/k8s/accounts-configmap.yaml` | то же, что для example-оверлея |
| `db/init.sql` | без изменений (RLS уже использует `app.tenant_id`) |
| `src/pg_gateway/config/loader.py` | hot reload (перевалидация + перезагрузка) |
| `openspec/specs/access-control/spec.md` | MODIFY «Режим cert_dn», «Фильтры строк», «Postgres RLS»; ADD hot reload |

## Не меняем (остаётся принятым риском)

- **DN pass-through**: ingress MUST NOT strip/rewrite `X-Client-Cert-DN`. Риск
  подделки при слабом mTLS задокументирован в `design.md` (D2), вне scope.

## Out of Scope (v1)

- GraphQL, WebSockets, миграции схемы, admin UI, multi-DB, Redis.
- Полноценная JWT/OIDC-аутентификация.
- Multi-tenant ТУЗ (одна ТУЗ на несколько тенантов) — при необходимости отдельный change.
- Rate limiting / квоты / circuit breaker (точки расширения — позже).
- Курсорная/стримовая выгрузка (offset-пагинация достаточна).
