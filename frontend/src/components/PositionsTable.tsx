import type { WalletPosition } from '../types';
import { formatCompact, formatExpiry, formatNumber, formatStrike } from '../format';
import { SelectControl } from './Controls';

export function PositionsTable({
  positions,
  selectedIds,
  assetFilter,
  assetOptions,
  loading,
  getRowId,
  isSelectable,
  onSelectionChange,
  onAssetFilterChange,
}: {
  positions: WalletPosition[];
  selectedIds: string[];
  assetFilter: string;
  assetOptions: string[];
  loading: boolean;
  getRowId: (position: WalletPosition, index: number) => string;
  isSelectable?: (position: WalletPosition) => boolean;
  onSelectionChange: (ids: string[]) => void;
  onAssetFilterChange: (asset: string) => void;
}) {
  const selectableRows = positions.map((position, index) => ({
    id: getRowId(position, index),
    selectable: isSelectable ? isSelectable(position) : true,
  }));
  const allIds = selectableRows.filter((row) => row.selectable).map((row) => row.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.includes(id));

  const toggleOne = (id: string, selectable: boolean) => {
    if (!selectable) return;
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((selectedId) => selectedId !== id)
        : [...selectedIds, id]
    );
  };

  return (
    <section className="change-panel positions-table-panel">
      <div className="panel-heading-row">
        <h2>Positions</h2>
        <div className="positions-heading-controls">
          <SelectControl value={assetFilter} options={assetOptions} onChange={onAssetFilterChange} label="Asset" />
          <span>{selectedIds.length}/{positions.length} selected</span>
        </div>
      </div>
      <div className="table-scroll">
        <table>
        <thead>
          <tr>
            <th className="select-column">
              <input
                type="checkbox"
                checked={allSelected}
                disabled={allIds.length === 0}
                onChange={() => onSelectionChange(allSelected ? [] : allIds)}
                aria-label="Select all positions"
              />
            </th>
            <th>Instrument</th>
            <th>Type</th>
            <th>Expiry</th>
            <th>Strike</th>
            <th>Side</th>
            <th>Notional</th>
            <th>Mark</th>
            <th>PnL</th>
            <th>Tx Hash</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr><td colSpan={10} className="empty-cell">{loading ? 'Loading positions' : 'No wallet positions'}</td></tr>
          )}
          {positions.map((position, index) => {
            const id = getRowId(position, index);
            const selectable = isSelectable ? isSelectable(position) : true;
            return (
              <tr key={id}>
                <td className="select-column">
                  <input
                    type="checkbox"
                    checked={selectable && selectedIds.includes(id)}
                    disabled={!selectable}
                    onChange={() => toggleOne(id, selectable)}
                    aria-label={`Select ${position.instrumentName}`}
                  />
                </td>
                <td>{position.instrumentName}</td>
                <td>{formatPositionType(position)}</td>
                <td>{isPerpPosition(position) ? 'Perp' : formatExpiry(position.expiry)}</td>
                <td>{formatStrike(position.strike)}</td>
                <td>{formatPositionSide(position)}</td>
                <td>{formatNotional(position)}</td>
                <td>{formatNumber(position.markPrice, 4)}</td>
                <td>{formatSignedUsd(position.pnl)}</td>
                <td>{position.txHash ? <TxHashLink txHash={position.txHash} /> : '-'}</td>
              </tr>
            );
          })}
        </tbody>
        </table>
      </div>
    </section>
  );
}

function TxHashLink({ txHash }: { txHash: string }) {
  return (
    <a href={`https://explorer.derive.xyz/tx/${txHash}`} target="_blank" rel="noreferrer">
      {formatHash(txHash)}
    </a>
  );
}

function formatPositionType(position: WalletPosition) {
  if (isPerpPosition(position)) return 'Perp';
  return formatOptionType(position.optionType);
}

function formatOptionType(value: string | null | undefined) {
  if (value === 'call') return 'Call';
  if (value === 'put') return 'Put';
  return value ?? '-';
}

function isPerpPosition(position: WalletPosition) {
  return String(position.instrumentType ?? '').toLowerCase() === 'perp'
    || position.instrumentName.toUpperCase().endsWith('-PERP');
}

function formatSigned(value: number | null | undefined) {
  if (value == null) return '-';
  const formatted = formatCompact(Math.abs(value), 2);
  return value > 0 ? `+${formatted}` : value < 0 ? `-${formatted}` : formatted;
}

function formatSignedUsd(value: number | null | undefined) {
  const formatted = formatSigned(value);
  return formatted === '-' ? '-' : formatted.startsWith('-') ? `-$${formatted.slice(1)}` : formatted.startsWith('+') ? `+$${formatted.slice(1)}` : `$${formatted}`;
}

function formatPositionSide(position: WalletPosition) {
  const raw = String(position.side ?? '').toLowerCase();
  if (raw === 'long' || raw === 'buy') return 'Long';
  if (raw === 'short' || raw === 'sell') return 'Short';
  if (position.amount == null) return '-';
  return position.amount >= 0 ? 'Long' : 'Short';
}

function formatNotional(position: WalletPosition) {
  const notional = position.notionalUsd ?? (
    position.amount != null && position.strike != null
      ? Math.abs(position.amount * position.strike)
      : null
  );
  return notional == null ? formatCompact(position.amount, 2) : `$${formatCompact(notional, 2)}`;
}

function formatHash(value: string) {
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}
