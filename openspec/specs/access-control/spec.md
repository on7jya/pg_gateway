# Access Control

## Purpose

Describe header-stub auth context, role ACL, field-level permissions, and row-level security.

## Requirements

### Requirement: Request context from trusted headers

In `authz.mode: header_stub`, the gateway SHALL read tenant and roles from configured headers (`X-Tenant-Id`, `X-Roles` by default). Authentication is out of scope for v1.

#### Scenario: Roles header parsing

- **WHEN** `X-Roles: admin,reader` is sent
- **THEN** the request context contains roles `admin` and `reader`

### Requirement: Row-level filters from context

Configured `row_filters` SHALL be applied to all queries. When `required: true` and context value is missing, the gateway MUST respond with HTTP 403 and code `MISSING_TENANT` (or equivalent).

#### Scenario: Missing tenant

- **WHEN** a request to a tenant-scoped resource omits `X-Tenant-Id`
- **THEN** the response is 403 with `{detail, code}`

#### Scenario: Tenant isolation

- **WHEN** tenant A lists users
- **THEN** only rows with `tenant_id = A` are returned

### Requirement: Role ACL

Resource `roles` SHALL gate operations and field read/write. Requests without a matching role MUST be denied with 403.

#### Scenario: Reader cannot create

- **WHEN** role `reader` calls `POST /api/v1/users`
- **THEN** the response is 403

### Requirement: AuthzPort stub

An `AuthzPort` abstraction SHALL exist for future external authorization. v1 header stub may defer detailed decisions to ACLChecker while remaining pluggable.

#### Scenario: Port is injectable

- **WHEN** the application starts
- **THEN** a concrete `AuthzPort` implementation is bound on app state
