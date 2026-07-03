import { useEffect, useMemo, useState } from 'react';
import { getBootstrap, getIvSmile, getOrderFlowEvents, getVolRegime } from './api/client';
import { ChartPanel } from './components/ChartPanel';
import { SelectControl, SegmentControl } from './components/Controls';
import { KpiStrip } from './components/KpiStrip';
import { MorphValue } from './components/MorphValue';
import { OrderFlowRail } from './components/OrderFlowRail';
import { SideNav, type AppRoute } from './components/SideNav';
import { TopBar } from './components/TopBar';
import { gexByExpiryOption, gexByStrikeOption, ivSmileOption, oiByExpiryOption, oiByStrikeOption, termStructureOption } from './charts/options';
import { useDashboardSocket } from './hooks/useDashboardSocket';
import { formatExpiry, formatPercent, formatTenorLabel, formatVol, formatVolChange } from './format';
import { hasEnoughVolHistory } from './display';
import { GreekStrategyPage, type GreekTab } from './pages/GreekStrategyPage';
import type { AtmTerm, DashboardBootstrap, ExpiryMetric, GexExpiryPoint, GexPoint, IvSmilePoint, OiStrikePoint, OrderFlowEvent, OrderFlowFilters, SkewTerm, VolRegime } from './types';
import './styles.css';

const DEFAULT_VOL_LOOKBACK_DAYS = 365;
const DEFAULT_ORDER_FLOW_FILTERS: OrderFlowFilters = {
  executionType: '',
  optionMix: '',
  side: '',
  orderType: '',
  timeInForce: '',
  minAmount: '',
  minPremiumUsd: '',
  wallet: '',
  subaccountId: '',
};

const GREEK_ROUTES: Partial<Record<AppRoute, GreekTab>> = {
  positionLookup: 'lookup',
  greekSimulator: 'greek',
  strategySimulator: 'strategy',
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>('market');
  const greekTab = GREEK_ROUTES[route];
  if (greekTab) {
    return (
      <main className="app-shell app-shell-greek">
        <SideNav route={route} onRouteChange={setRoute} />
        <GreekStrategyPage key={route} tab={greekTab} />
      </main>
    );
  }
  return <MarketDashboard route={route} onRouteChange={setRoute} />;
}

