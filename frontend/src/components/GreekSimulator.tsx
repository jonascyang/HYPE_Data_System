import { useEffect, useMemo, useRef, useState } from 'react';
import { simulateGreek } from '../api/client';
import { formatCompact } from '../format';
import type { GreekMetric, GreekSimulationLeg, GreekSimulationResponse, OptionInstrumentChoice } from '../types';
import { SelectControl, SegmentControl } from './Controls';
import { GreekCurvePanel } from './GreekCurvePanel';
import { PortfolioGreekStrip } from './PortfolioGreekStrip';

const OPTION_TYPES: Array<'call' | 'put'> = ['call', 'put'];
const SIDES: Array<'buy' | 'sell'> = ['buy', 'sell'];

type GreekLeg = Required<Pick<GreekSimulationLeg, 'instrumentName' | 'expiry' | 'strike' | 'optionType' | 'side' | 'quantity'>> & {
  id: string;
  markPrice?: number | null;
};

export function GreekSimulator({
  options,
  optionsLoading,
  optionsError,
}: {
  options: OptionInstrumentChoice[];
  optionsLoading: boolean;
  optionsError: string | null;
}) {
  const [expiry, setExpiry] = useState('');
  const [strike, setStrike] = useState('');
  const [optionType, setOptionType] = useState<'call' | 'put'>('call');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [quantity, setQuantity] = useState('1');
  const [metric, setMetric] = useState<GreekMetric>('delta');
  const [greekLegs, setGreekLegs] = useState<GreekLeg[]>([]);
  const [result, setResult] = useState<GreekSimulationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const simulationControllerRef = useRef<AbortController | null>(null);
  const simulationRequestRef = useRef(0);
  const mountedRef = useRef(true);

  const expiries = useMemo(() => unique(options.map((option) => option.expiry)).sort(), [options]);
  const strikes = useMemo(() => unique(
    options
      .filter((option) => option.expiry === expiry && option.optionType === optionType)
      .map((option) => String(option.strike))
  ).sort((a, b) => Number(a) - Number(b)), [options, expiry, optionType]);

  useEffect(() => {
    if (!expiry && expiries[0]) setExpiry(expiries[0]);
    if (expiry && expiries.length && !expiries.includes(expiry)) setExpiry(expiries[0]);
  }, [expiries, expiry]);

  useEffect(() => {
    if (!strike && strikes[0]) setStrike(strikes[0]);
    if (strike && strikes.length && !strikes.includes(strike)) setStrike(strikes[0]);
  }, [strikes, strike]);

  useEffect(() => () => {
    mountedRef.current = false;
    simulationControllerRef.current?.abort();
  }, []);

  const selectedOption = options.find((option) =>
    option.expiry === expiry && option.optionType === optionType && option.strike === Number(strike)
  );

  const runSimulation = async (nextLegs = greekLegs) => {
    if (nextLegs.length === 0) {
      simulationControllerRef.current?.abort();
      setResult(null);
      setError(null);
      setLoading(false);
      return;
    }
    simulationControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = simulationRequestRef.current + 1;
    simulationRequestRef.current = requestId;
    simulationControllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const payload = await simulateGreek({
        legs: greekLegsPayload(nextLegs),
        metric: 'delta',
      }, controller.signal);
      if (!mountedRef.current || simulationRequestRef.current !== requestId) return;
      setResult(payload);
    } catch (error: unknown) {
      if (mountedRef.current && simulationRequestRef.current === requestId && !isAbortError(error)) {
        setResult(null);
        setError('Simulation unavailable');
      }
    } finally {
      if (mountedRef.current && simulationRequestRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  const addGreekLeg = () => {
    const nextLeg = buildGreekLeg({
      expiry,
      strike,
      optionType,
      side,
      quantity,
      selectedOption,
      currentCount: greekLegs.length,
    });
    if (!nextLeg) {
      setError('Enter expiry, strike, and quantity');
      return;
    }
    const nextLegs = [...greekLegs, nextLeg];
    setGreekLegs(nextLegs);
    void runSimulation(nextLegs);
  };

  const removeGreekLeg = (id: string) => {
    const nextLegs = greekLegs.filter((leg) => leg.id !== id);
    setGreekLegs(nextLegs);
    void runSimulation(nextLegs);
  };

  const changeMetric = (nextMetric: GreekMetric) => {
    setMetric(nextMetric);
  };

  const canAdd = Boolean(expiry && Number.isFinite(Number(strike)) && Number(quantity) > 0);

  return (
    <div className="simulator-stack">
      <section className="change-panel simulator-control-panel">
        <div className="panel-heading-row">
          <span role="status" aria-live="polite">{optionsLoading ? 'Loading options' : optionsError ?? `${options.length} instruments`}</span>
        </div>
        <div className="simulator-controls">
          <SelectControl value={expiry} options={expiries} onChange={setExpiry} label="Expiry" />
          {strikes.length ? (
            <SelectControl value={strike} options={strikes} onChange={setStrike} label="Strike" />
          ) : (
            <label className="field-control">
              <span>Strike</span>
              <input value={strike} inputMode="decimal" onChange={(event) => setStrike(event.target.value)} />
            </label>
          )}
          <SegmentControl value={optionType} options={OPTION_TYPES} onChange={setOptionType} label="Option type" />
          <SegmentControl value={side} options={SIDES} onChange={setSide} label="Side" />
          <label className="field-control">
            <span>Quantity</span>
            <input value={quantity} inputMode="decimal" onChange={(event) => setQuantity(event.target.value)} />
          </label>
          <button className="primary-action add-greek-leg-button" type="button" onClick={addGreekLeg} disabled={loading || !canAdd}>
            <span aria-hidden="true">+</span>
            <span>ADD</span>
          </button>
        </div>
        {error && <div className="panel-inline-error" role="alert">{error}</div>}
        <div className="greek-leg-list" aria-label="Added option legs">
          {greekLegs.length === 0 ? (
            <div className="greek-leg-empty">No options added</div>
          ) : greekLegs.map((leg, index) => (
            <div className="greek-leg-row" key={leg.id}>
              <span>{index + 1}</span>
              <span>{leg.expiry}</span>
              <span>{formatStrike(leg.strike)} {leg.optionType.toUpperCase()}</span>
              <span>{leg.side.toUpperCase()}</span>
              <span>Qty {formatCompact(leg.quantity, 4)}</span>
              <span>${formatCompact(estimatedPremium(leg), 4)}</span>
              <button type="button" aria-label={`Remove leg ${index + 1}`} onClick={() => removeGreekLeg(leg.id)}>×</button>
            </div>
          ))}
        </div>
      </section>
      <PortfolioGreekStrip summary={result?.greeks ?? null} premium={result?.premium ?? null} loading={loading} />
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

function greekLegsPayload(legs: GreekLeg[]): GreekSimulationLeg[] {
  return legs.map((leg) => ({
    instrumentName: leg.instrumentName,
    expiry: leg.expiry,
    strike: leg.strike,
    optionType: leg.optionType,
    side: leg.side,
    quantity: leg.quantity,
  }));
}

function buildGreekLeg({
  expiry,
  strike,
  optionType,
  side,
  quantity,
  selectedOption,
  currentCount,
}: {
  expiry: string;
  strike: string;
  optionType: 'call' | 'put';
  side: 'buy' | 'sell';
  quantity: string;
  selectedOption?: OptionInstrumentChoice;
  currentCount: number;
}): GreekLeg | null {
  const parsedStrike = Number(strike);
  const parsedQuantity = Number(quantity);
  if (!expiry || !Number.isFinite(parsedStrike) || !Number.isFinite(parsedQuantity) || parsedQuantity <= 0) return null;
  const normalizedExpiry = expiry.replace(/-/g, '');
  return {
    id: `${Date.now()}-${currentCount}-${normalizedExpiry}-${parsedStrike}-${optionType}`,
    instrumentName: selectedOption?.instrumentName ?? `HYPE-${normalizedExpiry}-${formatStrike(parsedStrike)}-${optionType === 'call' ? 'C' : 'P'}`,
    expiry: normalizedExpiry,
    strike: parsedStrike,
    optionType,
    side,
    quantity: parsedQuantity,
    markPrice: selectedOption?.markPrice ?? null,
  };
}

function estimatedPremium(leg: GreekLeg) {
  if (leg.markPrice == null) return null;
  return leg.markPrice * leg.quantity * (leg.side === 'sell' ? 1 : -1);
}

function formatStrike(strike: number) {
  return Number.isInteger(strike) ? String(strike) : String(strike);
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}
