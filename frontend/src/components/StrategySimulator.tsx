import { useEffect, useMemo, useRef, useState } from 'react';
import { previewStrategy } from '../api/client';
import { formatCompact, formatExpiry, formatNumber, formatStrike } from '../format';
import type { GreekMetric, GreekSimulationLeg, OptionInstrumentChoice, StrategyLegPreview, StrategyName, StrategyPreviewResponse } from '../types';
import { SelectControl, SegmentControl } from './Controls';
import { GreekCurvePanel } from './GreekCurvePanel';
import { PortfolioGreekStrip } from './PortfolioGreekStrip';

const STRATEGIES: StrategyName[] = [
  'long_call',
  'long_put',
  'vertical_call_spread',
  'vertical_put_spread',
  'straddle',
  'strangle',
  'risk_reversal',
  'butterfly',
  'iron_condor',
  'calendar_spread',
  'custom',
];
const SIDES: Array<'buy' | 'sell'> = ['buy', 'sell'];
const OPTION_TYPES: Array<'call' | 'put'> = ['call', 'put'];

type StrategyBuilderLeg = {
  id: string;
  side: 'buy' | 'sell';
  optionType: 'call' | 'put';
  expiry: string;
  strike: string;
  quantity: string;
  strikeSlot: number;
  expiryOffset: number;
};

type StrategyLegSpec = Pick<StrategyBuilderLeg, 'side' | 'optionType' | 'strikeSlot' | 'expiryOffset'> & {
  quantity?: string;
};

const STRATEGY_LEG_TEMPLATES: Record<StrategyName, StrategyLegSpec[]> = {
  long_call: [{ side: 'buy', optionType: 'call', strikeSlot: 0, expiryOffset: 0 }],
  long_put: [{ side: 'buy', optionType: 'put', strikeSlot: 0, expiryOffset: 0 }],
  vertical_call_spread: [
    { side: 'buy', optionType: 'call', strikeSlot: -1, expiryOffset: 0 },
    { side: 'sell', optionType: 'call', strikeSlot: 1, expiryOffset: 0 },
  ],
  vertical_put_spread: [
    { side: 'buy', optionType: 'put', strikeSlot: 1, expiryOffset: 0 },
    { side: 'sell', optionType: 'put', strikeSlot: -1, expiryOffset: 0 },
  ],
  straddle: [
    { side: 'buy', optionType: 'call', strikeSlot: 0, expiryOffset: 0 },
    { side: 'buy', optionType: 'put', strikeSlot: 0, expiryOffset: 0 },
  ],
  strangle: [
    { side: 'buy', optionType: 'put', strikeSlot: -1, expiryOffset: 0 },
    { side: 'buy', optionType: 'call', strikeSlot: 1, expiryOffset: 0 },
  ],
  risk_reversal: [
    { side: 'sell', optionType: 'put', strikeSlot: -1, expiryOffset: 0 },
    { side: 'buy', optionType: 'call', strikeSlot: 1, expiryOffset: 0 },
  ],
  butterfly: [
    { side: 'buy', optionType: 'call', strikeSlot: -1, expiryOffset: 0 },
    { side: 'sell', optionType: 'call', strikeSlot: 0, expiryOffset: 0, quantity: '2' },
    { side: 'buy', optionType: 'call', strikeSlot: 1, expiryOffset: 0 },
  ],
  iron_condor: [
    { side: 'buy', optionType: 'put', strikeSlot: -2, expiryOffset: 0 },
    { side: 'sell', optionType: 'put', strikeSlot: -1, expiryOffset: 0 },
    { side: 'sell', optionType: 'call', strikeSlot: 1, expiryOffset: 0 },
    { side: 'buy', optionType: 'call', strikeSlot: 2, expiryOffset: 0 },
  ],
  calendar_spread: [
    { side: 'sell', optionType: 'call', strikeSlot: 0, expiryOffset: 0 },
    { side: 'buy', optionType: 'call', strikeSlot: 0, expiryOffset: 1 },
  ],
  custom: [{ side: 'buy', optionType: 'call', strikeSlot: 0, expiryOffset: 0 }],
};

