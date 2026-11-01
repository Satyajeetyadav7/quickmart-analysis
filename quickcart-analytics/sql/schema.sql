-- QuickCart analytics schema (SQLite). Star-style: orders/order_items facts, customers/products dimensions.

CREATE TABLE customers (
    customer_id          INTEGER PRIMARY KEY,
    signup_date          TEXT    NOT NULL,          -- YYYY-MM-DD
    city                 TEXT    NOT NULL,
    city_tier            TEXT    NOT NULL,          -- Tier 1 / Tier 2
    acquisition_channel  TEXT    NOT NULL,
    age_group            TEXT,
    device               TEXT
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         REAL NOT NULL,                    -- selling price (INR)
    cost          REAL NOT NULL                     -- landed cost (INR)
);

CREATE TABLE orders (
    order_id          INTEGER PRIMARY KEY,
    customer_id       INTEGER NOT NULL REFERENCES customers(customer_id),
    order_ts          TEXT    NOT NULL,             -- YYYY-MM-DD HH:MM:SS
    order_date        TEXT    NOT NULL,             -- YYYY-MM-DD
    order_hour        INTEGER NOT NULL,             -- 0-23
    dow               INTEGER NOT NULL,             -- 0 = Monday ... 6 = Sunday
    delivery_minutes  REAL    NOT NULL,
    discount_pct      INTEGER NOT NULL,
    delivery_fee      REAL    NOT NULL,
    gross_value       REAL    NOT NULL,             -- sum(price * qty) before discount
    discount_amount   REAL    NOT NULL,
    net_revenue       REAL    NOT NULL,             -- gross - discount + delivery_fee
    cogs              REAL    NOT NULL,             -- sum(cost * qty)
    status            TEXT    NOT NULL,             -- delivered / cancelled
    rating            INTEGER,                      -- 1-5, NULL when not rated
    payment_method    TEXT
);

CREATE TABLE order_items (
    order_id    INTEGER NOT NULL REFERENCES orders(order_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    quantity    INTEGER NOT NULL,
    unit_price  REAL    NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

-- Assumed customer-acquisition cost per channel (INR). Illustrative inputs, not measured data.
CREATE TABLE channel_cac (
    channel  TEXT PRIMARY KEY,
    cac_inr  REAL NOT NULL
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date     ON orders(order_date);
CREATE INDEX idx_items_product   ON order_items(product_id);
