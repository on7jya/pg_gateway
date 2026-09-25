# Дельта спецификации: cert-dn-accounts (tenant-изоляция + эксплуатация)

## MODIFIED Requirements

### Requirement: Режим cert_dn (ТУЗ)

В режиме `authz.mode: cert_dn` доверие к peer-сертификату MUST устанавливаться на
ingress (mTLS verify). Шлюз MUST идентифицировать техническую учётную запись по
заголовку DN (по умолчанию `X-Client-Cert-DN`, exact match после trim) и загружать
права из `accounts.<DN>.grants`. Секция `accounts` MUST быть непустой при старте.
**У записи account MUST быть поле `tenant_id` (ровно один tenant); tenant берётся
из аккаунта, а не из заголовка.** `GATEWAY_TRUST_TOKEN` MUST NOT быть обязателен.
Заголовки `X-Roles` и `X-Tenant-Id` MUST игнорироваться, даже если переданы.
Envoy/ingress MUST NOT strip или rewrite `X-Client-Cert-DN` (pass-through); без peer
cert edge MUST отвечать 401.

#### Scenario: Пустой или неизвестный DN

- **WHEN** запрос к API без `X-Client-Cert-DN` или с DN, отсутствующим в `accounts`
- **THEN** ответ — 401 с `{detail, code: UNAUTHORIZED}`

#### Scenario: Tenant из аккаунта

- **WHEN** известный DN с `tenant_id=A` вызывает операцию ресурса
- **THEN** контекст содержит `tenant_id=A`; заголовок `X-Tenant-Id` игнорируется

#### Scenario: Аккаунт без tenant

- **WHEN** в `cert_dn` у аккаунта не задан `tenant_id`
- **THEN** конфигурация отклоняется при старте (валидация)

#### Scenario: Grant на ресурс

- **WHEN** DN известен и у аккаунта есть grant на `orders`
- **THEN** операции/поля берутся из grant; запрос к ресурсу вне grants — 403

### Requirement: Фильтры строк из контекста

Настроенные `row_filters` SHALL применяться ко всем запросам. Когда `required: true`
и значение в контексте отсутствует, шлюз MUST отвечать HTTP 403 с кодом
`MISSING_TENANT`. В режиме `cert_dn` значение `from_context` (`tenant_id`)
поставляется из `accounts.<DN>.tenant_id`, а не из заголовка запроса.

#### Scenario: Отсутствует tenant

- **WHEN** запрос к ресурсу с привязкой к tenant не имеет tenant в контексте
- **THEN** ответ — 403 с `MISSING_TENANT`

#### Scenario: Изоляция tenant между ТУЗ

- **WHEN** ТУЗ с `tenant_id=A` запрашивает список `users`
- **THEN** возвращаются только строки с `tenant_id=A` (строки tenant B недоступны)

### Requirement: Postgres RLS

Демо-таблицы (`users`, `orders`, `order_items`) MUST иметь включённый ROW LEVEL
SECURITY с `FORCE ROW LEVEL SECURITY`. Политики SHALL ограничивать строки условием
`tenant_id = current_setting('app.tenant_id', true)::uuid` (пустое/NULL значение
настройки ⇒ нет строк). На каждом DB-запросе шлюз MUST устанавливать `app.tenant_id`
из `RequestContext` через transaction-local `set_config` / `SET LOCAL`. В режиме
`cert_dn` значение `app.tenant_id` берётся из `accounts.<DN>.tenant_id`. Роль
приложения MUST НЕ быть суперпользователем, обходящим RLS.

#### Scenario: RLS при cert_dn tenant из аккаунта

- **WHEN** ТУЗ с `tenant_id=A` выполняет запрос
- **THEN** `app.tenant_id` устанавливается в `A`, политика возвращает строки только tenant A

#### Scenario: RLS без tenant setting

- **WHEN** GUC `app.tenant_id` пуст
- **THEN** политика не возвращает строки для роли `gateway`

## ADDED Requirements

### Requirement: Hot reload реестра accounts

Реестр `accounts` SHALL поддерживать обновление без перезапуска процесса. Новые
grants/tenant SHALL применяться к последующим запросам. При невалидном обновлении
SHALL сохраняться предыдущая валидная конфигурация, отказ SHALL логироваться,
процесс MUST NOT падать.

#### Scenario: Обновление grant на лету

- **WHEN** `ACCOUNTS_CONFIG_PATH` изменён валидным содержимым
- **THEN** новые grants/tenant применяются к последующим запросам без рестарта

#### Scenario: Битый файл не ломает сервис

- **WHEN** обновлённый файл невалиден
- **THEN** продолжает действовать прежняя конфигурация, отказ логируется

### Requirement: Опциональные корреляционные заголовки

Шлюз SHALL разбирать опциональные заголовки `X-Session-Id` и `X-User-Id`
(имена настраиваются) в `RequestContext` независимо от режима авторизации.
Отсутствие, пустое значение или наличие только одного из них MUST быть допустимо.
Эти значения MUST NOT влиять на авторизацию (только корреляция/observability).

#### Scenario: Оба заголовка переданы

- **WHEN** сервис передаёт `X-Session-Id: sess-1` и `X-User-Id: user-1`
- **THEN** `RequestContext.session_id == "sess-1"` и `user_id == "user-1"`

#### Scenario: Передан только один или ни одного

- **WHEN** передан только `X-Session-Id` (или только `X-User-Id`, или ни одного)
- **THEN** недостающее значение — `None`, запрос обрабатывается без ошибки

#### Scenario: Пустой заголовок

- **WHEN** заголовок передан пустым или из пробелов
- **THEN** значение трактуется как `None`

#### Scenario: Не влияет на авторизацию

- **WHEN** значения `X-Session-Id` / `X-User-Id` не соответствуют никаким grants/ролям
- **THEN** решение об авторизации не меняется (заголовки игнорируются ACL/AuthzPort)
