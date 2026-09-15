# Движок запросов

## Purpose

Безопасная генерация SQL, фильтрация, пагинация, soft-delete, joins, агрегаты и транзакционные записи.

## Requirements

### Requirement: Только идентификаторы из whitelist

Идентификаторы таблиц и колонок MUST браться из whitelist конфига. Пользовательский ввод MUST появляться только как параметризованные значения.

#### Scenario: Отклонение неизвестного поля фильтра

- **WHEN** фильтр ссылается на поле, недоступное для фильтрации
- **THEN** шлюз возвращает 400

### Requirement: Пагинация

Эндпоинты списка SHALL поддерживать `limit` и `offset`. Лимит по умолчанию — 20; максимум — 100 (настраивается).

#### Scenario: Ограничение максимального limit

- **WHEN** запрошен `limit=1000`
- **THEN** эффективный лимит ограничен значением `max_limit`

### Requirement: Фильтры и сортировка

Шлюз SHALL поддерживать операции фильтрации: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `like`, `ilike`, `is_null`. Сортировка SHALL использовать query-параметр `sort` (`field` или `-field`).

#### Scenario: Фильтр равенства

- **WHEN** передан `filter[status][eq]=active`
- **THEN** возвращаются только совпадающие строки

### Requirement: Soft-delete

При включении delete SHALL устанавливать `deleted_at` (настраивается). Операции list/get SHALL исключать soft-deleted строки, если не указано `include_deleted=true`.

#### Scenario: Soft-delete скрывает строку

- **WHEN** пользователь soft-deleted
- **THEN** последующий list без `include_deleted` не включает этого пользователя

### Requirement: Includes (joins) глубиной ≤ 1

Шлюз SHALL разрешать `include` только для объявленных связей и MUST ограничивать глубину include не более чем 1.

#### Scenario: Include orders для user

- **WHEN** `GET /api/v1/users/{id}?include=orders`
- **THEN** ответ встраивает связанные `orders` для этого пользователя

### Requirement: Агрегации

`POST .../aggregate` SHALL допускать только настроенные функции, поля group_by и поля sum.

#### Scenario: Сумма totals по status

- **WHEN** для orders запрошена агрегация `sum` по `total_amount` с группировкой по `status`
- **THEN** возвращаются сгруппированные итоги

### Requirement: Транзакции и таймауты

CUD, batch, upsert и bulk-delete SHALL выполняться в транзакциях. Таймауты запросов SHALL обеспечиваться через настроенный `query_timeout_ms`.

#### Scenario: Конфликт уникальности

- **WHEN** create нарушает unique constraint
- **THEN** ответ — 409 с кодом `UNIQUE_VIOLATION`
