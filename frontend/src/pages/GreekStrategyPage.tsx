import { useEffect, useMemo, useRef, useState } from 'react';
import { getGreekStrategyOptions, getPortfolioGreeks, getWalletLookup } from '../api/client';
import { GreekCurvePanel } from '../components/GreekCurvePanel';
import { GreekSimulator } from '../components/GreekSimulator';
import { PortfolioGreekStrip } from '../components/PortfolioGreekStrip';
import { PositionsTable } from '../components/PositionsTable';
import { StrategySimulator } from '../components/StrategySimulator';
import { WalletLookupPanel } from '../components/WalletLookupPanel';
import type {
  GreekMetric,
  OptionInstrumentChoice,
  PortfolioGreeksResponse,
  WalletLookupResponse,
  WalletPosition,
} from '../types';

export type GreekTab = 'lookup' | 'greek' | 'strategy';

const PAGE_META: Record<GreekTab, { title: string }> = {
  lookup: { title: 'Position Lookup' },
  greek: { title: 'Greek Simulator' },
  strategy: { title: 'Strategy Simulator' },
};

export function GreekStrategyPage({ tab }: { tab: GreekTab }) {
  const [wallet, setWallet] = useState<WalletLookupResponse | null>(null);
  const [walletLoading, setWalletLoading] = useState(false);
  const [walletError, setWalletError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [assetFilter, setAssetFilter] = useState('');
  const [portfolio, setPortfolio] = useState<PortfolioGreeksResponse | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);
  const [portfolioMetric, setPortfolioMetric] = useState<GreekMetric>('delta');
  const [options, setOptions] = useState<OptionInstrumentChoice[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const walletControllerRef = useRef<AbortController | null>(null);
  const walletRequestRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
    walletControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (tab === 'lookup') {
      setOptions([]);
      setOptionsError(null);
      setOptionsLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setOptionsLoading(true);
    setOptionsError(null);
    getGreekStrategyOptions(controller.signal)
      .then((payload) => {
        if (!active) return;
        const rows = Array.isArray(payload) ? payload as OptionInstrumentChoice[] : payload.options;
        setOptions(rows ?? []);
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) {
          setOptions([]);
          setOptionsError('Options unavailable');
        }
      })
      .finally(() => {
        if (active) setOptionsLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [tab]);

  const underlyingOptions = useMemo(
    () => uniqueValues((wallet?.positions ?? []).map(positionUnderlying)).sort(),
    [wallet]
  );
  const visiblePositions = useMemo(
    () => (wallet?.positions ?? []).filter((position) => !assetFilter || positionUnderlying(position) === assetFilter),
    [assetFilter, wallet]
  );
  const visibleSelectedIds = useMemo(
    () => visiblePositions
      .filter(isGreekEligiblePosition)
      .map(positionRowId)
      .filter((id) => selectedIds.includes(id)),
    [selectedIds, visiblePositions]
  );
  const selectedPositions = useMemo(
    () => visiblePositions.filter((position, index) => isGreekEligiblePosition(position) && selectedIds.includes(positionRowId(position, index))),
    [selectedIds, visiblePositions]
  );
  const selectedUnderlyings = useMemo(
    () => uniqueValues(selectedPositions.map(positionUnderlying)).sort(),
    [selectedPositions]
  );
  const selectedPremium = useMemo(() => selectedPositions.reduce(
    (total, position) => total + (positionPremium(position) ?? 0),
    0
  ), [selectedPositions]);

  useEffect(() => {
    if (!wallet) {
      setPortfolio(null);
      setPortfolioError(null);
      return;
    }
    if (selectedPositions.length === 0) {
      setPortfolio(null);
      setPortfolioError(null);
      return;
    }
    if (selectedUnderlyings.length > 1) {
      setPortfolio(null);
      setPortfolioError('Select one asset to calculate Greeks and payoff');
      return;
    }
    const controller = new AbortController();
    let active = true;
    setPortfolioLoading(true);
    setPortfolioError(null);
    getPortfolioGreeks({ positions: selectedPositions, metric: 'delta' }, controller.signal)
      .then((payload) => {
        if (active) setPortfolio(payload);
      })
      .catch((error: unknown) => {
        if (active && !isAbortError(error)) {
          setPortfolio(null);
          setPortfolioError('Portfolio Greeks unavailable');
        }
      })
      .finally(() => {
        if (active) setPortfolioLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [wallet, selectedIds, selectedPositions, selectedUnderlyings]);

  const lookupWallet = async (address: string) => {
    walletControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = walletRequestRef.current + 1;
    walletRequestRef.current = requestId;
    walletControllerRef.current = controller;
      setWalletLoading(true);
      setWalletError(null);
      setPortfolio(null);
      setAssetFilter('');
      setSelectedIds([]);
    try {
      const payload = await getWalletLookup(address, controller.signal);
      if (!mountedRef.current || walletRequestRef.current !== requestId) return;
      setWallet(payload);
      setSelectedIds(payload.positions.filter(isGreekEligiblePosition).map(positionRowId));
    } catch (error: unknown) {
      if (mountedRef.current && walletRequestRef.current === requestId && !isAbortError(error)) {
        setWallet(null);
        setWalletError('Wallet lookup unavailable');
      }
    } finally {
      if (mountedRef.current && walletRequestRef.current === requestId) {
        setWalletLoading(false);
      }
    }
  };

  const meta = PAGE_META[tab];
  const routeStatus = statusForTab({
    tab,
    wallet,
    selectedCount: visibleSelectedIds.length,
    visibleCount: visiblePositions.length,
    optionsCount: options.length,
    optionsLoading,
    optionsError,
  });

  return (
    <div className="greek-strategy-page">
      <section className="route-topbar">
        <div>
          <h1>{meta.title}</h1>
        </div>
        <div className="route-topbar-status" role="status" aria-live="polite">
          <span className={`status-dot ${routeStatus.tone}`} />
          <span>{routeStatus.label}</span>
        </div>
      </section>

      {tab === 'lookup' && (
        <div className="greek-lookup-grid">
          <WalletLookupPanel wallet={wallet} loading={walletLoading} error={walletError} onLookup={lookupWallet} />
          <PositionsTable
            positions={visiblePositions}
            selectedIds={visibleSelectedIds}
            assetFilter={assetFilter}
            assetOptions={underlyingOptions}
            loading={walletLoading}
            getRowId={positionRowId}
            isSelectable={isGreekEligiblePosition}
            onSelectionChange={setSelectedIds}
            onAssetFilterChange={setAssetFilter}
          />
          <PortfolioGreekStrip summary={portfolio?.summary ?? null} premium={selectedPremium} loading={portfolioLoading} />
          <GreekCurvePanel
            curve={portfolio?.curves?.[portfolioMetric] ?? portfolio?.curve ?? null}
            payoffCurve={portfolio?.payoffCurve ?? null}
            metric={portfolioMetric}
            loading={portfolioLoading}
            error={portfolioError}
            onMetricChange={setPortfolioMetric}
          />
        </div>
      )}

      {tab === 'greek' && (
        <GreekSimulator options={options} optionsLoading={optionsLoading} optionsError={optionsError} />
      )}

      {tab === 'strategy' && (
        <StrategySimulator options={options} optionsLoading={optionsLoading} optionsError={optionsError} />
      )}
    </div>
  );
}

function positionRowId(position: WalletPosition, index: number) {
  void index;
  return position.id ?? `${position.subaccountId ?? 'sub'}-${position.instrumentName}-${position.amount ?? 'amount'}-${position.side ?? 'side'}-${position.strike ?? 'strike'}`;
}

function positionUnderlying(position: WalletPosition) {
  return position.underlying ?? position.instrumentName?.split('-', 1)[0] ?? '';
}

function isGreekEligiblePosition(position: WalletPosition) {
  const instrumentType = String(position.instrumentType ?? '').toLowerCase();
  if (instrumentType) return instrumentType === 'option' || instrumentType === 'options' || instrumentType === 'perp';
  return /^[A-Z]+-\d{8}-[0-9._]+-[CP]$/.test(position.instrumentName)
    || position.instrumentName.toUpperCase().endsWith('-PERP');
}

function positionPremium(position: WalletPosition) {
  if (isPerpPosition(position)) return null;
  if (position.premiumUsd != null) return position.premiumUsd;
  if (position.amount != null && position.markPrice != null) return position.amount * position.markPrice;
  return null;
}

function isPerpPosition(position: WalletPosition) {
  return String(position.instrumentType ?? '').toLowerCase() === 'perp'
    || position.instrumentName.toUpperCase().endsWith('-PERP');
}

function uniqueValues(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function statusForTab({
  tab,
  wallet,
  selectedCount,
  visibleCount,
  optionsCount,
  optionsLoading,
  optionsError,
}: {
  tab: GreekTab;
  wallet: WalletLookupResponse | null;
  selectedCount: number;
  visibleCount: number;
  optionsCount: number;
  optionsLoading: boolean;
  optionsError: string | null;
}) {
  if (tab === 'lookup') {
    if (!wallet) return { label: 'No wallet loaded', tone: 'stale' };
    return { label: `${selectedCount}/${visibleCount} positions selected`, tone: selectedCount > 0 ? 'live' : 'stale' };
  }
  if (optionsLoading) return { label: 'Loading instruments', tone: 'updating' };
  if (optionsError) return { label: 'Options unavailable', tone: 'stale' };
  return { label: `${optionsCount} instruments`, tone: optionsCount > 0 ? 'live' : 'stale' };
}
