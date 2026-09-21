# Контроль доступа

## Purpose

Описать stub-контекст аутентификации по заголовкам с обязательным trust-токеном (`header_stub`), режим технических учётных записей по DN сертификата (`cert_dn`), проводку `AuthzPort` в путь запроса, ACL ролей/grants, права на уровне полей и изоляцию строк (включая Postgres RLS для демо с tenant).

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

### Requirement: Режим cert_dn (ТУЗ)

В режиме `authz.mode: cert_dn` доверие к peer-сертификату MUST устанавливаться на ingress (mTLS verify). Шлюз MUST идентифицировать техническую учётную запись по заголовку DN (по умолчанию `X-Client-Cert-DN`, exact match после trim) и загружать права из `accounts.<DN>.grants`. Секция `accounts` MUST быть непустой при старте. У записи account MUST NOT быть поля `tenant_id`. `GATEWAY_TRUST_TOKEN` MUST NOT быть обязателен. Заголовки `X-Roles` и `X-Tenant-Id` MUST игнорироваться, даже если переданы. Envoy/ingress MUST NOT strip или rewrite `X-Client-Cert-DN` (pass-through); без peer cert edge MUST отвечать 401.

#### Scenario: Пустой или неизвестный DN

- **WHEN** запрос к API без `X-Client-Cert-DN` или с DN, отсутствующим в `accounts`
- **THEN** ответ — 401 с `{detail, code: UNAUTHORIZED}`

#### Scenario: Grant на ресурс

- **WHEN** DN известен и у аккаунта есть grant на `orders`
- **THEN** операции/поля берутся из grant; запрос к ресурсу вне grants — 403

#### Scenario: Игнорирование Roles/Tenant

- **WHEN** в режиме `cert_dn` переданы `X-Roles` и/или `X-Tenant-Id`
- **THEN** они не влияют на контекст (`roles` пусты, `tenant_id` — `None`); решение — только по DN + grants

### Requirement: Фильтры строк из контекста

Настроенные `row_filters` SHALL применяться ко всем запросам. Когда `required: true` и значение в контексте отсутствует, шлюз MUST отвечать HTTP 403 с кодом `MISSING_TENANT` (или эквивалентом). Для сценариев `cert_dn` демо-конфиг MAY снимать обязательные tenant-фильтры (`required: false` или пустой `row_filters` в overlay).

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

Секция `roles` ресурса SHALL ограничивать операции и чтение/запись полей в режиме `header_stub`. Запросы без подходящей роли MUST отклоняться с 403. В режиме `cert_dn` ACL SHALL браться только из `accounts.grants` (секция `resources.*.roles` не применяется).

#### Scenario: Reader не может создавать

- **WHEN** роль `reader` вызывает `POST /api/v1/users`
- **THEN** ответ — 403

#### Scenario: Grant field ACL

- **WHEN** account grant задаёт ограниченный `fields.read`
- **THEN** ответ содержит только разрешённые поля

### Requirement: Проводка AuthzPort

Абстракция `AuthzPort` SHALL существовать для будущей внешней авторизации. Каждая операция ресурса (list/get/create/update/patch/delete/batch/upsert/bulk_delete/aggregate) MUST вызывать `authz.allow(...)` до выполнения и при `false` отвечать 403. Реализация `HeaderStubAuthz` SHALL проверять trust-контекст и наличие валидной роли ресурса; `CertDnAuthz` SHALL разрешать ресурс iff у аккаунта есть grant. Детальные решения ACL остаются в `ACLChecker`.

#### Scenario: Порт внедряем и вызывается

- **WHEN** приложение запускается
- **THEN** конкретная реализация `AuthzPort` привязана к состоянию приложения (`HeaderStubAuthz` или `CertDnAuthz` по `authz.mode`)

#### Scenario: Отказ AuthzPort

- **WHEN** `authz.allow` возвращает false для операции
- **THEN** ответ — 403 до обращения к данным
