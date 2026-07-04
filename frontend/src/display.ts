import { formatCompact, formatContracts, formatGex, formatNumber, formatPercent, formatRatio, formatVol } from './format';

export const MIN_RANK_SAMPLES = 30;
export const MULTI_SERIES_TOOLTIP_LIMIT = 6;

export type MetricTone = 'neutral' | 'positive' | 'negative';

export type KpiMetricId = 'spotPrice' | 'totalOptionOi' | 'totalOptionVolume' | 'putCallVolumeRatio' | 'netGex' | 'ivRankPercentile';

export type KpiDisplay = {
  id: KpiMetricId;
  label: string;
  unit: string;
  value: string;
  change?: string;
  changeTone?: 'up' | 'down' | 'neutral';
  raw: number | null | undefined;
  tone: MetricTone;
  flash: 'directional' | 'neutral';
};

export const formatKpiDisplay = (
  id: KpiMetricId,
  value: number | null | undefined,
  secondaryValue?: number | null | undefined
): KpiDisplay => {
  if (id === 'spotPrice') {
    return {
      id,
      label: 'HYPE Spot',
      unit: 'USD',
      value: value == null ? '-' : `$${formatNumber(value, 2)}`,
      change: secondaryValue == null ? undefined : `24H ${secondaryValue > 0 ? '+' : ''}${formatPercent(secondaryValue, 2)}`,
      changeTone: secondaryValue == null || secondaryValue === 0 ? 'neutral' : secondaryValue > 0 ? 'up' : 'down',
      raw: value,
      tone: 'neutral',
      flash: 'directional',
    };
  }
  if (id === 'totalOptionOi') {
    return {
      id,
      label: 'Total Option OI',
      unit: 'Contracts',
      value: formatCompact(value),
      raw: value,
      tone: 'neutral',
      flash: 'neutral',
    };
  }
  if (id === 'totalOptionVolume') {
    return {
      id,
      label: 'Total Option Volume',
      unit: 'Contracts',
      value: formatCompact(value),
      raw: value,
      tone: 'neutral',
      flash: 'neutral',
    };
  }
  if (id === 'putCallVolumeRatio') {
    return {
      id,
      label: 'Put / Call Volume',
      unit: 'Ratio',
      value: formatRatio(value),
      raw: value,
      tone: 'neutral',
      flash: 'neutral',
    };
  }
  if (id === 'netGex') {
    return {
      id,
      label: 'Net GEX',
      unit: 'Gamma Exposure',
      value: formatCompact(value),
      raw: value,
      tone: value == null || value === 0 ? 'neutral' : value > 0 ? 'positive' : 'negative',
      flash: 'directional',
    };
  }
  return {
    id,
    label: 'IV Rank / Percentile',
    unit: 'History',
    value: `${formatNumber(value, 0)}% / ${formatNumber(secondaryValue, 0)}%`,
    raw: value,
    tone: 'neutral',
    flash: 'neutral',
  };
};

export const formatChartValue = (unit: 'contracts' | 'gex' | 'iv' | 'ratio' | 'usd', value: number | null | undefined) => {
  if (unit === 'contracts') return formatContracts(value);
  if (unit === 'gex') return formatGex(value);
  if (unit === 'iv') return formatVol(value == null ? value : value / 100);
  if (unit === 'ratio') return formatRatio(value);
  if (unit === 'usd') return value == null ? '-' : `$${formatCompact(value)}`;
  return value == null ? '-' : formatCompact(value);
};

export const expiryColorIndex = (expiry: string | null | undefined) => {
  if (!expiry) return 0;
  let hash = 0;
  for (let index = 0; index < expiry.length; index += 1) {
    hash = (hash * 31 + expiry.charCodeAt(index)) >>> 0;
  }
  return hash % 12;
};

export const sortExpiries = (expiries: string[]) =>
  Array.from(new Set(expiries)).sort((left, right) => left.localeCompare(right));

export const hasEnoughVolHistory = (sampleCount: number | null | undefined) =>
  typeof sampleCount === 'number' && sampleCount >= MIN_RANK_SAMPLES;
