CREATE TABLE IF NOT EXISTS derive_order_flow_events (
  id TEXT PRIMARY KEY,
  source_endpoint TEXT NOT NULL,
  external_event_id TEXT NOT NULL,

  event_kind TEXT NOT NULL,
  execution_type TEXT NOT NULL CHECK (execution_type IN ('ORDERBOOK_ORDER', 'RFQ')),
  leg_structure TEXT NOT NULL CHECK (leg_structure IN ('SINGLE_LEG', 'MULTI_LEG')),
  option_mix TEXT NOT NULL CHECK (option_mix IN ('CALL', 'PUT', 'BOTH')),

  trade_ts_ms INTEGER,
  observed_at_ms INTEGER NOT NULL,

  currency TEXT NOT NULL DEFAULT 'HYPE',
  instrument_type TEXT NOT NULL DEFAULT 'option',

  side TEXT NOT NULL CHECK (side IN ('buy', 'sell', 'unknown')),
  side_source TEXT NOT NULL,

  amount REAL,
  price REAL,
  premium_usd REAL,

  order_type TEXT CHECK (order_type IN ('limit', 'market') OR order_type IS NULL),
  time_in_force TEXT CHECK (time_in_force IN ('gtc', 'post_only', 'fok', 'ioc') OR time_in_force IS NULL),

  rfq_id TEXT,
  quote_id TEXT,
  tx_hash TEXT,
  tx_status TEXT,
  subaccount_id TEXT,
  wallet TEXT,

  created_at_ms INTEGER NOT NULL DEFAULT (unixepoch() * 1000),

  UNIQUE (source_endpoint, external_event_id)
);

CREATE TABLE IF NOT EXISTS derive_order_flow_legs (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES derive_order_flow_events(id) ON DELETE CASCADE,

  leg_index INTEGER NOT NULL,
  instrument_name TEXT NOT NULL,
  option_type TEXT NOT NULL CHECK (option_type IN ('call', 'put')),
  expiry TEXT NOT NULL,
  strike REAL NOT NULL,

  side TEXT NOT NULL CHECK (side IN ('buy', 'sell', 'unknown')),
  amount REAL NOT NULL,
  price REAL,
  premium_usd REAL,

  created_at_ms INTEGER NOT NULL DEFAULT (unixepoch() * 1000)
);

CREATE INDEX IF NOT EXISTS idx_order_flow_observed
ON derive_order_flow_events (observed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_order_flow_filters
ON derive_order_flow_events (execution_type, leg_structure, option_mix, observed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_order_flow_legs_event
ON derive_order_flow_legs (event_id, leg_index);
