CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'consulta'
        CHECK (role IN ('principal', 'administracion', 'ventas', 'bodega', 'consulta')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    sku VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(120),
    barcode VARCHAR(80),
    contifico_aux_code VARCHAR(80),
    cost NUMERIC(12, 4) NOT NULL DEFAULT 0,
    units_per_case INTEGER NOT NULL DEFAULT 12,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_positions (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL UNIQUE REFERENCES products(id),
    physical_confirmed INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    invoiced_pending_dispatch INTEGER NOT NULL DEFAULT 0,
    blocked_incident INTEGER NOT NULL DEFAULT 0,
    incoming_expected INTEGER NOT NULL DEFAULT 0,
    available_to_invoice INTEGER GENERATED ALWAYS AS (
        GREATEST(0, physical_confirmed - reserved - invoiced_pending_dispatch - blocked_incident)
    ) STORED,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id),
    user_id BIGINT REFERENCES users(id),
    movement_type VARCHAR(80) NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    source_document_type VARCHAR(80),
    source_document_id BIGINT,
    before_physical INTEGER,
    after_physical INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id BIGSERIAL PRIMARY KEY,
    chain_name VARCHAR(120) NOT NULL,
    order_number VARCHAR(120) NOT NULL,
    status VARCHAR(60) NOT NULL DEFAULT 'recibida',
    source_filename VARCHAR(255),
    notes TEXT,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chain_order_number UNIQUE (chain_name, order_number)
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    requested_quantity INTEGER NOT NULL,
    original_description TEXT
);

CREATE TABLE IF NOT EXISTS reservations (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id),
    purchase_order_id BIGINT REFERENCES purchase_orders(id),
    customer_name VARCHAR(255),
    quantity INTEGER NOT NULL,
    status VARCHAR(60) NOT NULL DEFAULT 'activa',
    reason TEXT NOT NULL,
    created_by_user_id BIGINT REFERENCES users(id),
    released_by_user_id BIGINT REFERENCES users(id),
    release_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_number VARCHAR(120) NOT NULL UNIQUE,
    customer_name VARCHAR(255),
    purchase_order_id BIGINT REFERENCES purchase_orders(id),
    status VARCHAR(60) NOT NULL DEFAULT 'facturada',
    contifico_source_id VARCHAR(120),
    registered_by_user_id BIGINT REFERENCES users(id),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dispatches (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    dispatched_quantity INTEGER NOT NULL,
    missing_quantity INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(60) NOT NULL,
    reason TEXT NOT NULL,
    confirmed_by_user_id BIGINT REFERENCES users(id),
    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,
    status VARCHAR(60) NOT NULL DEFAULT 'abierta',
    incident_type VARCHAR(80) NOT NULL,
    product_id BIGINT REFERENCES products(id),
    invoice_id BIGINT REFERENCES invoices(id),
    purchase_order_id BIGINT REFERENCES purchase_orders(id),
    description TEXT NOT NULL,
    resolution_notes TEXT,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS approvals (
    id BIGSERIAL PRIMARY KEY,
    status VARCHAR(60) NOT NULL DEFAULT 'solicitada',
    requested_by_user_id BIGINT REFERENCES users(id),
    approved_by_user_id BIGINT REFERENCES users(id),
    request_type VARCHAR(80) NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    action VARCHAR(120) NOT NULL,
    entity_type VARCHAR(120) NOT NULL,
    entity_id BIGINT,
    before_json TEXT,
    after_json TEXT,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS ix_stock_movements_product_id ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS ix_stock_movements_created_at ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_chain_name ON purchase_orders(chain_name);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_order_number ON purchase_orders(order_number);
CREATE INDEX IF NOT EXISTS ix_purchase_order_lines_purchase_order_id ON purchase_order_lines(purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_reservations_product_id ON reservations(product_id);
CREATE INDEX IF NOT EXISTS ix_reservations_status ON reservations(status);
CREATE INDEX IF NOT EXISTS ix_invoices_invoice_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS ix_invoice_lines_invoice_id ON invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS ix_dispatches_invoice_id ON dispatches(invoice_id);
CREATE INDEX IF NOT EXISTS ix_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity ON audit_log(entity_type, entity_id);
