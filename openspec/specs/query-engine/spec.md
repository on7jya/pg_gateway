# Query Engine

## Purpose

Safe SQL generation, filtering, pagination, soft-delete, joins, aggregates, and transactional writes.

## Requirements

### Requirement: Whitelisted identifiers only

Table and column identifiers MUST come from the config whitelist. User input MUST only appear as parameterized values.

#### Scenario: Reject unknown filter field

- **WHEN** a filter references a non-filterable field
- **THEN** the gateway returns 400

### Requirement: Pagination

List endpoints SHALL support `limit` and `offset`. Default limit is 20; maximum is 100 (configurable).

#### Scenario: Clamp max limit

- **WHEN** `limit=1000` is requested
- **THEN** the effective limit is capped at `max_limit`

### Requirement: Filters and sort

The gateway SHALL support filter ops: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `like`, `ilike`, `is_null`. Sort SHALL use the `sort` query (`field` or `-field`).

#### Scenario: Equality filter

- **WHEN** `filter[status][eq]=active` is provided
- **THEN** only matching rows are returned

### Requirement: Soft-delete

When enabled, delete SHALL set `deleted_at` (configurable). Lists/gets SHALL exclude soft-deleted rows unless `include_deleted=true`.

#### Scenario: Soft delete hides row

- **WHEN** a user is soft-deleted
- **THEN** subsequent list without `include_deleted` omits that user

### Requirement: Includes (joins) depth ≤ 1

The gateway SHALL allow `include` to load declared relations only, and MUST limit include depth to at most 1.

#### Scenario: Include orders for user

- **WHEN** `GET /api/v1/users/{id}?include=orders`
- **THEN** the response embeds related `orders` for that user

### Requirement: Aggregations

`POST .../aggregate` SHALL allow only configured functions, group_by fields, and sum fields.

#### Scenario: Sum totals by status

- **WHEN** aggregate `sum` on `total_amount` grouped by `status` is requested for orders
- **THEN** grouped totals are returned

### Requirement: Transactions and timeouts

CUD, batch, upsert, and bulk-delete SHALL run in transactions. Query timeouts SHALL be enforced via configured `query_timeout_ms`.

#### Scenario: Unique conflict

- **WHEN** create violates a unique constraint
- **THEN** the response is 409 with code `UNIQUE_VIOLATION`
