# Design: Tenant-изоляция ТУЗ (1:1) + эксплуатация cert_dn

## Журнал решений (Decision Log)

| # | Решение | Источник / статус |
|---|---------|-------------------|
| D1 | Идентичность ТУЗ = полный Subject DN (`X-Client-Cert-DN`) | Смерженная спека — не меняем |
| D2 | DN pass-through: ingress не strip/rewrite заголовок | Смерженная спека — принятый риск |
| D3 | **ТУЗ = ровно один tenant** (`tenant_id` зашит в аккаунте) | Данный change (отменяет «без tenant» из спеки) |
| D4 | Реестр accounts = YAML + **hot reload** | Данный change |
| D5 | Отзыв (CRL/OCSP) + короткие сроки на ingress | ~~Данный change~~ — пропущено |
| D6 | Коннектор владеет контрактом + процесс депрекации | Данный change |
| D7 | Offset-пагинация достаточна | Зафиксировано, вне scope |

## Tenant-изоляция (D3)

**Модель:** каждая ТУЗ привязана ровно к одному `tenant_id`, значение хранится в
аккаунте и берётся **только из конфига**, не из запроса. Клиент не может ни
подменить, ни подделать tenant.

```yaml
accounts:
  "CN=orders-reader,OU=tuz,O=Acme,C=RU":
    tenant_id: 11111111-1111-1111-1111-111111111111   # ← привязка 1:1
    grants:
      orders: {operations: [list, get, aggregate], fields: {read: [...], write: []}}
```

**Поток:**

```
middleware (cert_dn) → проверить DN → account = accounts[DN]
                     → ctx.tenant_id = account.tenant_id   (не из заголовка)
service._authorize   → authz.allow(...)
QueryBuilder         → row_filters: tenant_id = ctx.tenant_id
db._apply_rls_tenant → SET LOCAL app.tenant_id = ctx.tenant_id  → RLS
```

**Конкретные изменения:**

| Файл | Что меняется |
|------|--------------|
| `config/models.py` | `AccountConfig.tenant_id: str \| None`; в `cert_dn` — обязателен, валидация непустого UUID |
| `middleware.py` | ветка `cert_dn`: `ctx.tenant_id = account.tenant_id`; вместо `known_accounts`-frozenset — DN→tenant map |
| `main.py` | собрать `account_tenants` (DN → tenant_id) и пробросить в middleware |
| `config/accounts.example.yaml` + `deploy/k8s/accounts-configmap.yaml` | **убрать** `row_filters: []`; добавить `tenant_id` в каждый аккаунт |
| `db/init.sql` | без изменений: RLS уже использует `app.tenant_id`, `_apply_rls_tenant` возьмёт его из контекста |

**Ограничение модели:** сервис, которому нужны данные нескольких тенантов,
держит несколько ТУЗ (по сертификату/аккаунту на tenant). Multi-tenant ТУЗ
(набор разрешённых тенантов + `X-Tenant-Id` в запросе) — отдельный change при
необходимости.

## Принятые риски (вне scope)

- **D2 — доверие к DN-заголовку.** Шлюз принимает `X-Client-Cert-DN` как
  pass-through. Корректность зависит от строгой верификации mTLS на ingress.
  Меры смягчения, не меняющие спеку: строгая конфигурация mTLS, мониторинг
  заголовка. (Tenant-подделка уже исключена через D3 — tenant из аккаунта.)

## Опциональные корреляционные заголовки (session_id / user_id)

- `AuthzConfig` получает `session_id_header` (по умолчанию `X-Session-Id`) и
  `user_id_header` (`X-User-Id`).
- `middleware` разбирает оба заголовка **независимо от режима** (и header_stub, и
  cert_dn), значения тримятся; пустое/отсутствующее → `None`.
- Кладётся в `RequestContext.session_id` / `RequestContext.user_id`. Не влияет на
  авторизацию — только корреляция/observability (логи, трассировка, метрики).

## Hot reload (D4)

- Watch `ACCOUNTS_CONFIG_PATH` (inotify/поллинг), перевалидация через
  `AppConfig.model_validate`, атомарная подмена `app.state.config` и изменяемого
  DN→tenant/grants реестра. Невалидный файл → сохранить прежнюю конфигурацию +
  лог отказа (fail-safe).

## Жизненный цикл сертификатов (D5) — ПРОПУЩЕНО

По решению заказчика пропущено (вне scope). CRL/OCSP и короткие сроки — при
необходимости отдельный change (настройка ingress, не код шлюза).

## Governance контракта (D6)

- Схема меняется только в `config/config.yaml` (коннектор владеет контрактом).
- Ломающее изменение → change-proposal, changelog, уведомление сервисов до релиза.

## Точки расширения (rate limit / circuit breaker)

- Единая точка входа — `AuthzPort.allow` + `RequestContext.account_dn` (+ tenant_id).
- Будущие rate limit / квоты вешаются на `account_dn` в middleware.
