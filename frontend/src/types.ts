export type NullableNumber = number | null;

export type Summary = {
  spotPrice: NullableNumber;
  totalOptionOi: NullableNumber;
  totalOptionVolume: NullableNumber;
  putCallVolumeRatio: NullableNumber;
  netGex: NullableNumber;
  absGex: NullableNumber;
  vrp7d: NullableNumber;
  vrp30d: NullableNumber;
  atmIv: Record<string, NullableNumber>;
  ivRank: NullableNumber;
  ivPercentile: NullableNumber;
  volRegimeTenor: string | null;
  volRegimeLookbackDays: number | null;
};

export type Snapshot = {
  latestTsMs: number | null;
  snapshotLabel: string | null;
  generatedAt: string | null;
  source: string | null;
};

export type ExpiryMetric = {
  expiry: string;
  dte: NullableNumber;
  atmIv: NullableNumber;
  atmStrike: NullableNumber;
  call25dIv: NullableNumber;
  put25dIv: NullableNumber;
  skew25d: NullableNumber;
  fly25d: NullableNumber;
  totalOi: number;
  callOi: number;
  putOi: number;
  totalVolume: number;
  callVolume: number;
  putVolume: number;
  maxPain: NullableNumber;
  netGex: number;
  absGex: number;
  tradablePoints: number;
  modelPoints: number;
};

export type AtmTerm = {
  tenor: string;
  atmIv: NullableNumber;
  chg1d: NullableNumber;
  chg1w: NullableNumber;
  chg1m: NullableNumber;
  method?: string;
  leftExpiry?: string | null;
  rightExpiry?: string | null;
};

export type SkewTerm = {
  tenor: string;
  skew25d: NullableNumber;
  fly25d: NullableNumber;
  chg1d: NullableNumber;
  chg1w: NullableNumber;
  chg1m: NullableNumber;
  flyChg1d?: NullableNumber;
  flyChg1w?: NullableNumber;
  flyChg1m?: NullableNumber;
};

export type IvSmilePoint = {
  strike: number;
  callIv: NullableNumber;
  putIv: NullableNumber;
  callDelta: NullableNumber;
  putDelta: NullableNumber;
  callGamma: NullableNumber;
  putGamma: NullableNumber;
  callVega: NullableNumber;
  putVega: NullableNumber;
  callTheta: NullableNumber;
  putTheta: NullableNumber;
  callRho: NullableNumber;
  putRho: NullableNumber;
  callPremium: NullableNumber;
  putPremium: NullableNumber;
  callOi: number;
  putOi: number;
};

export type GexPoint = {
  strike: number;
  callGex: number;
  putGex: number;
  netGex: number;
  absGex: number;
};

export type GexExpiryPoint = GexPoint & {
  expiry: string;
};

export type OiPoint = {
  strike: number;
  callOi: number;
  putOi: number;
  totalOi: number;
};

export type OiStrikePoint = OiPoint & {
  expiry: string;
};

export type OiExpiry = {
  expiry: string;
  totalOi: number;
  callOi: number;
  putOi: number;
  totalVolume: number;
  callVolume: number;
  putVolume: number;
};

export type VrpPoint = {
  tsMs: number;
  period: string;
  rv: NullableNumber;
  atmIv: NullableNumber;
  vrp: NullableNumber;
};

export type VolRegime = {
  tenor: string;
  lookbackDays: number;
  latestTsMs: number | null;
  currentAtmIv: NullableNumber;
  minAtmIv: NullableNumber;
  maxAtmIv: NullableNumber;
  ivRank: NullableNumber;
  ivPercentile: NullableNumber;
  sampleCount: number;
};

export type OrderFlowLeg = {
  legIndex: number;
  instrumentName: string;
  optionType: 'call' | 'put';
  expiry: string;
  strike: number;
  side: 'buy' | 'sell' | 'unknown';
  amount: number;
  price: NullableNumber;
  premiumUsd: NullableNumber;
};

