import { memo, useEffect, useRef, useState } from 'react';
import { DropdownControl } from './Controls';
import { formatCompact, formatDateTime, formatStrike } from '../format';
import type { OrderFlowEvent, OrderFlowFilters, OrderFlowLeg } from '../types';

const EXECUTION_OPTIONS = ['', 'ORDERBOOK_ORDER', 'RFQ'];
const MIX_OPTIONS = ['', 'CALL', 'PUT', 'BOTH'];
const SIDE_OPTIONS = ['', 'buy', 'sell', 'unknown'];
const ORDER_TYPE_OPTIONS = ['', 'limit', 'market'];
const TIF_OPTIONS = ['', 'gtc', 'post_only', 'fok', 'ioc'];

export const OrderFlowRail = memo(function OrderFlowRail({
  events,
  filters,
  loading,
  onFiltersChange,
}: {
  events: OrderFlowEvent[];
  filters: OrderFlowFilters;
  loading: boolean;
  onFiltersChange: (filters: OrderFlowFilters) => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [copiedEventId, setCopiedEventId] = useState<string | null>(null);
  const [freshEventIds, setFreshEventIds] = useState<Set<string>>(new Set());
  const previousEventIdsRef = useRef<Set<string>>(new Set());
  const copiedTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copiedTimerRef.current != null) window.clearTimeout(copiedTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const previousIds = previousEventIdsRef.current;
    const currentIds = new Set(events.map((event) => event.id));
    const incomingIds = previousIds.size === 0
      ? []
      : events.map((event) => event.id).filter((id) => !previousIds.has(id));
    previousEventIdsRef.current = currentIds;
    if (incomingIds.length === 0) return;
    setFreshEventIds(new Set(incomingIds));
    const timer = window.setTimeout(() => setFreshEventIds(new Set()), 1250);
    return () => window.clearTimeout(timer);
  }, [events]);

  const markCopied = (eventId: string) => {
    setCopiedEventId(eventId);
    if (copiedTimerRef.current != null) window.clearTimeout(copiedTimerRef.current);
    copiedTimerRef.current = window.setTimeout(() => setCopiedEventId((current) => current === eventId ? null : current), 1400);
  };

  const update = (key: keyof OrderFlowFilters, value: string) => {
    onFiltersChange({ ...filters, [key]: value });
  };
  const walletAddress = filters.wallet.trim();
  const activeAdvancedFilters = [
    filters.orderType,
    filters.timeInForce,
    filters.minAmount,
    filters.minPremiumUsd,
    filters.wallet,
    filters.subaccountId,
  ].filter(Boolean).length;

  return (
    <aside className="order-flow-rail" aria-label="Order flow">
      <header className="order-flow-header">
        <div>
          <h2>Order Flow</h2>
          <span>{events.length ? `${events.length} latest` : loading ? 'Loading' : 'No events'}</span>
        </div>
        <button
          className="order-flow-filter-toggle"
          type="button"
          aria-expanded={advancedOpen}
          aria-controls="order-flow-advanced-filters"
          onClick={() => setAdvancedOpen((open) => !open)}
        >
          Filters{activeAdvancedFilters ? ` ${activeAdvancedFilters}` : ''}
        </button>
      </header>
      <div className="order-flow-filters">
        <RailSelect label="Type" value={filters.executionType} options={EXECUTION_OPTIONS} onChange={(value) => update('executionType', value)} />
        <RailSelect label="Mix" value={filters.optionMix} options={MIX_OPTIONS} onChange={(value) => update('optionMix', value)} />
        <RailSelect label="Side" value={filters.side} options={SIDE_OPTIONS} onChange={(value) => update('side', value)} />
        {advancedOpen && (
          <div className="order-flow-advanced-filters" id="order-flow-advanced-filters">
            {filters.executionType === 'ORDERBOOK_ORDER' && (
              <>
                <RailSelect label="Order" value={filters.orderType} options={ORDER_TYPE_OPTIONS} onChange={(value) => update('orderType', value)} />
                <RailSelect label="TIF" value={filters.timeInForce} options={TIF_OPTIONS} onChange={(value) => update('timeInForce', value)} />
              </>
            )}
            <RailInput label="Min Size" value={filters.minAmount} onChange={(value) => update('minAmount', value)} />
            <RailInput label="Min Premium" value={filters.minPremiumUsd} onChange={(value) => update('minPremiumUsd', value)} />
            <RailInput label="Wallet" value={walletAddress} onChange={(value) => update('wallet', value)} />
            <RailInput label="Subaccount" value={filters.subaccountId} onChange={(value) => update('subaccountId', value)} />
          </div>
        )}
      </div>
      <div className="order-flow-list">
        {events.length === 0 && (
          <div className="order-flow-empty">
            {loading ? 'Loading order flow' : 'Waiting for order flow events'}
          </div>
        )}
        {events.map((event) => {
          const open = expanded[event.id] ?? false;
          const priority = eventPriority(event);
          return (
            <article className={['order-flow-card', priority, open ? 'open' : '', freshEventIds.has(event.id) ? 'fresh' : ''].filter(Boolean).join(' ')} key={event.id}>
              <button
                className="order-flow-card-button"
                type="button"
                aria-expanded={open}
                aria-controls={`order-flow-legs-${event.id}`}
                onClick={() => setExpanded((current) => ({ ...current, [event.id]: !open }))}
              >
                <div className="order-flow-badges">
                  {priority === 'large' && <Badge value="Large" tone="large" />}
                  <Badge value={event.executionType === 'ORDERBOOK_ORDER' ? 'ORDERBOOK' : 'RFQ'} tone={event.executionType === 'RFQ' ? 'rfq' : 'neutral'} />
                  <Badge value={event.optionMix} tone={event.optionMix.toLowerCase()} />
                </div>
                <div className="order-flow-title-row">
                  <div className="order-flow-title">{eventTitle(event)}</div>
                  <span>{formatPremium(event.premiumUsd)}</span>
                </div>
                <div className="order-flow-meta">
                  <span>Size {formatCompact(event.amount, 1)}</span>
                  <span>{event.side}</span>
                </div>
                <div className="order-flow-meta">
                  <span>{formatDateTime(event.tradeTsMs ?? event.observedAtMs)}</span>
                  <span>{event.orderType ? `${event.orderType}${event.timeInForce ? ` / ${event.timeInForce}` : ''}` : event.side}</span>
                </div>
              </button>
              <div className="order-flow-meta order-flow-address-row">
                <AddressCopy
                  address={event.wallet}
                  copied={copiedEventId === event.id}
                  onCopy={async () => {
                    if (!event.wallet) return;
                    const copied = await copyTextToClipboard(event.wallet);
                    if (copied) markCopied(event.id);
                  }}
                />
                <span>{event.subaccountId ? `Sub ${event.subaccountId}` : 'Sub n/a'}</span>
              </div>
              {open && (
                <div className="order-flow-legs" id={`order-flow-legs-${event.id}`}>
                  {event.legs.map((leg) => <OrderFlowLegRow leg={leg} key={`${event.id}-${leg.legIndex}`} />)}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </aside>
  );
});

function RailSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <DropdownControl
      className="rail-control rail-select-control"
      label={label}
      value={value}
      options={options}
      onChange={onChange}
      placeholder="All"
    />
  );
}

function eventPriority(event: OrderFlowEvent) {
  const premium = event.premiumUsd ?? 0;
  const amount = event.amount ?? 0;
  return premium >= 50_000 || amount >= 100 ? 'large' : 'standard';
}

function formatPremium(value: number | null) {
  return value == null ? '$-' : `$${formatCompact(value, 1)}`;
}

function RailInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="rail-control">
      <span>{label}</span>
      <input inputMode="decimal" value={value} onChange={(event) => onChange(event.target.value)} placeholder="All" />
    </label>
  );
}

function Badge({ value, tone }: { value: string; tone: string }) {
  return <span className={`order-flow-badge ${tone}`}>{value}</span>;
}

function AddressCopy({
  address,
  copied,
  onCopy,
}: {
  address: string | null;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <span className="order-flow-address" title={address ?? 'Address unavailable'}>
      <span className="order-flow-address-label">{formatAddress(address)}</span>
      {address && (
        <button className={`address-copy-button${copied ? ' copied' : ''}`} type="button" onClick={() => void onCopy()} aria-label={`Copy full address ${address}`} title={copied ? 'Copied' : 'Copy full address'}>
          <span className="address-copy-glyph" aria-hidden="true" />
        </button>
      )}
    </span>
  );
}

function OrderFlowLegRow({ leg }: { leg: OrderFlowLeg }) {
  return (
    <div className="order-flow-leg">
      <span className={`leg-side ${leg.side}`}>{leg.side}</span>
      <span>{formatCompact(leg.amount, 1)}</span>
      <span>{leg.expiry.replace(/-/g, '/')}</span>
      <span>${formatStrike(leg.strike)}{leg.optionType === 'call' ? 'C' : 'P'}</span>
      <span>${formatCompact(leg.premiumUsd, 1)}</span>
    </div>
  );
}

function eventTitle(event: OrderFlowEvent) {
  if (event.legs.length === 1) {
    const leg = event.legs[0];
    const side = leg.side === 'unknown' ? '' : `${capitalize(leg.side)} `;
    return `${side}${leg.optionType === 'call' ? 'Call' : 'Put'} / ${leg.instrumentName}`;
  }
  return `${event.legs.length} legs / ${event.optionMix}`;
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatAddress(value: string | null) {
  if (!value) {
    return 'Address n/a';
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the textarea path for local HTTP deployments.
    }
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, value.length);
  const copied = document.execCommand('copy');
  textarea.remove();
  return copied;
}
