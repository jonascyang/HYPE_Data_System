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

CREATE INDEX IF NOT EXISTS idx_history_expiry_ts
ON derived_expiry_metrics (ts_ms, expiry_ts_ms);

CREATE INDEX IF NOT EXISTS idx_history_global_ts
ON derived_global_metrics (ts_ms);

CREATE INDEX IF NOT EXISTS idx_history_price_ts
ON hype_price_snapshots (ts_ms);

CREATE INDEX IF NOT EXISTS idx_history_atm_term_tenor_ts
ON derived_atm_term_metrics (tenor, ts_ms DESC);