export type OrderFlowEvent = {
  id: string;
  sourceEndpoint: string;
  externalEventId: string;
  eventKind: string;
  executionType: 'ORDERBOOK_ORDER' | 'RFQ';
  legStructure: 'SINGLE_LEG' | 'MULTI_LEG';
  optionMix: 'CALL' | 'PUT' | 'BOTH';
  tradeTsMs: NullableNumber;
  observedAtMs: number;
  currency: string;
  side: 'buy' | 'sell' | 'unknown';
  sideSource: string;
  amount: NullableNumber;
  price: NullableNumber;
  premiumUsd: NullableNumber;
  orderType: 'limit' | 'market' | null;
  timeInForce: 'gtc' | 'post_only' | 'fok' | 'ioc' | null;
  rfqId: string | null;
  quoteId: string | null;
  txHash: string | null;
  txStatus: string | null;
  subaccountId: string | null;
  wallet: string | null;
  legs: OrderFlowLeg[];
};

export type OrderFlowFilters = {
  executionType: string;
  optionMix: string;
  side: string;
  orderType: string;
  timeInForce: string;
  minAmount: string;
  minPremiumUsd: string;
  wallet: string;
  subaccountId: string;
};

export type DashboardBootstrap = {
  snapshot: Snapshot;
  summary: Summary;
  selectedExpiry: string | null;
  expiries: ExpiryMetric[];
  atmTerm: AtmTerm[];
  skewFly: SkewTerm[];
  ivSmile: IvSmilePoint[];
  gexByStrike: GexPoint[];
  gexByExpiry: GexExpiryPoint[];
  oiByStrike: OiStrikePoint[];
  oiByExpiry: OiExpiry[];
  vrpHistory: VrpPoint[];
  volRegime: VolRegime;
};

export type SocketStatus = 'connecting' | 'live' | 'updating' | 'stale' | 'reconnecting' | 'offline';

export type GreekMetric = 'delta' | 'gamma' | 'vega' | 'theta';

export type WalletSubaccount = {
  id: string;
  label?: string | null;
  balance?: NullableNumber;
  equity?: NullableNumber;
};

export type WalletPosition = {
  id?: string | null;
  instrumentName: string;
  instrumentType?: string | null;
  underlying?: string | null;
  optionType?: 'call' | 'put' | string | null;
  expiry?: string | null;
  strike?: NullableNumber;
  side?: 'buy' | 'sell' | 'long' | 'short' | string | null;
  amount?: NullableNumber;
  notionalUsd?: NullableNumber;
  markPrice?: NullableNumber;
  entryPrice?: NullableNumber;
  premiumUsd?: NullableNumber;
  pnl?: NullableNumber;
  txHash?: string | null;
  subaccountId?: string | null;
  delta?: NullableNumber;
  gamma?: NullableNumber;
  vega?: NullableNumber;
  theta?: NullableNumber;
};

export type WalletTrade = {
  id?: string | null;
  instrumentName?: string | null;
  instrumentType?: string | null;
  optionType?: 'call' | 'put' | string | null;
  expiry?: string | null;
  strike?: NullableNumber;
  side?: 'buy' | 'sell' | string | null;
  amount?: NullableNumber;
  price?: NullableNumber;
  premiumUsd?: NullableNumber;
  underlying?: string | null;
  txHash?: string | null;
  timestampMs?: number | null;
};

export type WalletLookupResponse = {
  inputAddress: string;
  wallet: string | null;
  scwOwner: string | null;
  ensName: string | null;
  subaccounts: WalletSubaccount[];
  positions: WalletPosition[];
  trades: WalletTrade[];
  currencies: unknown[] | Record<string, unknown>;
  source: string | { type?: string | null; url?: string | null } | null;
};

export type PortfolioGreekSummary = {
  totalDelta: NullableNumber;
  totalGamma: NullableNumber;
  totalVega: NullableNumber;
  totalTheta: NullableNumber;
  positionCount?: number;
};

