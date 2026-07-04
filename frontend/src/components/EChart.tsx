import { memo, useEffect, useRef } from 'react';
import type Highcharts from 'highcharts';
import type { AxisOptions, Options } from 'highcharts';
import { markPerf, measurePerf } from '../perf';

type ChartSeriesOption = NonNullable<Options['series']>[number];
type HighchartsRuntime = typeof Highcharts;

let highchartsPromise: Promise<HighchartsRuntime> | null = null;

function loadHighcharts() {
  highchartsPromise ??= import('highcharts').then(async (module) => {
    const highcharts = module.default;
    await import('highcharts/modules/stock.js');
    highcharts.setOptions({
      lang: { numericSymbols: ['k', 'm', 'b', 't'] },
      chart: { animation: false },
      accessibility: { enabled: false },
    });
    return highcharts;
  });
  return highchartsPromise;
}

export const EChart = memo(function EChart({ option }: { option: Options }) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Highcharts.Chart | null>(null);
  const optionRef = useRef(option);
  const updateFrameRef = useRef<number | null>(null);
  const resizeFrameRef = useRef<number | null>(null);
  const hiddenOptionRef = useRef<Options | null>(null);

  const queueUpdate = (chart: Highcharts.Chart, nextOption: Options) => {
    if (updateFrameRef.current != null) window.cancelAnimationFrame(updateFrameRef.current);
    updateFrameRef.current = window.requestAnimationFrame(() => {
      updateFrameRef.current = null;
      if (chartRef.current !== chart) return;
      applyChartUpdate(chart, nextOption);
      triggerLineDrawing(nodeRef.current);
    });
  };

  useEffect(() => {
    if (!nodeRef.current) return;
    const node = nodeRef.current;
    let alive = true;
    let chart: Highcharts.Chart | null = null;
    let observer: ResizeObserver | null = null;
    let resize: (() => void) | null = null;

    loadHighcharts().then((highcharts) => {
      if (!alive || !node.isConnected) return;
      chart = highcharts.chart(node, optionRef.current);
      chartRef.current = chart;
      triggerLineDrawing(node);

      resize = () => {
        if (resizeFrameRef.current != null || !chart) return;
        const targetChart = chart;
        resizeFrameRef.current = window.requestAnimationFrame(() => {
          resizeFrameRef.current = null;
          safeReflow(targetChart, node, alive);
        });
      };
      observer = new ResizeObserver(resize);
      observer.observe(node);
      window.addEventListener('resize', resize);
      requestAnimationFrame(resize);
    });

    return () => {
      alive = false;
      if (updateFrameRef.current != null) window.cancelAnimationFrame(updateFrameRef.current);
      if (resizeFrameRef.current != null) window.cancelAnimationFrame(resizeFrameRef.current);
      observer?.disconnect();
      if (resize) window.removeEventListener('resize', resize);
      chart?.destroy();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const flushHiddenUpdate = () => {
      if (document.hidden) return;
      const chart = chartRef.current;
      const hiddenOption = hiddenOptionRef.current;
      if (!chart || !hiddenOption) return;
      hiddenOptionRef.current = null;
      queueUpdate(chart, hiddenOption);
    };
    document.addEventListener('visibilitychange', flushHiddenUpdate);
    return () => document.removeEventListener('visibilitychange', flushHiddenUpdate);
  }, []);

  useEffect(() => {
    optionRef.current = option;
    const chart = chartRef.current;
    if (!chart) return;
    if (document.hidden) {
      hiddenOptionRef.current = optionRef.current;
      return;
    }
    queueUpdate(chart, optionRef.current);
  }, [option]);

  return <div ref={nodeRef} className="chart-host" />;
});

function safeReflow(chart: Highcharts.Chart, node: HTMLDivElement | null, alive: boolean) {
  if (!alive || !node?.isConnected) return;
  try {
    chart.reflow();
  } catch {
    // Highcharts can receive a late resize frame after React has detached the node.
  }
}

function triggerLineDrawing(node: HTMLElement | null) {
  if (!node?.isConnected) return;
  const paths = Array.from(node.querySelectorAll<SVGPathElement>('.highcharts-graph'));
  if (paths.length === 0) return;
  for (const path of paths) {
    try {
      path.style.setProperty('--line-length', `${Math.ceil(path.getTotalLength())}`);
    } catch {
      path.style.removeProperty('--line-length');
    }
  }
  node.classList.remove('line-drawing-active');
  void node.offsetWidth;
  node.classList.add('line-drawing-active');
  window.setTimeout(() => node.classList.remove('line-drawing-active'), 420);
}

function applyChartUpdate(chart: Highcharts.Chart, nextOption: Options) {
  const updateStart = markPerf();
  const chartName = String(nextOption.chart?.className ?? 'chart');
  const nextSeries = normalizeSeries(nextOption.series);
  const currentSeries = userSeries(chart.series);
  if (!canPatchSeries(currentSeries, nextSeries)) {
    chart.update(nextOption, false, true, false);
    chart.redraw(false);
    measurePerf('chart.full_update', updateStart, { chart: chartName, series: nextSeries.length });
    return;
  }

  updateAxes(userAxes(chart.xAxis), normalizeAxes(nextOption.xAxis));
  updateAxes(userAxes(chart.yAxis), normalizeAxes(nextOption.yAxis));
  if (nextOption.title || nextOption.subtitle) {
    chart.setTitle(nextOption.title, nextOption.subtitle, false);
  }

  nextSeries.forEach((seriesOption, index) => {
    const data = getSeriesData(seriesOption);
    if (data) {
      currentSeries[index].setData(data, false, false, false);
    }
  });
  chart.redraw(false);
  measurePerf('chart.patch_update', updateStart, { chart: chartName, series: nextSeries.length });
}

function canPatchSeries(currentSeries: Highcharts.Series[], nextSeries: ChartSeriesOption[]) {
  if (nextSeries.length === 0 || currentSeries.length !== nextSeries.length) return false;
  return nextSeries.every((seriesOption, index) => {
    const current = currentSeries[index];
    const nextType = getSeriesType(seriesOption) ?? current.type;
    const nextStack = getSeriesStack(seriesOption);
    return current.type === nextType
      && current.name === seriesOption.name
      && getSeriesStack(current.options as ChartSeriesOption) === nextStack;
  });
}

function updateAxes(axes: Highcharts.Axis[], nextAxes: AxisOptions[]) {
  if (nextAxes.length === 0 || axes.length !== nextAxes.length) return;
  nextAxes.forEach((axisOption, index) => {
    axes[index].update(axisOption, false);
  });
}

function userSeries(series: Highcharts.Series[]) {
  return series.filter((item) => !isInternalOption(item.options));
}

function userAxes(axes: Highcharts.Axis[]) {
  return axes.filter((axis) => !isInternalOption(axis.options));
}

function isInternalOption(option: object) {
  return Boolean((option as { isInternal?: boolean }).isInternal);
}

function normalizeSeries(series: Options['series']) {
  return Array.isArray(series) ? series : [];
}

function normalizeAxes(axis: Options['xAxis'] | Options['yAxis']) {
  if (!axis) return [];
  return Array.isArray(axis) ? axis : [axis];
}

function getSeriesData(seriesOption: ChartSeriesOption) {
  return (seriesOption as { data?: Highcharts.PointOptionsType[] }).data;
}

function getSeriesType(seriesOption: ChartSeriesOption) {
  return (seriesOption as { type?: string }).type;
}

function getSeriesStack(seriesOption: ChartSeriesOption) {
  return (seriesOption as { stack?: string | number }).stack;
}
