import { memo, useEffect, useRef } from 'react';
import Highcharts from 'highcharts';
import type { Options } from 'highcharts';

const LINE_DRAWING_CLASS = 'line-drawing-active';

Highcharts.setOptions({
  lang: { numericSymbols: ['k', 'm', 'b', 't'] },
  chart: { animation: false },
});

export const EChart = memo(function EChart({ option }: { option: Options }) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Highcharts.Chart | null>(null);
  const optionRef = useRef(option);
  const updateFrameRef = useRef<number | null>(null);
  const drawFrameRef = useRef<number | null>(null);
  const drawKeyRef = useRef(option.chart?.className ?? '');

  const queueLineDrawing = () => {
    if (drawFrameRef.current != null) window.cancelAnimationFrame(drawFrameRef.current);
    drawFrameRef.current = window.requestAnimationFrame(() => {
      drawFrameRef.current = null;
      triggerLineDrawing(nodeRef.current);
    });
  };

  useEffect(() => {
    if (!nodeRef.current) return;
    const node = nodeRef.current;
    const chart = Highcharts.chart(node, option);
    let alive = true;
    chartRef.current = chart;

    const resize = () => safeReflow(chart, node, alive);
    const observer = new ResizeObserver(resize);
    observer.observe(node);
    window.addEventListener('resize', resize);
    requestAnimationFrame(resize);
    queueLineDrawing();

    return () => {
      alive = false;
      if (updateFrameRef.current != null) window.cancelAnimationFrame(updateFrameRef.current);
      if (drawFrameRef.current != null) window.cancelAnimationFrame(drawFrameRef.current);
      observer.disconnect();
      window.removeEventListener('resize', resize);
      chart.destroy();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    optionRef.current = option;
    const chart = chartRef.current;
    const node = nodeRef.current;
    if (!chart) return;
    if (updateFrameRef.current != null) window.cancelAnimationFrame(updateFrameRef.current);
    updateFrameRef.current = window.requestAnimationFrame(() => {
      updateFrameRef.current = null;
      if (chartRef.current !== chart) return;
      chart.update(optionRef.current, false, true, false);
      chart.redraw(false);
      safeReflow(chart, node, chartRef.current === chart);
      const drawKey = optionRef.current.chart?.className ?? '';
      if (drawKeyRef.current !== drawKey) {
        drawKeyRef.current = drawKey;
        queueLineDrawing();
      }
    });
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

function triggerLineDrawing(node: HTMLDivElement | null) {
  if (!node?.isConnected) return;
  const paths = Array.from(node.querySelectorAll<SVGPathElement>('.highcharts-graph'));
  let hasDrawableLine = false;
  for (const path of paths) {
    try {
      const length = Math.ceil(path.getTotalLength());
      if (!Number.isFinite(length) || length <= 0) continue;
      path.style.setProperty('--line-length', `${length}px`);
      hasDrawableLine = true;
    } catch {
      // Highcharts can detach helper paths during redraw.
    }
  }
  if (!hasDrawableLine) return;
  node.classList.remove(LINE_DRAWING_CLASS);
  void node.offsetWidth;
  node.classList.add(LINE_DRAWING_CLASS);
}
