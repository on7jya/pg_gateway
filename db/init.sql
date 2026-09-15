-- Demo CRM schema for pg_gateway (tenant-aware)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (tenant_id, email)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    order_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (tenant_id, order_number)
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, order_id, sku)
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_orders_tenant ON orders(tenant_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_order_items_tenant ON order_items(tenant_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- Seed tenants
-- tenant A: 11111111-1111-1111-1111-111111111111
-- tenant B: 22222222-2222-2222-2222-222222222222

INSERT INTO users (id, tenant_id, email, full_name, status) VALUES
    ('a0000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'alice@acme.test', 'Alice Admin', 'active'),
    ('a0000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'bob@acme.test', 'Bob Buyer', 'active'),
    ('b0000000-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', 'carol@other.test', 'Carol Other', 'active');

INSERT INTO orders (id, tenant_id, user_id, order_number, status, total_amount) VALUES
    ('c0000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'a0000000-0000-0000-0000-000000000001', 'ORD-1001', 'paid', 150.00),
    ('c0000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'a0000000-0000-0000-0000-000000000002', 'ORD-1002', 'pending', 40.00),
    ('c0000000-0000-0000-0000-000000000003', '22222222-2222-2222-2222-222222222222', 'b0000000-0000-0000-0000-000000000001', 'ORD-2001', 'paid', 99.50);

INSERT INTO order_items (tenant_id, order_id, sku, quantity, unit_price) VALUES
    ('11111111-1111-1111-1111-111111111111', 'c0000000-0000-0000-0000-000000000001', 'SKU-A', 2, 50.00),
    ('11111111-1111-1111-1111-111111111111', 'c0000000-0000-0000-0000-000000000001', 'SKU-B', 1, 50.00),
    ('11111111-1111-1111-1111-111111111111', 'c0000000-0000-0000-0000-000000000002', 'SKU-C', 4, 10.00),
    ('22222222-2222-2222-2222-222222222222', 'c0000000-0000-0000-0000-000000000003', 'SKU-X', 1, 99.50);
