import { greekCurveOption, payoffCurveOption } from '../charts/greeks';
import type { GreekCurveResponse, GreekMetric, PayoffCurveResponse } from '../types';
import { ChartPanel } from './ChartPanel';

const METRICS: GreekMetric[] = ['delta', 'gamma', 'vega', 'theta'];

export function GreekCurvePanel({
  curve,
  payoffCurve,
  metric,
  loading,
  error,
  onMetricChange,
}: {
  curve: GreekCurveResponse | null;
  payoffCurve?: PayoffCurveResponse | null;
  metric: GreekMetric;
  loading?: boolean;
  error?: string | null;
  onMetricChange: (metric: GreekMetric) => void;
}) {
  const points = curve?.points ?? [];
  const payoffPoints = payoffCurve?.points ?? [];
  const unavailable = curve?.unavailableInstruments ?? [];
  const payoffUnavailable = payoffCurve?.unavailableInstruments ?? [];
  const notice = error ?? (unavailable.length ? `${unavailable.length} instruments missing curve data` : null);
  const payoffNotice = error ?? (payoffUnavailable.length ? `${payoffUnavailable.length} instruments missing payoff data` : null);

  return (
    <div className="greek-curve-section">
      <ChartPanel
        className="greek-curve-panel"
        option={greekCurveOption(points, metric)}
        loading={loading}
        empty={!loading && points.length === 0}
        emptyLabel={error ?? 'No portfolio curve data'}
        notice={notice}
        controls={<GreekMetricControl value={metric} onChange={onMetricChange} />}
      />
      <ChartPanel
        className="greek-curve-panel payoff-curve-panel"
        option={payoffCurveOption(payoffPoints)}
        loading={loading}
        empty={!loading && payoffPoints.length === 0}
        emptyLabel={error ?? 'No payoff data'}
        notice={payoffNotice}
      />
    </div>
  );
}

function GreekMetricControl({
  value,
  onChange,
}: {
  value: GreekMetric;
  onChange: (metric: GreekMetric) => void;
}) {
  return (
    <div className="segment-control" role="group" aria-label="Greek metric">
      {METRICS.map((metric) => (
        <button
          key={metric}
          className={metric === value ? 'active' : ''}
          onClick={() => onChange(metric)}
          type="button"
          aria-pressed={metric === value}
        >
          {metricLabel(metric)}
        </button>
      ))}
    </div>
  );
}

function metricLabel(metric: GreekMetric) {
  if (metric === 'delta') return 'Delta';
  if (metric === 'gamma') return 'Gamma';
  if (metric === 'vega') return 'Vega';
  return 'Theta';
}
