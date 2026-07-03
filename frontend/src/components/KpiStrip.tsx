import { memo, useEffect, useRef, useState } from 'react';
import type { Summary, VolRegime } from '../types';
import { formatKpiDisplay, hasEnoughVolHistory, type KpiDisplay } from '../display';
import { MorphValue } from './MorphValue';

export const KpiStrip = memo(function KpiStrip({ summary, volRegime }: { summary: Summary | null; volRegime: VolRegime | null }) {
  const showRank = Boolean(hasEnoughVolHistory(volRegime?.sampleCount) && summary?.ivRank != null && summary?.ivPercentile != null);
  const items: KpiDisplay[] = [
    formatKpiDisplay('spotPrice', summary?.spotPrice),
    formatKpiDisplay('totalOptionOi', summary?.totalOptionOi),
    formatKpiDisplay('totalOptionVolume', summary?.totalOptionVolume),
    formatKpiDisplay('putCallVolumeRatio', summary?.putCallVolumeRatio),
    formatKpiDisplay('netGex', summary?.netGex),
    ...(showRank ? [formatKpiDisplay('ivRankPercentile', summary?.ivRank, summary?.ivPercentile)] : []),
  ];
  return (
    <section className="kpi-strip">
      {items.map(({ id, label, unit, value, raw, tone, flash }) => (
        <div className="kpi" data-tone={tone} key={id}>
          <div className="kpi-label-row">
            <span className="kpi-label">{label}</span>
            <span className="kpi-unit">{unit}</span>
          </div>
          <FlashValue value={value} raw={raw} flash={flash} />
        </div>
      ))}
    </section>
  );
});

function FlashValue({ value, raw, flash }: { value: string; raw: number | null | undefined; flash: KpiDisplay['flash'] }) {
  const previousRef = useRef<number | null>(null);
  const [tone, setTone] = useState<'up' | 'down' | 'neutral' | ''>('');

  useEffect(() => {
    if (raw == null || !Number.isFinite(raw)) {
      previousRef.current = null;
      return;
    }
    const previous = previousRef.current;
    previousRef.current = raw;
    if (previous == null || previous === raw) return;
    setTone(flash === 'neutral' ? 'neutral' : raw > previous ? 'up' : 'down');
    const timer = window.setTimeout(() => setTone(''), 520);
    return () => window.clearTimeout(timer);
  }, [flash, raw]);

  return <MorphValue value={value} className={['kpi-value', tone ? `pulse-${tone}` : ''].filter(Boolean).join(' ')} />;
}