export type GreekCurvePoint = {
  shock: number;
  shockPct?: number;
  spotPrice?: NullableNumber;
  value?: NullableNumber;
  delta?: NullableNumber;
  gamma?: NullableNumber;
  vega?: NullableNumber;
  theta?: NullableNumber;
  totalDelta?: NullableNumber;
  totalGamma?: NullableNumber;
  totalVega?: NullableNumber;
  totalTheta?: NullableNumber;
};

export type GreekScenarioRow = GreekCurvePoint & {
  label?: string;
};

export type GreekCurveResponse = {
  metric: GreekMetric;
  points: GreekCurvePoint[];
  scenarioRows: GreekScenarioRow[];
  unavailableInstruments?: string[];
};

export type PayoffCurveResponse = {
  points: GreekCurvePoint[];
  scenarioRows: GreekScenarioRow[];
  unavailableInstruments?: string[];
};

export type PortfolioGreeksRequest = {
  positions: WalletPosition[];
  metric: GreekMetric;
};

export type PortfolioGreeksResponse = {
  summary: PortfolioGreekSummary;
  curve: GreekCurveResponse | null;
  curves?: Partial<Record<GreekMetric, GreekCurveResponse | null>>;
  payoffCurve?: PayoffCurveResponse | null;
  unavailableInstruments?: string[];
};

export type OptionInstrumentChoice = {
  instrumentName: string;
  expiry: string;
  strike: number;
  optionType: 'call' | 'put';
  markPrice?: NullableNumber;
  bidPrice?: NullableNumber;
  askPrice?: NullableNumber;
  spotPrice?: NullableNumber;
};

export type GreekStrategyOptionsResponse = {
  options: OptionInstrumentChoice[];
  expiries?: string[];
  strikes?: number[];
};

export type GreekSimulationLeg = {
  instrumentName?: string;
  expiry?: string;
  strike?: number;
  optionType?: 'call' | 'put';
  side: 'buy' | 'sell';
  quantity: number;
};

export type GreekSimulationRequest = {
  instrumentName?: string;
  expiry?: string;
  strike?: number;
  optionType?: 'call' | 'put';
  side?: 'buy' | 'sell';
  quantity?: number;
  metric: GreekMetric;
  legs?: GreekSimulationLeg[];
};

export type StrategyName =
  | 'long_call'
  | 'long_put'
  | 'vertical_call_spread'
  | 'vertical_put_spread'
  | 'straddle'
  | 'strangle'
  | 'risk_reversal'
  | 'butterfly'
  | 'iron_condor'
  | 'calendar_spread'
  | 'custom';

export type StrategyPreviewRequest = {
  strategy: StrategyName;
  expiry: string;
  strikes: number[];
  quantity: number;
  side?: 'buy' | 'sell';
  metric: GreekMetric;
  legs?: GreekSimulationLeg[];
};

export type StrategyLegPreview = {
  instrumentName: string;
  optionType: 'call' | 'put' | string;
  expiry: string;
  strike: number;
  side: 'buy' | 'sell' | string;
  quantity: number;
  markPrice?: NullableNumber;
  premium?: NullableNumber;
};

export type GreekSimulationResponse = {
  premium: NullableNumber;
  greeks: PortfolioGreekSummary;
  curve: GreekCurveResponse | null;
  curves?: Partial<Record<GreekMetric, GreekCurveResponse | null>>;
  payoffCurve?: PayoffCurveResponse | null;
  legs?: StrategyLegPreview[];
};

export type StrategyPreviewResponse = {
  premium: NullableNumber;
  greeks: PortfolioGreekSummary;
  curve: GreekCurveResponse | null;
  curves?: Partial<Record<GreekMetric, GreekCurveResponse | null>>;
  payoffCurve?: PayoffCurveResponse | null;
  legs: StrategyLegPreview[];
};
