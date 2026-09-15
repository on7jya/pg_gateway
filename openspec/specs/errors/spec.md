# Ошибки

## Purpose

Единая форма ответа об ошибке и отображение HTTP-статусов.

## Requirements

### Requirement: Конверт ошибки

Ответы об ошибках SHALL использовать JSON-тело `{ "detail": string, "code": string }`.

#### Scenario: Форма ошибки валидации

- **WHEN** тело запроса не проходит валидацию
- **THEN** ответ — 400 с `detail` и `code`

### Requirement: Отображение статусов

Шлюз SHALL отображать:

| Условие | Статус | Типичный код |
|-----------|--------|--------------|
| Валидация / некорректный query | 400 | `VALIDATION_ERROR` |
| Запрещено / отсутствует tenant / ACL | 403 | `FORBIDDEN` / `MISSING_TENANT` |
| Не найдено | 404 | `NOT_FOUND` |
| Нарушение уникальности | 409 | `UNIQUE_VIOLATION` |
| Таймаут запроса | 504 | `TIMEOUT` |

#### Scenario: Неизвестный id

- **WHEN** `GET /api/v1/users/{unknown}`
- **THEN** ответ — 404 с `{detail, code}`

### Requirement: Формы ответа списка и одиночного объекта

Успешные ответы списка SHALL быть `{ data, meta }`, где `meta` включает `total`, `limit`, `offset`. Успешные ответы одиночного объекта SHALL быть самим объектом (без обёртки).

#### Scenario: Конверт списка

- **WHEN** `GET /api/v1/users` успешен
- **THEN** тело содержит массив `data` и объект `meta`