function MarketDashboard({
  route,
  onRouteChange,
}: {
  route: AppRoute;
  onRouteChange: (route: AppRoute) => void;
}) {
  const [data, setData] = useState<DashboardBootstrap | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [ivSmileExpiry, setIvSmileExpiry] = useState('');
  const [oiSide, setOiSide] = useState<'total' | 'call' | 'put'>('total');
  const [oiExpirySide, setOiExpirySide] = useState<'total' | 'call' | 'put'>('total');
  const [volTenor, setVolTenor] = useState('1M');
  const [ivSmile, setIvSmile] = useState<IvSmilePoint[]>([]);
  const [gexByStrike, setGexByStrike] = useState<GexPoint[]>([]);
  const [gexByExpiry, setGexByExpiry] = useState<GexExpiryPoint[]>([]);
  const [oiByStrike, setOiByStrike] = useState<OiStrikePoint[]>([]);
  const [volRegime, setVolRegime] = useState<VolRegime | null>(null);
  const [orderFlow, setOrderFlow] = useState<OrderFlowEvent[]>([]);
  const [orderFlowFilters, setOrderFlowFilters] = useState<OrderFlowFilters>(DEFAULT_ORDER_FLOW_FILTERS);
  const [orderFlowLoading, setOrderFlowLoading] = useState(false);
  const [updatingPanel, setUpdatingPanel] = useState<string | null>(null);

  const expiries = useMemo(() => data?.expiries.map((row) => row.expiry) ?? [], [data]);
  const effectiveOrderFlowFilters = useDebouncedValue(orderFlowFilters, 180);
  const orderFlowFilterKey = useMemo(() => orderFlowFiltersKey(effectiveOrderFlowFilters), [effectiveOrderFlowFilters]);

  useEffect(() => {
    const controller = new AbortController();
    setBootstrapError(null);
    getBootstrap(controller.signal)
      .then((payload) => {
        setData(payload);
        const expiry = payload.selectedExpiry ?? payload.expiries[0]?.expiry ?? '';
        setIvSmileExpiry(expiry);
        setIvSmile(payload.ivSmile);
        setGexByStrike(payload.gexByStrike);
        setGexByExpiry(payload.gexByExpiry ?? []);
        setOiByStrike(payload.oiByStrike);
        setVolRegime(payload.volRegime);
      })
      .catch((error: unknown) => {
        if (!isAbortError(error)) setBootstrapError('Dashboard data unavailable');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!ivSmileExpiry) return;
    const controller = new AbortController();
    let active = true;
    setUpdatingPanel('ivSmile');
    getIvSmile(ivSmileExpiry, controller.signal)
      .then((rows) => {
        if (active) setIvSmile(rows);
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) setIvSmile([]);
      })
      .finally(() => {
        if (active) setUpdatingPanel(null);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [ivSmileExpiry]);

  useEffect(() => {
    const controller = new AbortController();
    getVolRegime(volTenor, DEFAULT_VOL_LOOKBACK_DAYS, controller.signal)
      .then(setVolRegime)
      .catch((error: unknown) => {
        if (!isAbortError(error)) setVolRegime(null);
      });
    return () => controller.abort();
  }, [volTenor]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setOrderFlowLoading(true);
    getOrderFlowEvents(effectiveOrderFlowFilters, controller.signal)
      .then((rows) => {
        if (active) setOrderFlow(rows);
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) setOrderFlow([]);
      })
      .finally(() => {
        if (active) setOrderFlowLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [effectiveOrderFlowFilters, orderFlowFilterKey]);

  const socketSubscriptions = useMemo(
    () => [
      { panel: 'ivSmile', params: { expiry: ivSmileExpiry } },
      { panel: 'gexByStrike' },
      { panel: 'gexByExpiry' },
      { panel: 'oiByStrike' },
      { panel: 'volRegime', params: { tenor: volTenor, lookbackDays: DEFAULT_VOL_LOOKBACK_DAYS } },
      { panel: 'orderFlow', params: orderFlowSocketParams(effectiveOrderFlowFilters) },
    ],
    [effectiveOrderFlowFilters, ivSmileExpiry, orderFlowFilterKey, volTenor]
  );

  const socketStatus = useDashboardSocket(
    socketSubscriptions,
    (message) => {
      const payload = message.payload;
      if (payload.summary || payload.atmTerm || payload.skewFly || payload.snapshot || payload.expiries || payload.oiByExpiry) {
        setData((prev) => prev ? {
          ...prev,
          ...(payload.snapshot ? { snapshot: payload.snapshot as DashboardBootstrap['snapshot'] } : {}),
          ...(payload.summary ? { summary: payload.summary as DashboardBootstrap['summary'] } : {}),
          ...(payload.expiries ? { expiries: payload.expiries as DashboardBootstrap['expiries'] } : {}),
          ...(payload.atmTerm ? { atmTerm: payload.atmTerm as DashboardBootstrap['atmTerm'] } : {}),
          ...(payload.skewFly ? { skewFly: payload.skewFly as DashboardBootstrap['skewFly'] } : {}),
          ...(payload.oiByExpiry ? { oiByExpiry: payload.oiByExpiry as DashboardBootstrap['oiByExpiry'] } : {}),
        } : prev);
      }
      if (payload.ivSmile) setIvSmile(payload.ivSmile as IvSmilePoint[]);
      if (payload.gexByStrike) setGexByStrike(payload.gexByStrike as GexPoint[]);
      if (payload.gexByExpiry) setGexByExpiry(payload.gexByExpiry as GexExpiryPoint[]);
      if (payload.oiByStrike) setOiByStrike(payload.oiByStrike as OiStrikePoint[]);
      if (payload.volRegime) setVolRegime(payload.volRegime as VolRegime);
      if (payload.orderFlow) setOrderFlow(payload.orderFlow as OrderFlowEvent[]);
    }
  );

  const panelExpiries = expiries.length ? expiries : [''];
  const ivSmileMetric = findExpiry(data?.expiries, ivSmileExpiry);
  const showRank = hasEnoughVolHistory(volRegime?.sampleCount);
  const isLoading = !data && !bootstrapError;
  const hasBootstrapError = Boolean(bootstrapError);
  const spotPrice = data?.summary.spotPrice ?? null;
  const termOption = useMemo(() => termStructureOption(data?.atmTerm ?? []), [data?.atmTerm]);
  const ivSmileChartOption = useMemo(
    () => ivSmileOption(ivSmile, ivSmileExpiry, ivSmileMetric?.atmStrike ?? spotPrice),
    [ivSmile, ivSmileExpiry, ivSmileMetric?.atmStrike, spotPrice]
  );
  const gexByStrikeChartOption = useMemo(
    () => gexByStrikeOption(gexByStrike, spotPrice),
    [gexByStrike, spotPrice]
  );
  const gexByExpiryChartOption = useMemo(
    () => gexByExpiryOption(gexByExpiry, spotPrice),
    [gexByExpiry, spotPrice]
  );
  const oiByStrikeChartOption = useMemo(
    () => oiByStrikeOption(oiByStrike, oiSide, spotPrice),
    [oiByStrike, oiSide, spotPrice]
  );
  const oiByExpiryChartOption = useMemo(
    () => oiByExpiryOption(data?.oiByExpiry ?? [], oiExpirySide),
    [data?.oiByExpiry, oiExpirySide]
  );

  return (
    <main className="app-shell">
      <SideNav route={route} onRouteChange={onRouteChange} />
      <div className="dashboard-main">
        <TopBar snapshot={data?.snapshot ?? null} status={socketStatus} />
        <KpiStrip summary={data?.summary ?? null} volRegime={volRegime} />
        {bootstrapError && <section className="system-banner" role="status">{bootstrapError}</section>}
        <section className="vol-regime-strip">
          <div>
            <span className="strip-label">ATM IV {volRegime?.tenor ?? volTenor}</span>
            <MorphValue value={formatVol(volRegime?.currentAtmIv)} className="strip-value" />
          </div>
          {showRank && (
            <>
              <div>
                <span className="strip-label">IV Rank</span>
                <MorphValue value={formatPercent(volRegime?.ivRank, 0)} className="strip-value" />
              </div>
              <div>
                <span className="strip-label">IV Percentile</span>
                <MorphValue value={formatPercent(volRegime?.ivPercentile, 0)} className="strip-value" />
              </div>
            </>
          )}
          <div className="local-controls">
            <SegmentControl value={volTenor} options={['1W', '1M', '3M', '6M']} onChange={setVolTenor} label="Volatility tenor" />
          </div>
        </section>
        <section className="chart-grid">
          <ChartPanel
            className="panel-term"
            option={termOption}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && data.atmTerm.length === 0)}
            emptyLabel={hasBootstrapError ? 'Term structure unavailable' : 'No term structure data'}
          />
          <ChartPanel
            className="panel-smile"
            option={ivSmileChartOption}
            updating={updatingPanel === 'ivSmile'}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && ivSmile.length === 0)}
            emptyLabel={hasBootstrapError ? 'IV smile unavailable' : 'No IV smile data'}
            controls={<SelectControl value={ivSmileExpiry} options={panelExpiries} onChange={setIvSmileExpiry} label="Expiry" formatOption={formatExpiry} />}
          />
          <ChartPanel
            className="panel-gex-strike"
            option={gexByStrikeChartOption}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && gexByStrike.length === 0)}
            emptyLabel={hasBootstrapError ? 'GEX unavailable' : 'No GEX data'}
          />
          <ChartPanel
            className="panel-gex-expiry"
            option={gexByExpiryChartOption}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && gexByExpiry.length === 0)}
            emptyLabel={hasBootstrapError ? 'Expiry GEX unavailable' : 'No expiry GEX data'}
          />
          <ChartPanel
            className="panel-oi-strike"
            option={oiByStrikeChartOption}
            updating={updatingPanel === 'oiByStrike'}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && oiByStrike.length === 0)}
            emptyLabel={hasBootstrapError ? 'Strike OI unavailable' : 'No strike OI data'}
            controls={<SegmentControl value={oiSide} options={['total', 'call', 'put']} onChange={setOiSide} label="Strike OI side" />}
          />
          <ChartPanel
            className="panel-oi-expiry"
            option={oiByExpiryChartOption}
            loading={isLoading}
            empty={hasBootstrapError || Boolean(data && data.oiByExpiry.length === 0)}
            emptyLabel={hasBootstrapError ? 'Expiry OI unavailable' : 'No expiry OI data'}
            controls={<SegmentControl value={oiExpirySide} options={['total', 'call', 'put']} onChange={setOiExpirySide} label="Expiry OI side" />}
          />
          <AtmChangeTable rows={data?.atmTerm ?? []} loading={isLoading} />
          <SkewFlyTable title="25D RR" valueHeader="RR" rows={data?.skewFly ?? []} metric="skew25d" changeMetric="skew" loading={isLoading} />
          <SkewFlyTable title="25D Fly" valueHeader="Fly" rows={data?.skewFly ?? []} metric="fly25d" changeMetric="fly" loading={isLoading} />
        </section>
      </div>
      <OrderFlowRail
        events={orderFlow}
        filters={orderFlowFilters}
        loading={orderFlowLoading}
        onFiltersChange={(filters) => {
          setOrderFlowFilters(
            filters.executionType === 'ORDERBOOK_ORDER'
              ? filters
              : { ...filters, orderType: '', timeInForce: '' }
          );
        }}
      />
    </main>
  );
}

