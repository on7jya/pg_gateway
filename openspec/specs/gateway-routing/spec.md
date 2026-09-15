# Маршрутизация шлюза

## Purpose

Определить, как HTTP-маршруты генерируются из YAML-конфигурации и публикуются под базовым путём шлюза.

## Requirements

### Requirement: Конфиг — источник истины для маршрутов

Шлюз SHALL генерировать маршруты FastAPI исключительно из секции `resources` YAML-конфига. Жёстко заданные ORM-модели таблиц/колонок MUST NOT использоваться как источник схемы.

#### Scenario: Ресурс объявлен в конфиге

- **WHEN** объявлен ресурс с именем `users` и `operations.list: true`
- **THEN** шлюз предоставляет `GET /api/v1/users`

#### Scenario: Операция отключена

- **WHEN** для ресурса `operations.create` равно `false`
- **THEN** `POST /api/v1/{resource}` не регистрируется

### Requirement: Утверждённый контракт путей

Шлюз SHALL предоставлять следующие пути для каждой включённой операции:

- `GET/POST /api/v1/{resource}`
- `GET/PUT/PATCH/DELETE /api/v1/{resource}/{id}`
- `POST /api/v1/{resource}/batch`
- `POST /api/v1/{resource}/upsert`
- `POST /api/v1/{resource}/bulk-delete`
- `POST /api/v1/{resource}/aggregate`
- `GET /health`, `GET /ready`

#### Scenario: Путь batch не перехватывается как id

- **WHEN** клиент вызывает `POST /api/v1/users/batch`
- **THEN** выполняется обработчик batch (а не get-by-id)

### Requirement: OpenAPI — артефакт

OpenAPI 3.1 SHALL быть экспортируемым из приложения FastAPI и MUST NOT быть источником истины для маршрутов.

#### Scenario: Экспорт

- **WHEN** выполняется `make export-openapi`
- **THEN** записывается `openapi.yaml`, отражающий сгенерированные маршруты и схемы
