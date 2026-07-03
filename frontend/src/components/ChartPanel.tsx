import { memo, type ReactNode } from 'react';
import type { Options } from 'highcharts';
import { EChart } from './EChart';

type ChartPanelProps = {
  option: Options;
  controls?: ReactNode;
  className?: string;
  updating?: boolean;
  loading?: boolean;
  empty?: boolean;
  notice?: string | null;
  emptyLabel?: string;
};

export const ChartPanel = memo(function ChartPanel({
  option,
  controls,
  className,
  updating,
  loading,
  empty,
  notice,
  emptyLabel = 'No data available',
}: ChartPanelProps) {
  const state = loading ? 'loading' : empty ? 'empty' : updating ? 'updating' : 'ready';
  const classes = ['chart-panel', className].filter(Boolean).join(' ');
  return (
    <section className={classes} data-state={state} aria-busy={loading || updating ? 'true' : undefined}>
      {(controls || updating || notice) && (
        <div className="panel-controls">
          {notice && <span className="panel-notice">{notice}</span>}
          {updating && <span className="updating">Updating</span>}
          {controls}
        </div>
      )}
      <EChart option={option} />
      {(loading || empty) && (
        <div className="panel-state" role="status" aria-live="polite">
          {loading && (
            <div className="panel-state-skeleton" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
            </div>
          )}
          <span className="panel-state-label">{loading ? 'Loading market data' : emptyLabel}</span>
        </div>
      )}
    </section>
  );
});
