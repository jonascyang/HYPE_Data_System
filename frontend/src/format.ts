const numberFormat = (digits: number) =>
  new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

const trimZeros = (value: string) => value.replace(/\.0+$|(\.\d*[1-9])0+$/, '$1');

export const formatNumber = (value: number | null | undefined, digits = 2) =>
  value == null ? '-' : numberFormat(digits).format(value);

export const formatRatio = (value: number | null | undefined) =>
  value == null ? '-' : numberFormat(2).format(value);

export const formatCompact = (value: number | null | undefined, digits = 2) => {
  if (value == null) return '-';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}${trimZeros((abs / 1_000_000_000).toFixed(digits))}B`;
  if (abs >= 1_000_000) return `${sign}${trimZeros((abs / 1_000_000).toFixed(digits))}M`;
  if (abs >= 1_000) return `${sign}${trimZeros((abs / 1_000).toFixed(digits))}K`;
  return `${sign}${trimZeros(abs.toFixed(abs >= 100 ? 0 : digits))}`;
};

export const formatContracts = (value: number | null | undefined) =>
  value == null ? '-' : `${formatCompact(value)} contracts`;

export const formatGex = (value: number | null | undefined) =>
  value == null ? '-' : `${formatCompact(value)} GEX`;

export const formatPercent = (value: number | null | undefined, digits = 0) =>
  value == null ? '-' : `${numberFormat(digits).format(value)}%`;

export const formatVol = (value: number | null | undefined, digits = 1) =>
  value == null ? '-' : `${numberFormat(digits).format(value * 100)}%`;

export const formatVolChange = (value: number | null | undefined) => {
  if (value == null) return '-';
  const formatted = formatVol(Math.abs(value), 1);
  return value > 0 ? `+${formatted}` : value < 0 ? `-${formatted}` : formatted;
};

export const formatStrike = (value: number | string | null | undefined) => {
  if (value == null || value === '') return '-';
  const numeric = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numeric) ? trimZeros(numeric.toFixed(2)) : String(value);
};

export const formatExpiry = (value: string | null | undefined) => {
  if (!value) return '-';
  const compact = value.replace(/\D/g, '');
  if (compact.length === 8) return `${compact.slice(0, 4)}/${compact.slice(4, 6)}/${compact.slice(6, 8)}`;
  return value.replace(/-/g, '/');
};

export const formatTenorLabel = (value: string | null | undefined) => {
  if (value === '1D') return '1 Day';
  if (value === '1W') return '1 Week';
  if (value === '1M') return '1 Month';
  if (value === '3M') return '3 Month';
  if (value === '6M') return '6 Month';
  if (value === '1Y') return '1 Year';
  return value || '-';
};

export const formatDateTime = (tsMs: number | null | undefined) => {
  if (tsMs == null) return 'Waiting';
  const date = new Date(tsMs);
  if (Number.isNaN(date.getTime())) return 'Waiting';
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const min = String(date.getMinutes()).padStart(2, '0');
  return `${yyyy}/${mm}/${dd} ${hh}:${min}`;
};
