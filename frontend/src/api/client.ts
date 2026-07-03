import type {
  DashboardBootstrap,
  GexExpiryPoint,
  GexPoint,
  GreekSimulationRequest,
  GreekSimulationResponse,
  GreekStrategyOptionsResponse,
  IvSmilePoint,
  OiExpiry,
  OiStrikePoint,
  OrderFlowEvent,
  OrderFlowFilters,
  PortfolioGreeksRequest,
  PortfolioGreeksResponse,
  StrategyPreviewRequest,
  StrategyPreviewResponse,
  VolRegime,
  WalletLookupResponse,
} from '../types';

const json = async <T>(url: string, signal?: AbortSignal): Promise<T> => {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
};

const postJson = async <T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
};

export const getBootstrap = (signal?: AbortSignal) => json<DashboardBootstrap>('/api/options/dashboard/bootstrap', signal);
export const getIvSmile = (expiry: string, signal?: AbortSignal) => json<IvSmilePoint[]>(`/api/options/iv-smile?expiry=${encodeURIComponent(expiry)}`, signal);
export const getGexByStrike = (signal?: AbortSignal) => json<GexPoint[]>('/api/options/gex-by-strike', signal);
export const getGexByExpiry = (signal?: AbortSignal) => json<GexExpiryPoint[]>('/api/options/gex-by-expiry', signal);
export const getOiByStrike = (signal?: AbortSignal) => json<OiStrikePoint[]>('/api/options/oi-by-strike', signal);
export const getOiByExpiry = (signal?: AbortSignal) => json<OiExpiry[]>('/api/options/oi-by-expiry', signal);
export const getVolRegime = (tenor: string, lookbackDays: number, signal?: AbortSignal) =>
  json<VolRegime>(`/api/options/vol-regime?tenor=${encodeURIComponent(tenor)}&lookbackDays=${lookbackDays}`, signal);

export const getOrderFlowEvents = (filters: OrderFlowFilters, signal?: AbortSignal) => {
  const params = new URLSearchParams();
  const mappings: Array<[keyof OrderFlowFilters, string]> = [
    ['executionType', 'executionType'],
    ['optionMix', 'optionMix'],
    ['side', 'side'],
    ['orderType', 'orderType'],
    ['timeInForce', 'timeInForce'],
    ['minAmount', 'minAmount'],
    ['minPremiumUsd', 'minPremiumUsd'],
    ['wallet', 'wallet'],
    ['subaccountId', 'subaccountId'],
  ];
  mappings.forEach(([key, param]) => {
    const value = filters[key];
    if (value) params.set(param, value);
  });
  params.set('limit', '100');
  return json<OrderFlowEvent[]>(`/api/order-flow/events?${params.toString()}`, signal);
};

export const getWalletLookup = (address: string, signal?: AbortSignal) =>
  json<WalletLookupResponse>(`/api/greek-strategy/wallet?address=${encodeURIComponent(address)}`, signal);

export const getPortfolioGreeks = (request: PortfolioGreeksRequest, signal?: AbortSignal) =>
  postJson<PortfolioGreeksResponse>('/api/greek-strategy/portfolio-greeks', request, signal);

export const getGreekStrategyOptions = (signal?: AbortSignal) =>
  json<GreekStrategyOptionsResponse>('/api/greek-strategy/options', signal);

export const simulateGreek = (request: GreekSimulationRequest, signal?: AbortSignal) =>
  postJson<GreekSimulationResponse>('/api/greek-strategy/simulate', request, signal);

export const previewStrategy = (request: StrategyPreviewRequest, signal?: AbortSignal) =>
  postJson<StrategyPreviewResponse>('/api/greek-strategy/strategy-preview', request, signal);
