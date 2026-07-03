import { useState } from 'react';
import type { WalletLookupResponse, WalletTrade } from '../types';
import { formatCompact, formatDateTime } from '../format';

export function WalletLookupPanel({
  wallet,
  loading,
  error,
  onLookup,
}: {
  wallet: WalletLookupResponse | null;
  loading: boolean;
  error: string | null;
  onLookup: (address: string) => void;
}) {
  const [address, setAddress] = useState('');

  return (
    <section className="change-panel wallet-lookup-panel">
      <div className="panel-heading-row">
        <h2>Wallet Lookup</h2>
        <span>{sourceLabel(wallet?.source)}</span>
      </div>
      <form
        className="wallet-lookup-form"
        onSubmit={(event) => {
          event.preventDefault();
          const trimmed = address.trim();
          if (trimmed) onLookup(trimmed);
        }}
      >
        <input
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="0x..."
          spellCheck={false}
          aria-label="Wallet address"
        />
        <button type="submit" disabled={loading || !address.trim()} aria-busy={loading ? 'true' : undefined}>
          {loading ? 'Loading' : 'Lookup'}
        </button>
      </form>
      {error && <div className="panel-inline-error" role="alert">{error}</div>}
      <div className="wallet-summary-strip">
        <SummaryCell label="Wallet" value={formatAddress(wallet?.wallet)} />
        <SummaryCell label="Owner" value={formatAddress(wallet?.scwOwner)} />
        <SummaryCell label="ENS" value={wallet?.ensName ?? '-'} />
        <SummaryCell label="Positions" value={wallet ? String(wallet.positions.length) : '-'} />
      </div>
      <div className="wallet-trades">
        <h3>Recent Trades</h3>
        <div className="table-scroll">
          <table>
          <thead>
            <tr><th>Instrument</th><th>Side</th><th>Size</th><th>Premium / Value</th><th>Time</th><th>Tx Hash</th></tr>
          </thead>
          <tbody>
            {!wallet && (
              <tr><td colSpan={6} className="empty-cell">{loading ? 'Loading wallet data' : 'No wallet loaded'}</td></tr>
            )}
            {wallet && wallet.trades.length === 0 && (
              <tr><td colSpan={6} className="empty-cell">No recent trades</td></tr>
            )}
            {wallet?.trades.slice(0, 6).map((trade, index) => (
              <TradeRow trade={trade} key={trade.id ?? `${trade.txHash ?? 'trade'}-${index}`} />
            ))}
          </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="strip-label">{label}</span>
      <span className="strip-value">{value}</span>
    </div>
  );
}

function TradeRow({ trade }: { trade: WalletTrade }) {
  return (
    <tr>
      <td>{trade.instrumentName ?? '-'}</td>
      <td>{formatTradeSide(trade.side)}</td>
      <td>{formatCompact(trade.amount, 2)}</td>
      <td>{formatUsd(trade.premiumUsd)}</td>
      <td>{formatDateTime(trade.timestampMs)}</td>
      <td>{trade.txHash ? <TxHashLink txHash={trade.txHash} /> : '-'}</td>
    </tr>
  );
}

function formatTradeSide(value: string | null | undefined) {
  if (!value) return '-';
  const normalized = value.toLowerCase();
  if (normalized === 'buy') return 'Buy';
  if (normalized === 'sell') return 'Sell';
  return value;
}

function formatUsd(value: number | null | undefined) {
  return value == null ? '-' : `$${formatCompact(value, 2)}`;
}

function TxHashLink({ txHash }: { txHash: string }) {
  return (
    <a href={`https://explorer.derive.xyz/tx/${txHash}`} target="_blank" rel="noreferrer">
      {formatHash(txHash)}
    </a>
  );
}

function formatAddress(value: string | null | undefined) {
  if (!value) return '-';
  if (value.length <= 12) return value;
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function formatHash(value: string) {
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function sourceLabel(source: WalletLookupResponse['source'] | undefined) {
  if (!source) return 'Derive Wallet';
  if (typeof source === 'string') return source;
  return source.type ?? 'Derive Wallet';
}
