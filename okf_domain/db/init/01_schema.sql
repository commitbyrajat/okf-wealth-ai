CREATE TABLE customers (
    customer_id integer PRIMARY KEY,
    customer_name text NOT NULL,
    email text NOT NULL UNIQUE,
    risk_profile text NOT NULL CHECK (risk_profile IN ('conservative', 'balanced', 'growth')),
    created_at date NOT NULL
);

CREATE TABLE fund_master (
    fund_id integer PRIMARY KEY,
    fund_name text NOT NULL,
    amc_name text NOT NULL,
    category text NOT NULL,
    exit_load_period_days integer NOT NULL CHECK (exit_load_period_days >= 0),
    exit_load_rate numeric(5,2) NOT NULL CHECK (exit_load_rate >= 0),
    current_nav numeric(12,4) NOT NULL CHECK (current_nav > 0),
    nav_date date NOT NULL
);

CREATE TABLE transactions (
    transaction_id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES customers(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    fund_id integer NOT NULL REFERENCES fund_master(fund_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    type text NOT NULL CHECK (type IN ('BUY', 'SELL')),
    units numeric(18,4) NOT NULL CHECK (units > 0),
    transaction_date date NOT NULL
);

CREATE INDEX transactions_customer_id_idx ON transactions(customer_id);
CREATE INDEX transactions_fund_id_idx ON transactions(fund_id);
CREATE INDEX transactions_customer_fund_date_idx ON transactions(customer_id, fund_id, transaction_date);

COPY customers (customer_id, customer_name, email, risk_profile, created_at)
FROM '/seed-data/customers.csv'
WITH (FORMAT csv, HEADER true);

COPY fund_master (
    fund_id,
    fund_name,
    amc_name,
    category,
    exit_load_period_days,
    exit_load_rate,
    current_nav,
    nav_date
)
FROM '/seed-data/fund_master.csv'
WITH (FORMAT csv, HEADER true);

COPY transactions (transaction_id, customer_id, fund_id, type, units, transaction_date)
FROM '/seed-data/transactions.csv'
WITH (FORMAT csv, HEADER true);

CREATE VIEW current_holdings AS
SELECT
    c.customer_id,
    c.customer_name,
    f.fund_id,
    f.fund_name,
    f.category,
    SUM(CASE WHEN t.type = 'BUY' THEN t.units ELSE -t.units END)::numeric(18,4) AS units,
    f.current_nav,
    (SUM(CASE WHEN t.type = 'BUY' THEN t.units ELSE -t.units END) * f.current_nav)::numeric(18,2) AS market_value,
    CASE
        WHEN SUM(CASE WHEN t.type = 'BUY' THEN t.units ELSE -t.units END) <= 0 THEN 'CLOSED'
        ELSE 'OPEN'
    END AS status
FROM transactions t
JOIN customers c ON c.customer_id = t.customer_id
JOIN fund_master f ON f.fund_id = t.fund_id
GROUP BY c.customer_id, c.customer_name, f.fund_id, f.fund_name, f.category, f.current_nav;

CREATE VIEW redemption_lots AS
SELECT
    t.transaction_id AS buy_transaction_id,
    t.customer_id,
    c.customer_name,
    t.fund_id,
    f.fund_name,
    t.units,
    t.transaction_date,
    (CURRENT_DATE - t.transaction_date) AS holding_period_days,
    f.exit_load_period_days,
    f.exit_load_rate,
    ((CURRENT_DATE - t.transaction_date) >= f.exit_load_period_days) AS exit_load_free
FROM transactions t
JOIN customers c ON c.customer_id = t.customer_id
JOIN fund_master f ON f.fund_id = t.fund_id
WHERE t.type = 'BUY';
