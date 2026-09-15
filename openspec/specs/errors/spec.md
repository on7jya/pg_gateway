# Errors

## Purpose

Uniform error response shape and status code mapping.

## Requirements

### Requirement: Error envelope

Error responses SHALL use JSON body `{ "detail": string, "code": string }`.

#### Scenario: Validation error shape

- **WHEN** a request body fails validation
- **THEN** the response is 400 with `detail` and `code`

### Requirement: Status mapping

The gateway SHALL map:

| Condition | Status | Typical code |
|-----------|--------|--------------|
| Validation / bad query | 400 | `VALIDATION_ERROR` |
| Forbidden / missing tenant / ACL | 403 | `FORBIDDEN` / `MISSING_TENANT` |
| Not found | 404 | `NOT_FOUND` |
| Unique violation | 409 | `UNIQUE_VIOLATION` |
| Query timeout | 504 | `TIMEOUT` |

#### Scenario: Unknown id

- **WHEN** `GET /api/v1/users/{unknown}`
- **THEN** response is 404 with `{detail, code}`

### Requirement: List vs single response shapes

Successful list responses SHALL be `{ data, meta }` where `meta` includes `total`, `limit`, `offset`. Successful single-object responses SHALL be the object itself (plain).

#### Scenario: List envelope

- **WHEN** `GET /api/v1/users` succeeds
- **THEN** body contains `data` array and `meta` object