export function StrategySimulator({
  options,
  optionsLoading,
  optionsError,
}: {
  options: OptionInstrumentChoice[];
  optionsLoading: boolean;
  optionsError: string | null;
}) {
  const [strategy, setStrategy] = useState<StrategyName>('long_call');
  const [strategyLegs, setStrategyLegs] = useState<StrategyBuilderLeg[]>([]);
  const [metric, setMetric] = useState<GreekMetric>('delta');
  const [result, setResult] = useState<StrategyPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previewControllerRef = useRef<AbortController | null>(null);
  const previewRequestRef = useRef(0);
  const mountedRef = useRef(true);

  const expiries = useMemo(() => unique(options.map((option) => option.expiry)).sort(), [options]);
  const strikesByExpiry = useMemo(() => {
    const grouped = new Map<string, string[]>();
    for (const option of options) {
      const strikes = grouped.get(option.expiry) ?? [];
      strikes.push(formatStrike(option.strike));
      grouped.set(option.expiry, strikes);
    }
    for (const [expiry, strikes] of grouped) {
      grouped.set(expiry, unique(strikes).sort((a, b) => Number(a) - Number(b)));
    }
    return grouped;
  }, [options]);

  useEffect(() => () => {
    mountedRef.current = false;
    previewControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    setStrategyLegs((current) => {
      if (current.length === 0) return createStrategyLegs(strategy, expiries, strikesByExpiry);
      return current.map((leg) => fillLegDefaults(leg, expiries, strikesByExpiry));
    });
  }, [expiries, strikesByExpiry, strategy]);

  const changeStrategy = (nextStrategy: string) => {
    const typedStrategy = nextStrategy as StrategyName;
    setStrategy(typedStrategy);
    setStrategyLegs(createStrategyLegs(typedStrategy, expiries, strikesByExpiry));
    setResult(null);
    setError(null);
  };

  const updateStrategyLeg = (id: string, patch: Partial<StrategyBuilderLeg>) => {
    setStrategyLegs((current) => current.map((leg) => (leg.id === id ? { ...leg, ...patch } : leg)));
    setResult(null);
  };

  const addStrategyLeg = () => {
    setStrategyLegs((current) => [
      ...current,
      createStrategyLeg(
        { side: 'buy', optionType: 'call', strikeSlot: 0, expiryOffset: 0 },
        current.length,
        expiries,
        strikesByExpiry,
      ),
    ]);
    setResult(null);
  };

  const removeStrategyLeg = (id: string) => {
    setStrategyLegs((current) => current.filter((leg) => leg.id !== id));
    setResult(null);
  };

  const runPreview = async () => {
    const payloadLegs = strategyLegsPayload(strategyLegs);
    if (payloadLegs.length === 0 || payloadLegs.some((leg) => !leg.expiry || !leg.strike || !Number.isFinite(leg.quantity) || leg.quantity <= 0)) {
      setError('Enter expiry, strike, and quantity for every leg');
      return;
    }
    previewControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = previewRequestRef.current + 1;
    previewRequestRef.current = requestId;
    previewControllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const payload = await previewStrategy({
        strategy: 'custom',
        expiry: payloadLegs[0].expiry ?? '',
        strikes: [],
        quantity: 1,
        metric: 'delta',
        legs: payloadLegs,
      }, controller.signal);
      if (!mountedRef.current || previewRequestRef.current !== requestId) return;
      setResult(payload);
    } catch (error: unknown) {
      if (mountedRef.current && previewRequestRef.current === requestId && !isAbortError(error)) {
        setResult(null);
        setError('Strategy preview unavailable');
      }
    } finally {
      if (mountedRef.current && previewRequestRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  const changeMetric = (nextMetric: GreekMetric) => {
    setMetric(nextMetric);
  };

  return (
    <div className="simulator-stack">
      <section className="change-panel simulator-control-panel strategy-builder-panel">
        <div className="panel-heading-row">
          <h2>Strategy Simulator</h2>
          <span role="status" aria-live="polite">{optionsLoading ? 'Loading options' : optionsError ?? `${options.length} instruments`}</span>
        </div>
        <div className="simulator-controls strategy-builder-controls">
          <SelectControl value={strategy} options={STRATEGIES} onChange={changeStrategy} label="Strategy" formatOption={strategyLabel} />
          <button className="primary-action add-strategy-leg-button" type="button" onClick={addStrategyLeg}>
            <span aria-hidden="true">+</span>
            <span>Add Leg</span>
          </button>
          <button className="primary-action" type="button" onClick={() => void runPreview()} disabled={loading || strategyLegs.length === 0}>
            {loading ? 'Previewing' : 'Preview'}
          </button>
          <div className="strategy-leg-builder">
            {strategyLegs.map((leg, index) => (
              <StrategyLegEditor
                key={leg.id}
                leg={leg}
                index={index}
                expiries={expiries}
                strikes={strikesByExpiry.get(leg.expiry) ?? []}
                strikesByExpiry={strikesByExpiry}
                canRemove={strategyLegs.length > 1}
                onChange={(patch) => updateStrategyLeg(leg.id, patch)}
                onRemove={() => removeStrategyLeg(leg.id)}
              />
            ))}
          </div>
        </div>
        {error && <div className="panel-inline-error" role="alert">{error}</div>}
      </section>
      <PortfolioGreekStrip summary={result?.greeks ?? null} premium={result?.premium ?? null} loading={loading} />
      <StrategyLegTable legs={result?.legs ?? []} loading={loading} />
      <GreekCurvePanel
        curve={result?.curves?.[metric] ?? result?.curve ?? null}
        payoffCurve={result?.payoffCurve ?? null}
        metric={metric}
        loading={loading}
        error={error}
        onMetricChange={changeMetric}
      />
    </div>
  );
}

function StrategyLegEditor({
  leg,
  index,
  expiries,
  strikes,
  strikesByExpiry,
  canRemove,
  onChange,
  onRemove,
}: {
  leg: StrategyBuilderLeg;
  index: number;
  expiries: string[];
  strikes: string[];
  strikesByExpiry: Map<string, string[]>;
  canRemove: boolean;
  onChange: (patch: Partial<StrategyBuilderLeg>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="strategy-leg-editor-row">
      <span className="strategy-leg-index">{index + 1}</span>
      <SegmentControl value={leg.side} options={SIDES} onChange={(value) => onChange({ side: value })} label="Side" />
      <SegmentControl value={leg.optionType} options={OPTION_TYPES} onChange={(value) => onChange({ optionType: value })} label="Type" />
      <SelectControl value={leg.expiry} options={expiries} onChange={(expiry) => onChange({ expiry, strike: defaultStrike(strikesByExpiry.get(expiry) ?? [], leg.strikeSlot) })} label="Expiry" formatOption={formatExpiry} />
      <SelectControl value={leg.strike} options={strikes} onChange={(strike) => onChange({ strike })} label="Strike" formatOption={formatStrike} />
      <label className="field-control strategy-quantity-control">
        <span>Quantity</span>
        <input value={leg.quantity} inputMode="decimal" onChange={(event) => onChange({ quantity: event.target.value })} />
      </label>
      <button className="strategy-leg-remove" type="button" onClick={onRemove} disabled={!canRemove} aria-label={`Remove leg ${index + 1}`}>
        ×
      </button>
    </div>
  );
}

function StrategyLegTable({ legs, loading }: { legs: StrategyLegPreview[]; loading: boolean }) {
  return (
    <section className="change-panel strategy-leg-panel">
      <h2>Preview Legs</h2>
      <div className="table-scroll">
        <table>
        <thead><tr><th>Instrument</th><th>Type</th><th>Expiry</th><th>Strike</th><th>Side</th><th>Qty</th><th>Mark</th><th>Premium</th></tr></thead>
        <tbody>
          {legs.length === 0 && (
            <tr><td colSpan={8} className="empty-cell">{loading ? 'Loading strategy legs' : 'No strategy preview'}</td></tr>
          )}
          {legs.map((leg, index) => (
            <tr key={`${leg.instrumentName}-${index}`}>
              <td>{leg.instrumentName}</td>
              <td>{leg.optionType}</td>
              <td>{formatExpiry(leg.expiry)}</td>
              <td>{formatStrike(leg.strike)}</td>
              <td>{leg.side}</td>
              <td>{formatCompact(leg.quantity, 2)}</td>
              <td>{formatNumber(leg.markPrice, 4)}</td>
              <td>${formatCompact(leg.premium, 4)}</td>
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </section>
  );
}

function createStrategyLegs(strategy: StrategyName, expiries: string[], strikesByExpiry: Map<string, string[]>) {
  return STRATEGY_LEG_TEMPLATES[strategy].map((spec, index) => createStrategyLeg(spec, index, expiries, strikesByExpiry));
}

function createStrategyLeg(spec: StrategyLegSpec, index: number, expiries: string[], strikesByExpiry: Map<string, string[]>): StrategyBuilderLeg {
  const expiry = defaultExpiry(expiries, spec.expiryOffset);
  return {
    id: `${Date.now()}-${index}-${spec.side}-${spec.optionType}-${spec.expiryOffset}-${spec.strikeSlot}`,
    side: spec.side,
    optionType: spec.optionType,
    expiry,
    strike: defaultStrike(strikesByExpiry.get(expiry) ?? [], spec.strikeSlot),
    quantity: spec.quantity ?? '1',
    strikeSlot: spec.strikeSlot,
    expiryOffset: spec.expiryOffset,
  };
}

function fillLegDefaults(leg: StrategyBuilderLeg, expiries: string[], strikesByExpiry: Map<string, string[]>): StrategyBuilderLeg {
  const expiry = leg.expiry || defaultExpiry(expiries, leg.expiryOffset);
  const strikes = strikesByExpiry.get(expiry) ?? [];
  return {
    ...leg,
    expiry,
    strike: leg.strike || defaultStrike(strikes, leg.strikeSlot),
  };
}

function strategyLegsPayload(legs: StrategyBuilderLeg[]): GreekSimulationLeg[] {
  return legs.map((leg) => {
    const strike = Number(leg.strike);
    const expiry = leg.expiry.replace(/-/g, '');
    return {
      instrumentName: `HYPE-${expiry}-${formatStrike(strike)}-${leg.optionType === 'call' ? 'C' : 'P'}`,
      expiry,
      strike,
      optionType: leg.optionType,
      side: leg.side,
      quantity: Number(leg.quantity),
    };
  });
}

function defaultExpiry(expiries: string[], offset: number) {
  return expiries[Math.min(Math.max(offset, 0), Math.max(expiries.length - 1, 0))] ?? '';
}

function defaultStrike(strikes: string[], slot: number) {
  if (strikes.length === 0) return '';
  const center = Math.floor((strikes.length - 1) / 2);
  const index = Math.min(Math.max(center + slot, 0), strikes.length - 1);
  return strikes[index];
}

function strategyLabel(value: string) {
  return value.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}
