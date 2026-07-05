import { memo } from 'react';
import type { Snapshot, SocketStatus } from '../types';
import { formatDateTime } from '../format';

export const TopBar = memo(function TopBar({ snapshot, status }: { snapshot: Snapshot | null; status: SocketStatus }) {
  return (
    <header className="topbar">
      <div className="topbar-status" role="status" aria-live="polite">
        <span className="muted">Snapshot: {formatDateTime(snapshot?.latestTsMs)}</span>
        <span className={`status-dot ${status}`} />
        <span>{statusLabel(status)}</span>
      </div>
    </header>
  );
});

function statusLabel(status: SocketStatus) {
  if (status === 'live') return 'Live';
  if (status === 'updating') return 'Updating';
  if (status === 'stale') return 'Stale';
  if (status === 'reconnecting') return 'Reconnecting';
  if (status === 'offline') return 'Offline';
  return 'Connecting';
}
