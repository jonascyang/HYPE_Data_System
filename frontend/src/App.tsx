import { lazy, memo, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Options } from 'highcharts';
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
import { markPerf, measurePerf } from './perf';
import type { GreekTab } from './pages/GreekStrategyPage';
import type { AtmTerm, DashboardBootstrap, ExpiryMetric, GexExpiryPoint, GexPoint, IvSmilePoint, NullableNumber, OiExpiry, OiStrikePoint, OrderFlowEvent, OrderFlowFilters, SkewTerm, Snapshot, Summary, VolRegime } from './types';
import './styles.css';

const loadGreekStrategyPage = () => import('./pages/GreekStrategyPage');
const GreekStrategyPage = lazy(() =>
  loadGreekStrategyPage().then((module) => ({ default: module.GreekStrategyPage }))
);

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
const EMPTY_PANEL_EXPIRIES = [''];

const GREEK_ROUTES: Partial<Record<AppRoute, GreekTab>> = {
  positionLookup: 'lookup',
  greekSimulator: 'greek',
  strategySimulator: 'strategy',
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>('market');
  const handleRouteChange = useCallback((nextRoute: AppRoute) => {
    const start = markPerf();
    setRoute(nextRoute);
    window.requestAnimationFrame(() => {
      measurePerf('interaction.route_switch', start, { route: nextRoute });
    });
  }, []);

  useEffect(() => {
    if (route !== 'market') return;
    const preload = () => {
      void loadGreekStrategyPage();
    };
    const idleWindow = window as Window & {
      requestIdleCallback?: (callback: IdleRequestCallback, options?: IdleRequestOptions) => number;
      cancelIdleCallback?: (handle: number) => void;
    };
    if (idleWindow.requestIdleCallback) {
      const idleId = idleWindow.requestIdleCallback(preload, { timeout: 2200 });
      return () => idleWindow.cancelIdleCallback?.(idleId);
    }
    const timer = window.setTimeout(preload, 1200);
    return () => window.clearTimeout(timer);
  }, [route]);

  const greekTab = GREEK_ROUTES[route];
  if (greekTab) {
    return (
      <main className="app-shell app-shell-greek">
        <SideNav route={route} onRouteChange={handleRouteChange} />
        <Suspense fallback={<GreekRouteFallback />}>
          <GreekStrategyPage key={route} tab={greekTab} />
        </Suspense>
      </main>
    );
  }
  return <MarketDashboard route={route} onRouteChange={handleRouteChange} />;
}

