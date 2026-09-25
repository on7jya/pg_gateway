# Changelog

Все заметные изменения проекта документируются здесь.
Формат — [Keep a Changelog](https://keepachangelog.com/ru/), версионирование — [SemVer](https://semver.org/).

## [Unreleased]

### Added

- Режим `cert_dn` (mTLS по DN сертификата) как единственный режим авторизации.
- Tenant-изоляция ТУЗ: `tenant_id` зашит в аккаунте (ровно один tenant).
- Hot reload реестра accounts (`RELOAD_INTERVAL`).
- Опциональные корреляционные заголовки `X-Session-Id` / `X-User-Id`.

### Removed

- Режим `header_stub`: `GATEWAY_TRUST_TOKEN`, заголовки `X-Gateway-Token`,
  `X-Roles`, `X-Tenant-Id`, роль-ACL (`resources.*.roles`).

### Fixed

- `batch` / `upsert` с элементами разной формы теперь отклоняются с
  `BATCH_SHAPE_MISMATCH` / `UPSERT_SHAPE_MISMATCH` (раньше отсутствующие NOT NULL
  колонки вставлялись как `NULL` и падали с `NotNullViolationError`).

## [0.1.0] - 2026-09-15

### Added

- Конфигурируемый API-шлюз к PostgreSQL: динамические роутеры и Pydantic-схемы
  из YAML, безопасный `QueryBuilder`, мягкое удаление, фильтры/сортировка/
  пагинация, joins (глубина ≤1), агрегаты, batch/upsert/bulk-delete.
- Изоляция строк через `row_filters` + Postgres RLS (`FORCE ROW LEVEL SECURITY`).
- Экспорт OpenAPI 3.1 как артефакт.
