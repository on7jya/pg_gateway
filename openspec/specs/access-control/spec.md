# Контроль доступа

## Purpose

Описать stub-контекст аутентификации по заголовкам с обязательным trust-токеном, проводку `AuthzPort` в путь запроса, ACL ролей, права на уровне полей и изоляцию строк (включая Postgres RLS).

## Requirements

### Requirement: Trust-токен для режима header_stub

В режиме `authz.mode: header_stub` шлюз MUST требовать непустой `GATEWAY_TRUST_TOKEN` при старте. Клиенты MUST передавать тот же секрет в заголовке trust (по умолчанию `X-Gateway-Token`). Без валидного токена шлюз MUST отвечать HTTP 401 с кодом `UNAUTHORIZED`. Эндпоинт `/health` MAY быть исключением (без токена).

#### Scenario: Отсутствует trust-токен

- **WHEN** запрос к `/api/v1/users` без `X-Gateway-Token` (или с неверным значением)
- **THEN** ответ — 401 с `{detail, code: UNAUTHORIZED}`

#### Scenario: Старт без секрета

- **WHEN** `authz.mode: header_stub` и `GATEWAY_TRUST_TOKEN` пуст или не задан
- **THEN** приложение MUST отказать в старте с явной ошибкой конфигурации

### Requirement: Контекст запроса из доверенных заголовков

В режиме `authz.mode: header_stub` шлюз SHALL читать tenant и роли из настроенных заголовков (по умолчанию `X-Tenant-Id`, `X-Roles`) **только после** успешной проверки trust-токена. Неизвестные роли (отсутствующие в реестре ролей ресурсов) MUST игнорироваться; если после фильтрации не осталось ни одной валидной роли при настроенных ролях ресурса — запрос MUST отклоняться (403).

#### Scenario: Разбор заголовка ролей

- **WHEN** передан валидный `X-Gateway-Token` и `X-Roles: admin,reader`
- **THEN** контекст запроса содержит роли `admin` и `reader` (если они объявлены в конфиге)

#### Scenario: Неизвестные роли

- **WHEN** передан валидный trust-токен и `X-Roles` содержит только неизвестные имена
- **THEN** ответ — 403 (роли не прошли AuthzPort / ACL)

### Requirement: Фильтры строк из контекста

Настроенные `row_filters` SHALL применяться ко всем запросам. Когда `required: true` и значение в контексте отсутствует, шлюз MUST отвечать HTTP 403 с кодом `MISSING_TENANT` (или эквивалентом).

#### Scenario: Отсутствует tenant

- **WHEN** запрос к ресурсу с привязкой к tenant содержит trust-токен и роли, но не содержит `X-Tenant-Id`
- **THEN** ответ — 403 с `{detail, code}`

#### Scenario: Изоляция tenant

- **WHEN** tenant A запрашивает список users
- **THEN** возвращаются только строки с `tenant_id = A`

### Requirement: Postgres RLS

Демо-таблицы (`users`, `orders`, `order_items`) MUST иметь включённый ROW LEVEL SECURITY с `FORCE ROW LEVEL SECURITY`. Политики SHALL ограничивать строки условием `tenant_id = current_setting('app.tenant_id', true)::uuid` (пустое/NULL значение настройки ⇒ нет строк). На каждом DB-запросе шлюз MUST устанавливать `app.tenant_id` из `RequestContext` через transaction-local `set_config` / `SET LOCAL`. Роль приложения MUST НЕ быть суперпользователем, обходящим RLS.

#### Scenario: RLS без tenant setting

- **WHEN** GUC `app.tenant_id` пуст
- **THEN** политика не возвращает строки для роли `gateway`

### Requirement: ACL ролей

Секция `roles` ресурса SHALL ограничивать операции и чтение/запись полей. Запросы без подходящей роли MUST отклоняться с 403.

#### Scenario: Reader не может создавать

- **WHEN** роль `reader` вызывает `POST /api/v1/users`
- **THEN** ответ — 403

### Requirement: Проводка AuthzPort

Абстракция `AuthzPort` SHALL существовать для будущей внешней авторизации. Каждая операция ресурса (list/get/create/update/patch/delete/batch/upsert/bulk_delete/aggregate) MUST вызывать `authz.allow(...)` до выполнения и при `false` отвечать 403. Реализация header-stub v1 SHALL проверять trust-контекст и наличие валидной роли ресурса; детальные решения ACL остаются в `ACLChecker`.

#### Scenario: Порт внедряем и вызывается

- **WHEN** приложение запускается
- **THEN** конкретная реализация `AuthzPort` привязана к состоянию приложения

#### Scenario: Отказ AuthzPort

- **WHEN** `authz.allow` возвращает false для операции
- **THEN** ответ — 403 до обращения к данным