function GreekRouteFallback() {
  return (
    <section className="route-loading-panel" aria-live="polite">
      <span>Loading</span>
    </section>
  );
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
  const [volRegimeByTenor, setVolRegimeByTenor] = useState<Record<string, VolRegime>>({});
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
        setVolRegimeByTenor(payload.volRegimeByTenor ?? {});
        setVolRegime(payload.volRegimeByTenor?.[volTenor] ?? payload.volRegime);
      })
      .catch((error: unknown) => {
        if (!isAbortError(error)) setBootstrapError('Dashboard data unavailable');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!ivSmileExpiry) return;
    const cachedRows = data?.ivSmileByExpiry?.[ivSmileExpiry];
    if (cachedRows) {
      const start = markPerf();
      setIvSmile((previous) => mergeIvSmilePoints(previous, cachedRows));
      setUpdatingPanel(null);
      requestAnimationFrame(() => measurePerf('interaction.expiry_change.cache', start, { expiry: ivSmileExpiry }));
      return;
    }
    const controller = new AbortController();
    let active = true;
    const fetchStart = markPerf();
    setUpdatingPanel('ivSmile');
    getIvSmile(ivSmileExpiry, controller.signal)
      .then((rows) => {
        if (active) setIvSmile((previous) => mergeIvSmilePoints(previous, rows));
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) setIvSmile([]);
      })
      .finally(() => {
        if (active) {
          setUpdatingPanel(null);
          measurePerf('interaction.expiry_change.fetch', fetchStart, { expiry: ivSmileExpiry });
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [data?.ivSmileByExpiry, ivSmileExpiry]);

  useEffect(() => {
    const cached = volRegimeByTenor[volTenor] ?? data?.volRegimeByTenor?.[volTenor];
    if (cached) {
      const start = markPerf();
      setVolRegime((previous) => mergeNullableFlatObject(previous, cached));
      requestAnimationFrame(() => measurePerf('interaction.tenor_change.cache', start, { tenor: volTenor }));
      return;
    }
    const controller = new AbortController();
    const fetchStart = markPerf();
    getVolRegime(volTenor, DEFAULT_VOL_LOOKBACK_DAYS, controller.signal)
      .then((row) => {
        setVolRegimeByTenor((previous) => (
          previous[volTenor] && sameFlatObject(previous[volTenor], row)
            ? previous
            : { ...previous, [volTenor]: row }
        ));
        setVolRegime((previous) => mergeNullableFlatObject(previous, row));
        measurePerf('interaction.tenor_change.fetch', fetchStart, { tenor: volTenor });
      })
      .catch((error: unknown) => {
        if (!isAbortError(error)) setVolRegime(null);
      });
    return () => controller.abort();
  }, [data?.volRegimeByTenor, volRegimeByTenor, volTenor]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const fetchStart = markPerf();
    setOrderFlowLoading(true);
    getOrderFlowEvents(effectiveOrderFlowFilters, controller.signal)
      .then((rows) => {
        if (active) setOrderFlow((previous) => mergeOrderFlowEvents(previous, rows));
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) setOrderFlow([]);
      })
      .finally(() => {
        if (active) {
          setOrderFlowLoading(false);
          measurePerf('interaction.order_flow_filter.fetch', fetchStart, { filters: orderFlowFilterKey });
        }
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
      const mergeStart = markPerf();
      const payload = message.payload;
      if (payload.summary || payload.atmTerm || payload.skewFly || payload.snapshot || payload.expiries || payload.oiByExpiry) {
        setData((prev) => prev ? mergeDashboardPayload(prev, payload) : prev);
      }
      if (payload.ivSmile) setIvSmile((previous) => mergeIvSmilePoints(previous, payload.ivSmile as IvSmilePoint[]));
      if (payload.gexByStrike) setGexByStrike((previous) => mergeStrikeRows(previous, payload.gexByStrike as GexPoint[]));
      if (payload.gexByExpiry) setGexByExpiry((previous) => mergeExpiryStrikeRows(previous, payload.gexByExpiry as GexExpiryPoint[]));
      if (payload.oiByStrike) setOiByStrike((previous) => mergeOiStrikeRows(previous, payload.oiByStrike as OiStrikePoint[]));
      if (payload.volRegime) {
        const nextVolRegime = payload.volRegime as VolRegime;
        setVolRegimeByTenor((previous) => (
          previous[nextVolRegime.tenor] && sameFlatObject(previous[nextVolRegime.tenor], nextVolRegime)
            ? previous
            : { ...previous, [nextVolRegime.tenor]: nextVolRegime }
        ));
        setVolRegime((previous) => mergeNullableFlatObject(previous, nextVolRegime));
      }
      if (payload.orderFlow) setOrderFlow((previous) => mergeOrderFlowEvents(previous, payload.orderFlow as OrderFlowEvent[]));
      measurePerf('dashboard.merge', mergeStart, { panels: Object.keys(payload).join(',') });
    }
  );

  const panelExpiries = expiries.length ? expiries : EMPTY_PANEL_EXPIRIES;
  const ivSmileMetric = findExpiry(data?.expiries, ivSmileExpiry);
  const showRank = hasEnoughVolHistory(volRegime?.sampleCount);
  const isLoading = !data && !bootstrapError;
  const hasBootstrapError = Boolean(bootstrapError);
  const spotPrice = data?.summary.spotPrice ?? null;
  const termOption = useMemo(
    () => measureOptionBuild('chart.option.term_structure', () => termStructureOption(data?.atmTerm ?? [])),
    [data?.atmTerm]
  );
  const ivSmileChartOption = useMemo(
    () => measureOptionBuild(
      'chart.option.iv_smile',
      () => ivSmileOption(ivSmile, ivSmileExpiry, ivSmileMetric?.atmStrike ?? spotPrice),
    ),
    [ivSmile, ivSmileExpiry, ivSmileMetric?.atmStrike, spotPrice]
  );
  const gexByStrikeChartOption = useMemo(
    () => measureOptionBuild('chart.option.gex_by_strike', () => gexByStrikeOption(gexByStrike, spotPrice)),
    [gexByStrike, spotPrice]
  );
  const gexByExpiryChartOption = useMemo(
    () => measureOptionBuild('chart.option.gex_by_expiry', () => gexByExpiryOption(gexByExpiry, spotPrice)),
    [gexByExpiry, spotPrice]
  );
  const oiByStrikeChartOption = useMemo(
    () => measureOptionBuild('chart.option.oi_by_strike', () => oiByStrikeOption(oiByStrike, oiSide, spotPrice)),
    [oiByStrike, oiSide, spotPrice]
  );
  const oiByExpiryChartOption = useMemo(
    () => measureOptionBuild('chart.option.oi_by_expiry', () => oiByExpiryOption(data?.oiByExpiry ?? [], oiExpirySide)),
    [data?.oiByExpiry, oiExpirySide]
  );
  const handleIvSmileExpiryChange = useCallback((expiry: string) => {
    const start = markPerf();
    setIvSmileExpiry(expiry);
    requestAnimationFrame(() => measurePerf('interaction.expiry_select', start, { expiry }));
  }, []);
  const handleOiSideChange = useCallback((side: 'total' | 'call' | 'put') => {
    const start = markPerf();
    setOiSide(side);
    requestAnimationFrame(() => measurePerf('interaction.oi_strike_side', start, { side }));
  }, []);
  const handleOiExpirySideChange = useCallback((side: 'total' | 'call' | 'put') => {
    const start = markPerf();
    setOiExpirySide(side);
    requestAnimationFrame(() => measurePerf('interaction.oi_expiry_side', start, { side }));
  }, []);
  const handleVolTenorChange = useCallback((tenor: string) => {
    const start = markPerf();
    setVolTenor(tenor);
    requestAnimationFrame(() => measurePerf('interaction.tenor_select', start, { tenor }));
  }, []);
  const ivSmileControls = useMemo(
    () => <SelectControl value={ivSmileExpiry} options={panelExpiries} onChange={handleIvSmileExpiryChange} label="Expiry" formatOption={formatExpiry} />,
    [handleIvSmileExpiryChange, ivSmileExpiry, panelExpiries]
  );
  const oiStrikeControls = useMemo(
    () => <SegmentControl value={oiSide} options={['total', 'call', 'put']} onChange={handleOiSideChange} label="Strike OI side" />,
    [handleOiSideChange, oiSide]
  );
  const oiExpiryControls = useMemo(
    () => <SegmentControl value={oiExpirySide} options={['total', 'call', 'put']} onChange={handleOiExpirySideChange} label="Expiry OI side" />,
    [handleOiExpirySideChange, oiExpirySide]
  );
  const handleOrderFlowFiltersChange = useCallback((filters: OrderFlowFilters) => {
    const start = markPerf();
    setOrderFlowFilters(
      filters.executionType === 'ORDERBOOK_ORDER'
        ? filters
        : { ...filters, orderType: '', timeInForce: '' }
    );
    requestAnimationFrame(() => measurePerf('interaction.order_flow_filter_input', start));
  }, []);

  return (
    <main className="app-shell">
      <SideNav route={route} onRouteChange={onRouteChange} />
      <div className="dashboard-main">
        <TopBar snapshot={data?.snapshot ?? null} status={socketStatus} />
        <KpiStrip summary={data?.summary ?? null} volRegime={volRegime} />
        {bootstrapError && <section className="system-banner" role="status">{bootstrapError}</section>}
        <VolRegimeStrip
          volRegime={volRegime}
          volTenor={volTenor}
          showRank={showRank}
          onVolTenorChange={handleVolTenorChange}
        />
        <DashboardChartGrid
          data={data}
          isLoading={isLoading}
          hasBootstrapError={hasBootstrapError}
          updatingPanel={updatingPanel}
          termOption={termOption}
          ivSmileChartOption={ivSmileChartOption}
          gexByStrikeChartOption={gexByStrikeChartOption}
          gexByExpiryChartOption={gexByExpiryChartOption}
          oiByStrikeChartOption={oiByStrikeChartOption}
          oiByExpiryChartOption={oiByExpiryChartOption}
          ivSmile={ivSmile}
          gexByStrike={gexByStrike}
          gexByExpiry={gexByExpiry}
          oiByStrike={oiByStrike}
          ivSmileControls={ivSmileControls}
          oiStrikeControls={oiStrikeControls}
          oiExpiryControls={oiExpiryControls}
        />
      </div>
      <OrderFlowRail
        events={orderFlow}
        filters={orderFlowFilters}
        loading={orderFlowLoading}
        onFiltersChange={handleOrderFlowFiltersChange}
      />
    </main>
  );
}

const VolRegimeStrip = memo(function VolRegimeStrip({
  volRegime,
  volTenor,
  showRank,
  onVolTenorChange,
}: {
  volRegime: VolRegime | null;
  volTenor: string;
  showRank: boolean;
  onVolTenorChange: (tenor: string) => void;
}) {
  return (
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
        <SegmentControl value={volTenor} options={['1W', '1M', '3M', '6M']} onChange={onVolTenorChange} label="Volatility tenor" />
      </div>
    </section>
  );
});

const DashboardChartGrid = memo(function DashboardChartGrid({
  data,
  isLoading,
  hasBootstrapError,
  updatingPanel,
  termOption,
  ivSmileChartOption,
  gexByStrikeChartOption,
  gexByExpiryChartOption,
  oiByStrikeChartOption,
  oiByExpiryChartOption,
  ivSmile,
  gexByStrike,
  gexByExpiry,
  oiByStrike,
  ivSmileControls,
  oiStrikeControls,
  oiExpiryControls,
}: {
  data: DashboardBootstrap | null;
  isLoading: boolean;
  hasBootstrapError: boolean;
  updatingPanel: string | null;
  termOption: Options;
  ivSmileChartOption: Options;
  gexByStrikeChartOption: Options;
  gexByExpiryChartOption: Options;
  oiByStrikeChartOption: Options;
  oiByExpiryChartOption: Options;
  ivSmile: IvSmilePoint[];
  gexByStrike: GexPoint[];
  gexByExpiry: GexExpiryPoint[];
  oiByStrike: OiStrikePoint[];
  ivSmileControls: ReactNode;
  oiStrikeControls: ReactNode;
  oiExpiryControls: ReactNode;
}) {
  return (
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
        controls={ivSmileControls}
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
        controls={oiStrikeControls}
      />
      <ChartPanel
        className="panel-oi-expiry"
        option={oiByExpiryChartOption}
        loading={isLoading}
        empty={hasBootstrapError || Boolean(data && data.oiByExpiry.length === 0)}
        emptyLabel={hasBootstrapError ? 'Expiry OI unavailable' : 'No expiry OI data'}
        controls={oiExpiryControls}
      />
      <AtmChangeTable rows={data?.atmTerm ?? []} loading={isLoading} />
      <SkewFlyTable title="25D RR" valueHeader="RR" rows={data?.skewFly ?? []} metric="skew25d" changeMetric="skew" loading={isLoading} />
      <SkewFlyTable title="25D Fly" valueHeader="Fly" rows={data?.skewFly ?? []} metric="fly25d" changeMetric="fly" loading={isLoading} />
    </section>
  );
});

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

function mergeDashboardPayload(previous: DashboardBootstrap, payload: Record<string, unknown>) {
  const updates: Partial<DashboardBootstrap> = {};

  const setIfChanged = <K extends keyof DashboardBootstrap>(key: K, value: DashboardBootstrap[K]) => {
    if (value !== previous[key]) updates[key] = value;
  };

  if (payload.snapshot) {
    setIfChanged('snapshot', mergeFlatObject(previous.snapshot, payload.snapshot as Snapshot));
  }
  if (payload.summary) {
    setIfChanged('summary', mergeSummary(previous.summary, payload.summary as Partial<Summary>));
  }
  if (payload.expiries) {
    setIfChanged('expiries', mergeExpiryMetrics(previous.expiries, payload.expiries as ExpiryMetric[]));
  }
  if (payload.atmTerm) {
    setIfChanged('atmTerm', mergeAtmTerms(previous.atmTerm, payload.atmTerm as AtmTerm[]));
  }
  if (payload.skewFly) {
    setIfChanged('skewFly', mergeSkewTerms(previous.skewFly, payload.skewFly as SkewTerm[]));
  }
  if (payload.oiByExpiry) {
    setIfChanged('oiByExpiry', mergeOiExpiries(previous.oiByExpiry, payload.oiByExpiry as OiExpiry[]));
  }
  if (payload.ivSmileByExpiry) {
    setIfChanged('ivSmileByExpiry', payload.ivSmileByExpiry as Record<string, IvSmilePoint[]>);
  }
  if (payload.volRegimeByTenor) {
    setIfChanged('volRegimeByTenor', payload.volRegimeByTenor as Record<string, VolRegime>);
  }
  if (payload.snapshotVersion) {
    setIfChanged('snapshotVersion', payload.snapshotVersion as string | number);
  }
  if (payload.panelVersions) {
    setIfChanged('panelVersions', payload.panelVersions as Record<string, string | number>);
  }

  return Object.keys(updates).length === 0 ? previous : { ...previous, ...updates };
}

function mergeIvSmilePoints(previous: IvSmilePoint[], next: IvSmilePoint[]) {
  return mergeRowsByKey(previous, next, (row) => row.strike);
}

function mergeStrikeRows<T extends { strike: number }>(previous: T[], next: T[]) {
  return mergeRowsByKey(previous, next, (row) => row.strike);
}

function mergeExpiryStrikeRows<T extends { expiry: string; strike: number }>(previous: T[], next: T[]) {
  return mergeRowsByKey(previous, next, (row) => `${row.expiry}:${row.strike}`);
}

function mergeOiStrikeRows(previous: OiStrikePoint[], next: OiStrikePoint[]) {
  return mergeExpiryStrikeRows(previous, next);
}

function mergeExpiryMetrics(previous: ExpiryMetric[], next: ExpiryMetric[]) {
  return mergeRowsByKey(previous, next, (row) => row.expiry);
}

function mergeAtmTerms(previous: AtmTerm[], next: AtmTerm[]) {
  return mergeRowsByKey(previous, next, (row) => row.tenor);
}

function mergeSkewTerms(previous: SkewTerm[], next: SkewTerm[]) {
  return mergeRowsByKey(previous, next, (row) => row.tenor);
}

function mergeOiExpiries(previous: OiExpiry[], next: OiExpiry[]) {
  return mergeRowsByKey(previous, next, (row) => row.expiry);
}

function mergeRowsByKey<T extends object>(
  previous: T[],
  next: T[],
  keyFor: (row: T) => string | number,
) {
  if (previous.length === 0) return next;
  const previousByKey = new Map(previous.map((row) => [keyFor(row), row]));
  let sameArray = previous.length === next.length;
  const merged = next.map((row, index) => {
    const current = previousByKey.get(keyFor(row));
    const nextRow = current && sameFlatObject(current, row) ? current : row;
    if (nextRow !== previous[index]) sameArray = false;
    return nextRow;
  });
  return sameArray ? previous : merged;
}

function mergeNullableFlatObject<T extends object>(previous: T | null, next: T) {
  return previous ? mergeFlatObject(previous, next) : next;
}

function mergeFlatObject<T extends object>(previous: T, next: T) {
  return sameFlatObject(previous, next) ? previous : next;
}

function mergeSummary(previous: Summary, patch: Partial<Summary>) {
  const nextAtmIv = patch.atmIv ? mergeRecord(previous.atmIv, patch.atmIv) : previous.atmIv;
  const next = { ...previous, ...patch, atmIv: nextAtmIv };
  return sameFlatObject(previous, next) ? previous : next;
}

function mergeRecord(previous: Record<string, NullableNumber>, patch: Record<string, NullableNumber>) {
  const next = { ...previous, ...patch };
  return sameFlatObject(previous, next) ? previous : next;
}

function sameFlatObject<T extends object>(left: T, right: T) {
  const leftKeys = Object.keys(left) as Array<keyof T>;
  const rightKeys = Object.keys(right) as Array<keyof T>;
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every((key) => (
    Object.prototype.hasOwnProperty.call(right, key) && Object.is(left[key], right[key])
  ));
}

function mergeOrderFlowEvents(previous: OrderFlowEvent[], next: OrderFlowEvent[]) {
  if (previous.length === 0) return next;
  const previousById = new Map(previous.map((event) => [event.id, event]));
  let sameArray = previous.length === next.length;
  const merged = next.map((event, index) => {
    const current = previousById.get(event.id);
    const nextEvent = current && sameOrderFlowEvent(current, event) ? current : event;
    if (nextEvent !== previous[index]) sameArray = false;
    return nextEvent;
  });
  return sameArray ? previous : merged;
}

function sameOrderFlowEvent(left: OrderFlowEvent, right: OrderFlowEvent) {
  return left.id === right.id
    && left.sourceEndpoint === right.sourceEndpoint
    && left.externalEventId === right.externalEventId
    && left.eventKind === right.eventKind
    && left.executionType === right.executionType
    && left.legStructure === right.legStructure
    && left.optionMix === right.optionMix
    && left.tradeTsMs === right.tradeTsMs
    && left.observedAtMs === right.observedAtMs
    && left.currency === right.currency
    && left.side === right.side
    && left.sideSource === right.sideSource
    && left.amount === right.amount
    && left.price === right.price
    && left.premiumUsd === right.premiumUsd
    && left.orderType === right.orderType
    && left.timeInForce === right.timeInForce
    && left.rfqId === right.rfqId
    && left.quoteId === right.quoteId
    && left.txHash === right.txHash
    && left.txStatus === right.txStatus
    && left.subaccountId === right.subaccountId
    && left.wallet === right.wallet
    && sameOrderFlowLegs(left.legs, right.legs);
}

function sameOrderFlowLegs(left: OrderFlowEvent['legs'], right: OrderFlowEvent['legs']) {
  if (left.length !== right.length) return false;
  return left.every((leftLeg, index) => {
    const rightLeg = right[index];
    return leftLeg.legIndex === rightLeg.legIndex
      && leftLeg.instrumentName === rightLeg.instrumentName
      && leftLeg.optionType === rightLeg.optionType
      && leftLeg.expiry === rightLeg.expiry
      && leftLeg.strike === rightLeg.strike
      && leftLeg.side === rightLeg.side
      && leftLeg.amount === rightLeg.amount
      && leftLeg.price === rightLeg.price
      && leftLeg.premiumUsd === rightLeg.premiumUsd;
  });
}

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs, value]);
  return debounced;
}

const AtmChangeTable = memo(function AtmChangeTable({ rows, loading }: { rows: AtmTerm[]; loading: boolean }) {
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
});

const SkewFlyTable = memo(function SkewFlyTable({
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
  const byTenor = useMemo(() => new Map(rows.map((row) => [row.tenor, row])), [rows]);
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
});

function findExpiry(rows: ExpiryMetric[] | undefined, expiry: string) {
  return rows?.find((row) => row.expiry === expiry);
}

function measureOptionBuild<T>(name: string, build: () => T) {
  const start = markPerf();
  const result = build();
  measurePerf(name, start);
  return result;
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}
