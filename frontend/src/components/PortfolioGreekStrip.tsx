import type { PortfolioGreekSummary } from '../types';
import { formatCompact } from '../format';
import { MorphValue } from './MorphValue';

export function PortfolioGreekStrip({
  summary,
  premium,
  loading,
}: {
  summary: PortfolioGreekSummary | null;
  premium?: number | null;
  loading?: boolean;
}) {
  const items: Array<[string, number | null | undefined, ('usd' | 'number')?]> = [
    ['Premium', premium, 'usd'],
    ['Total Delta', summary?.totalDelta],
    ['Total Gamma', summary?.totalGamma],
    ['Total Vega', summary?.totalVega],
    ['Total Theta', summary?.totalTheta],
  ];
  return (
    <section className="kpi-strip greek-kpi-strip" aria-busy={loading ? 'true' : undefined}>
      {items.map(([label, rawValue, format = 'number']) => (
        <div className="kpi" data-tone={toneForGreek(rawValue)} key={label}>
          <div className="kpi-label">{label}</div>
          <MorphValue value={formatGreek(rawValue, loading, format)} className={loading ? 'kpi-value is-loading' : 'kpi-value'} />
        </div>
      ))}
    </section>
  );
}

function formatGreek(value: number | null | undefined, loading?: boolean, format: 'usd' | 'number' = 'number') {
  if (loading) return 'Loading';
  const formatted = formatCompact(value, 4);
  return format === 'usd' ? `$${formatted}` : formatted;
}

function toneForGreek(value: number | null | undefined) {
  if (value == null || Math.abs(value) < 0.0000001) return 'flat';
  return value > 0 ? 'positive' : 'negative';
}
