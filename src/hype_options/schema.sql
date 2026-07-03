CREATE TABLE IF NOT EXISTS derive_instruments (
  instrument_name TEXT PRIMARY KEY,
  instrument_type TEXT NOT NULL,
  base_currency TEXT NOT NULL,
  quote_currency TEXT NOT NULL,
  expiry_ts_ms INTEGER NOT NULL,
  expiry_yyyymmdd TEXT NOT NULL,
  strike REAL NOT NULL,
  option_type TEXT NOT NULL,
  is_active INTEGER NOT NULL,
  activation_ts_ms INTEGER,
  deactivation_ts_ms INTEGER,
  tick_size REAL,
  min_amount REAL,
  max_amount REAL,
  amount_step REAL,
  maker_fee_rate REAL,
  taker_fee_rate REAL,
  base_asset_address TEXT,
  base_asset_sub_id TEXT,
  raw_json TEXT,
  first_seen_ms INTEGER NOT NULL,
  last_seen_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS derive_ticker_snapshots (
  ts_ms INTEGER NOT NULL,
  source_ts_ms INTEGER,
  instrument_name TEXT NOT NULL,
  expiry_ts_ms INTEGER NOT NULL,
  expiry_yyyymmdd TEXT NOT NULL,
  strike REAL NOT NULL,
  option_type TEXT NOT NULL,

  index_price REAL,
  mark_price REAL,
  forward_price REAL,

  bid_price REAL,
  ask_price REAL,
  bid_size REAL,
  ask_size REAL,
  mid_price REAL,
  spread_abs REAL,
  spread_bps REAL,

  mark_iv REAL,
  bid_iv REAL,
  ask_iv REAL,
  delta REAL,
  gamma REAL,
  vega REAL,
  theta REAL,
  rho REAL,
  rate REAL,

  open_interest REAL,
  volume REAL,
  trade_count INTEGER,
  high_price REAL,
  low_price REAL,

  surface_quality TEXT NOT NULL,
  raw_payload_id TEXT,

  PRIMARY KEY (ts_ms, instrument_name)
);

CREATE TABLE IF NOT EXISTS derive_raw_ticker_payloads (
  id TEXT PRIMARY KEY,
  ts_ms INTEGER NOT NULL,
  expiry_yyyymmdd TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  payload_bytes INTEGER,
  payload_sha256 TEXT NOT NULL,
  payload_zstd BLOB,
  expires_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS hype_price_snapshots (
  ts_ms INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  index_name TEXT NOT NULL,
  price REAL NOT NULL,
  raw_json TEXT
);

CREATE TABLE IF NOT EXISTS derived_expiry_metrics (
  ts_ms INTEGER NOT NULL,
  expiry_ts_ms INTEGER NOT NULL,
  expiry_yyyymmdd TEXT NOT NULL,
  dte_days REAL,

  atm_iv REAL,
  atm_strike REAL,
  call_25d_iv REAL,
  put_25d_iv REAL,
  skew_25d REAL,
  fly_25d REAL,

  total_oi REAL,
  call_oi REAL,
  put_oi REAL,
  put_call_oi_ratio REAL,

  total_volume REAL,
  call_volume REAL,
  put_volume REAL,
  put_call_volume_ratio REAL,

  max_pain_price REAL,
  total_gex REAL,
  net_gex REAL,
  abs_gex REAL,

  model_point_count INTEGER,
  tradable_point_count INTEGER,

  PRIMARY KEY (ts_ms, expiry_ts_ms)
);

CREATE TABLE IF NOT EXISTS derived_gex_by_strike (
  ts_ms INTEGER NOT NULL,
  expiry_ts_ms INTEGER NOT NULL,
  strike REAL NOT NULL,
  call_gex REAL,
  put_gex REAL,
  net_gex REAL,
  abs_gex REAL,
  call_oi REAL,
  put_oi REAL,

  PRIMARY KEY (ts_ms, expiry_ts_ms, strike)
);

CREATE TABLE IF NOT EXISTS derived_global_metrics (
  ts_ms INTEGER PRIMARY KEY,
  spot_price REAL,

  rv_1d REAL,
  rv_7d REAL,
  rv_14d REAL,
  rv_30d REAL,

  atm_iv_7d REAL,
  atm_iv_30d REAL,
  atm_iv_60d REAL,
  atm_iv_90d REAL,

  vrp_7d REAL,
  vrp_30d REAL,

  total_option_oi REAL,
  total_option_volume REAL,
  call_volume REAL,
  put_volume REAL,
  put_call_volume_ratio REAL,

  total_gex REAL,
  net_gex REAL,
  abs_gex REAL
);

CREATE TABLE IF NOT EXISTS derived_atm_term_metrics (
  ts_ms INTEGER NOT NULL,
  tenor TEXT NOT NULL,
  target_dte_days REAL NOT NULL,
  atm_iv REAL,
  method TEXT NOT NULL,

  left_expiry_yyyymmdd TEXT,
  left_dte_days REAL,
  left_atm_iv REAL,

  right_expiry_yyyymmdd TEXT,
  right_dte_days REAL,
  right_atm_iv REAL,

  PRIMARY KEY (ts_ms, tenor)
);

CREATE TABLE IF NOT EXISTS collection_runs (
  id TEXT PRIMARY KEY,
  started_ms INTEGER NOT NULL,
  finished_ms INTEGER,
  endpoint TEXT NOT NULL,
  expiry_yyyymmdd TEXT,
  status TEXT NOT NULL,
  row_count INTEGER,
  error_message TEXT,
  payload_sha256 TEXT
);

CREATE TABLE IF NOT EXISTS derive_option_instruments (
  instrument_name TEXT PRIMARY KEY,
  currency TEXT NOT NULL DEFAULT 'HYPE',
  option_type TEXT NOT NULL CHECK (option_type IN ('call', 'put')),
  expiry TEXT NOT NULL,
  strike REAL NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  updated_at_ms INTEGER NOT NULL
);

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

CREATE INDEX IF NOT EXISTS idx_ticker_instrument_ts
ON derive_ticker_snapshots (instrument_name, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_ticker_ts
ON derive_ticker_snapshots (ts_ms);

CREATE INDEX IF NOT EXISTS idx_ticker_expiry_ts
ON derive_ticker_snapshots (expiry_ts_ms, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_ticker_surface
ON derive_ticker_snapshots (surface_quality, expiry_ts_ms, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_raw_payload_expires
ON derive_raw_ticker_payloads (expires_at_ms);

CREATE INDEX IF NOT EXISTS idx_gex_ts
ON derived_gex_by_strike (ts_ms);

CREATE INDEX IF NOT EXISTS idx_gex_expiry
ON derived_gex_by_strike (expiry_ts_ms, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_atm_term_tenor_ts
ON derived_atm_term_metrics (tenor, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_collection_runs_started
ON collection_runs (started_ms);

CREATE INDEX IF NOT EXISTS idx_order_flow_observed
ON derive_order_flow_events (observed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_order_flow_filters
ON derive_order_flow_events (execution_type, leg_structure, option_mix, observed_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_order_flow_legs_event
ON derive_order_flow_legs (event_id, leg_index);
