# Tasks: cert-dn-accounts (tenant-изоляция + эксплуатация)

> Также выполнено (вне списка ниже): удаление режима `header_stub` (trust-токен,
> `X-Roles`/`X-Gateway-Token`, `GATEWAY_TRUST_TOKEN`) — остался только `cert_dn`.

## P0 — tenant-изоляция ТУЗ (безопасность)

- [x] **`AccountConfig.tenant_id`.** В `config/models.py` добавлено поле
      `tenant_id: str` (обязателен, валидация непустого значения).
- [x] **Проставить tenant из аккаунта.** В `middleware.py`: `ctx.tenant_id` из
      DN→tenant map (`account_tenants`).
- [x] **Проброс в middleware.** В `main.py` собрать `account_tenants` (DN → tenant_id)
      и передать в `RequestContextMiddleware`.
- [x] **Вернуть `row_filters`.** Убрано `row_filters: []` из
      `config/accounts.example.yaml`; `tenant_id` добавлен в каждый аккаунт.
- [x] **Проверить RLS.** `db.py::_apply_rls_tenant` ограничивает строки tenant'ом
      из аккаунта (без изменений в `db.py`/`init.sql`).
- [x] **Тесты изоляции.** Unit: tenant инжектится из аккаунта (`test_request_context.py`),
      валидация обязательного `tenant_id` (`test_cert_dn.py`). Integration:
      `test_tenant_isolation_between_accounts` (ТУЗ A не видит tenant B).

## P1 — операционная доводка

- [x] **Опциональные корреляционные заголовки.** `X-Session-Id` / `X-User-Id`
      в `RequestContext` (поля `session_id`/`user_id`), конфиг `AuthzConfig`,
      разбор в middleware (оба/один/ни одного; пустые → `None`), unit-тесты
      `tests/unit/test_request_context.py`, README.

- [x] **Hot reload реестра accounts (D4).** `config/reloader.py` (`ConfigReloader`):
      поллинг `ACCOUNTS_CONFIG_PATH` + `CONFIG_PATH`, перевалидация, атомарная подмена
      `app.state.config` + DN→tenant/grants реестра; fail-safe при невалидном файле.
      Фоновый таск в lifespan, интервал `RELOAD_INTERVAL`.
- [x] **Тесты hot reload.** `tests/unit/test_reload.py`: перевалидация валидного/битого
      оверлея, применение изменений к `account_tenants` и `app.state.config`.
- [-] **Жизненный цикл сертификатов (D5) — ПРОПУЩЕНО.** CRL/OCSP + короткие сроки на
      ingress. Вне scope по решению заказчика.
- [x] **Governance (D6).** `CHANGELOG.md` (Keep a Changelog + SemVer), спека
      `openspec/specs/versioning/spec.md`, правила `versioning` в `openspec/config.yaml`,
      раздел «Версионирование и депрекация» в README.

## P2 — отложено (точки расширения)

- [ ] Rate limit / квоты / circuit breaker на `account_dn` (хук в middleware/AuthzPort).
- [ ] Поднять `asyncpg` пул (`max_size`) и read replicas под нагрузку — по метрикам.
- [ ] Observability: `account_dn` + `tenant_id` в структурированные логи + метрики.

## Definition of Done

- Tenant-изоляция ТУЗ покрыта unit/integration-тестами (изоляция между аккаунтами,
  tenant из аккаунта, игнорирование заголовка, 403 при отсутствии tenant).
- Hot reload покрыт тестами (валидное обновление применяется, битый файл не роняет).
- `openspec/specs/access-control/spec.md` обновлён (см. `specs/`): MODIFY cert_dn/RLA/RLS,
  ADD hot reload + отзыв.
- README описывает `tenant_id` у аккаунтов, `ACCOUNTS_CONFIG_PATH` и hot reload.
