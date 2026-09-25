# Контроль доступа

## Purpose

Описать режим технических учётных записей по DN сертификата (`cert_dn`), проводку `AuthzPort`, ACL по grants, права на уровне полей и изоляцию строк (включая Postgres RLS для демо с tenant).

## Requirements

### Requirement: Идентичность ТУЗ по DN сертификата

В режиме `cert_dn` доверие к peer-сертификату MUST устанавливаться на ingress (mTLS verify). Шлюз MUST идентифицировать техническую учётную запись по заголовку DN (по умолчанию `X-Client-Cert-DN`, exact match после trim) и загружать права из `accounts.<DN>.grants`. У записи account MUST быть поле `tenant_id` (ровно один tenant); tenant берётся из аккаунта, а не из заголовка. Envoy/ingress MUST NOT strip или rewrite `X-Client-Cert-DN` (pass-through); без peer cert edge MUST отвечать 401.

#### Scenario: Пустой или неизвестный DN

- **WHEN** запрос к API без `X-Client-Cert-DN` или с DN, отсутствующим в `accounts`
- **THEN** ответ — 401 с `{detail, code: UNAUTHORIZED}`

#### Scenario: Tenant из аккаунта

- **WHEN** известный DN с `tenant_id=A` вызывает операцию ресурса
- **THEN** контекст содержит `tenant_id=A`; заголовок `X-Tenant-Id` игнорируется

#### Scenario: Grant на ресурс

- **WHEN** DN известен и у аккаунта есть grant на `orders`
- **THEN** операции/поля берутся из grant; запрос к ресурсу вне grants — 403

### Requirement: ACL по grants

Права ТУЗ SHALL браться только из `accounts.<DN>.grants` (операции и поля чтения/записи). Операции и поля вне grant MUST отклоняться (403/400).

#### Scenario: Grant ограничивает операцию

- **WHEN** у ТУЗ в grant ресурса нет операции `create`
- **THEN** `POST /api/v1/{resource}` отвечает 403

#### Scenario: Grant ограничивает поля

- **WHEN** grant ресурса задаёт `fields.read` без колонки X
- **THEN** колонка X не появляется в ответах и не принимается на запись

### Requirement: Фильтры строк из контекста

Настроенные `row_filters` SHALL применяться ко всем запросам. Когда `required: true` и значение в контексте отсутствует, шлюз MUST отвечать HTTP 403 с кодом `MISSING_TENANT`. В режиме `cert_dn` значение `from_context` (`tenant_id`) поставляется из `accounts.<DN>.tenant_id`, а не из заголовка запроса.

#### Scenario: Отсутствует tenant

- **WHEN** запрос к ресурсу с привязкой к tenant не имеет tenant в контексте
- **THEN** ответ — 403 с `MISSING_TENANT`

#### Scenario: Изоляция tenant

- **WHEN** tenant A запрашивает список users
- **THEN** возвращаются только строки с `tenant_id = A`

### Requirement: Postgres RLS

Демо-таблицы (`users`, `orders`, `order_items`) MUST иметь включённый ROW LEVEL SECURITY с `FORCE ROW LEVEL SECURITY`. Политики SHALL ограничивать строки условием `tenant_id = current_setting('app.tenant_id', true)::uuid` (пустое/NULL значение настройки ⇒ нет строк). На каждом DB-запросе шлюз MUST устанавливать `app.tenant_id` из `RequestContext` через transaction-local `set_config` / `SET LOCAL`. Роль приложения MUST НЕ быть суперпользователем, обходящим RLS.

#### Scenario: RLS без tenant setting

- **WHEN** GUC `app.tenant_id` пуст
- **THEN** политика не возвращает строки для роли `gateway`

### Requirement: Проводка AuthzPort

Абстракция `AuthzPort` SHALL существовать для будущей внешней авторизации. Каждая операция ресурса (list/get/create/update/patch/delete/batch/upsert/bulk_delete/aggregate) MUST вызывать `authz.allow(...)` до выполнения и при `false` отвечать 403. Реализация `CertDnAuthz` SHALL разрешать ресурс iff у аккаунта есть grant. Детальные решения ACL остаются в `ACLChecker`.

#### Scenario: Отказ AuthzPort

- **WHEN** `authz.allow` возвращает false для операции
- **THEN** ответ — 403 до обращения к данным

### Requirement: Опциональные корреляционные заголовки

Шлюз SHALL разбирать опциональные заголовки `X-Session-Id` и `X-User-Id` (имена настраиваются) в `RequestContext` независимо от авторизации. Отсутствие, пустое значение или наличие только одного из них MUST быть допустимо. Значения MUST NOT влиять на авторизацию.

#### Scenario: Оба заголовка переданы

- **WHEN** сервис передаёт `X-Session-Id: sess-1` и `X-User-Id: user-1`
- **THEN** `RequestContext.session_id == "sess-1"` и `user_id == "user-1"`

#### Scenario: Передан только один или ни одного

- **WHEN** передан только `X-Session-Id` (или только `X-User-Id`, или ни одного)
- **THEN** недостающее значение — `None`, запрос обрабатывается без ошибки

### Requirement: Hot reload реестра accounts

Реестр `accounts` SHALL поддерживать обновление без перезапуска процесса. Новые grants/tenant
SHALL применяться к последующим запросам. При невалидном обновлении SHALL сохраняться
предыдущая валидная конфигурация, отказ SHALL логироваться, процесс MUST NOT падать.

#### Scenario: Обновление grant на лету

- **WHEN** `ACCOUNTS_CONFIG_PATH` изменён валидным содержимым
- **THEN** новые grants/tenant применяются к последующим запросам без рестарта

#### Scenario: Битый файл не ломает сервис

- **WHEN** обновлённый файл невалиден
- **THEN** продолжает действовать прежняя конфигурация, отказ логируется