function orderFlowSocketParams(filters: OrderFlowFilters) {
  return Object.fromEntries(
    Object.entries(filters)
      .filter(([, value]) => value !== '')
      .map(([key, value]) => [key, value])
  );
}

function orderFlowFiltersKey(filters: OrderFlowFilters) {
  return [
    filters.executionType,
    filters.optionMix,
    filters.side,
    filters.orderType,
    filters.timeInForce,
    filters.minAmount,
    filters.minPremiumUsd,
    filters.wallet,
    filters.subaccountId,
  ].join('|');
}

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, value]);
  return debounced;
}

function AtmChangeTable({ rows, loading }: { rows: AtmTerm[]; loading: boolean }) {
  return (
    <section className="change-panel metric-table-panel panel-atm-change">
      <h2>ATM IV Change</h2>
      <table>
        <thead><tr><th>DTE</th><th>ATM IV</th><th>Chg-1D</th><th>Chg-1W</th><th>Chg-1M</th></tr></thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={5} className="empty-cell">{loading ? 'Loading term changes' : 'No ATM change data'}</td></tr>
          )}
          {rows.map((row) => (
            <tr key={row.tenor}>
              <td>{formatTenorLabel(row.tenor)}</td>
              <td>{formatVol(row.atmIv)}</td>
              <td>{formatVolChange(row.chg1d)}</td>
              <td>{formatVolChange(row.chg1w)}</td>
              <td>{formatVolChange(row.chg1m)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SkewFlyTable({
  title,
  valueHeader,
  rows,
  metric,
  changeMetric,
  loading,
}: {
  title: string;
  valueHeader: 'RR' | 'Fly';
  rows: SkewTerm[];
  metric: 'skew25d' | 'fly25d';
  changeMetric: 'skew' | 'fly';
  loading: boolean;
}) {
  const byTenor = new Map(rows.map((row) => [row.tenor, row]));
  const tableRows = ['1D', '1W', '1M', '3M', '6M', '1Y'];
  return (
    <section className="change-panel metric-table-panel panel-skew-fly">
      <h2>{title}</h2>
          <table>
            <thead><tr><th>DTE</th><th>{valueHeader}</th><th>Chg-1D</th><th>Chg-1W</th><th>Chg-1M</th></tr></thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr><td colSpan={5} className="empty-cell">Loading term data</td></tr>
              ) : tableRows.map((tenor) => {
                const row = byTenor.get(tenor);
                return (
                  <tr key={tenor}>
                    <td>{formatTenorLabel(tenor)}</td>
                    <td>{formatVol(row?.[metric])}</td>
                    <td>{formatVolChange(changeMetric === 'fly' ? row?.flyChg1d : row?.chg1d)}</td>
                    <td>{formatVolChange(changeMetric === 'fly' ? row?.flyChg1w : row?.chg1w)}</td>
                    <td>{formatVolChange(changeMetric === 'fly' ? row?.flyChg1m : row?.chg1m)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
  );
}

function findExpiry(rows: ExpiryMetric[] | undefined, expiry: string) {
  return rows?.find((row) => row.expiry === expiry);
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}
