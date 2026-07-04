import type { Options, SeriesOptionsType } from 'highcharts';
import type { GreekCurvePoint, GreekMetric, NullableNumber } from '../types';
import { formatCompact, formatNumber } from '../format';

const br = '<tspan class="highcharts-br">&ZeroWidthSpace;</tspan>';
const axisLabelStyle = { fontSize: '0.7rem', fontWeight: '400' };

const escapeSvgText = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const header = (label: string) => `<tspan class="highcharts-header tooltip-date">${escapeSvgText(label)}</tspan>`;
const pointLine = (colorClass: string, text: string) =>
  `<tspan class="highcharts-color-${colorClass}">●</tspan> ${escapeSvgText(text)}`;
const tooltipLabel = (context: any) => String(
  context?.point?.custom?.xLabel
    ?? context?.point?.category
    ?? context?.key
    ?? context?.x
    ?? ''
);

const tooltip = (formatter: (this: any) => string): Options['tooltip'] => ({
  className: 'highcharts-tooltip',
  borderRadius: 2,
  valueDecimals: 4,
  animation: false,
  useHTML: false,
  formatter,
});

const asSeries = (series: SeriesOptionsType[]) => series;

const metricLabel = (metric: GreekMetric) => {
  if (metric === 'delta') return 'Delta';
  if (metric === 'gamma') return 'Gamma';
  if (metric === 'vega') return 'Vega';
  return 'Theta';
};

const PRICE_TICK_INTERVAL = 5;

const shockPercent = (point: GreekCurvePoint) => {
  const raw = point.shockPct ?? point.shock;
  return Math.abs(raw) <= 1 ? raw * 100 : raw;
};

const shockLabel = (point: GreekCurvePoint) => {
  const pct = shockPercent(point);
  if (Math.abs(pct) < 0.0001) return 'Current';
  return `${pct > 0 ? '+' : ''}${formatNumber(pct, 0)}%`;
};

const priceLabel = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(value)) return '-';
  return formatNumber(value, Math.abs(value) >= 10 ? 0 : 2);
};

const curveXValue = (point: GreekCurvePoint, index: number) => (
  typeof point.spotPrice === 'number' && Number.isFinite(point.spotPrice)
    ? point.spotPrice
    : index
);

const priceAxisBounds = (rows: GreekCurvePoint[]): { min?: number; max?: number } => {
  const prices = rows
    .map((row) => row.spotPrice)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!prices.length) return {};
  return {
    min: Math.floor(Math.min(...prices) / PRICE_TICK_INTERVAL) * PRICE_TICK_INTERVAL,
    max: Math.ceil(Math.max(...prices) / PRICE_TICK_INTERVAL) * PRICE_TICK_INTERVAL,
  };
};

const formatUsdCompact = (value: number | null | undefined, digits = 4) => {
  if (value == null) return '-';
  const formatted = formatCompact(Math.abs(value), digits);
  if (value > 0) return `+$${formatted}`;
  if (value < 0) return `-$${formatted}`;
  return '$0';
};

const curvePointWithLabel = (row: GreekCurvePoint, y: number | null | undefined, index: number) => ({
  x: curveXValue(row, index),
  y: y ?? null,
  custom: { xLabel: priceLabel(row.spotPrice), spotPrice: row.spotPrice ?? null, shockLabel: shockLabel(row) },
}) as any;

export const greekValue = (point: GreekCurvePoint | null | undefined, metric: GreekMetric): NullableNumber => {
  if (!point) return null;
  if (point.value != null) return point.value;
  if (metric === 'delta') return point.delta ?? point.totalDelta ?? null;
  if (metric === 'gamma') return point.gamma ?? point.totalGamma ?? null;
  if (metric === 'vega') return point.vega ?? point.totalVega ?? null;
  return point.theta ?? point.totalTheta ?? null;
};

const currentPlotLine = (rows: GreekCurvePoint[]): any[] | undefined => {
  const index = rows.findIndex((row) => Math.abs(shockPercent(row)) < 0.0001);
  if (index < 0) return undefined;
  return [{
    value: curveXValue(rows[index], index),
    width: 1,
    zIndex: 5,
    dashStyle: 'Dash',
    className: 'atm-plot-line',
    label: {
      text: 'Current',
      rotation: 0,
      align: 'left',
      x: 4,
      y: 13,
      style: { fontSize: '0.72rem', fontWeight: '300' },
    },
  }];
};

export const greekCurveOption = (rows: GreekCurvePoint[], metric: GreekMetric): Options => {
  const label = metricLabel(metric);
  const priceBounds = priceAxisBounds(rows);
  return {
    chart: {
      backgroundColor: 'transparent',
      className: 'hype-chart greek-curve-chart',
      styledMode: true,
      animation: false,
      spacingTop: 13,
      spacingRight: 24,
      spacingBottom: 38,
      spacingLeft: 8,
    },
    title: { text: `Portfolio ${label} Curve`, align: 'left', x: 8, y: 15 },
    credits: { enabled: false },
    exporting: { enabled: false },
    legend: { enabled: false },
    xAxis: {
      type: 'linear',
      min: priceBounds.min,
      max: priceBounds.max,
      tickInterval: PRICE_TICK_INTERVAL,
      startOnTick: true,
      endOnTick: true,
      allowDecimals: false,
      title: { text: '' },
      crosshair: { className: 'highcharts-crosshair-x', snap: true },
      tickLength: 0,
      lineWidth: 1,
      labels: {
        style: axisLabelStyle,
        formatter: function () {
          const value = typeof this.value === 'number' ? this.value : Number(this.value);
          return Number.isFinite(value) ? priceLabel(value) : String(this.value);
        },
      },
      plotLines: currentPlotLine(rows),
    },
    yAxis: {
      opposite: true,
      title: { text: '' },
      tickLength: 0,
      lineWidth: 0,
      gridLineWidth: 1,
      plotLines: [{ width: 1, value: 0, zIndex: 4, className: 'zero-plot-line' }],
      labels: {
        style: axisLabelStyle,
        formatter: function () {
          const value = typeof this.value === 'number' ? this.value : Number(this.value);
          return Number.isFinite(value) ? formatCompact(value, 2) : String(this.value);
        },
      },
    },
    tooltip: tooltip(function () {
      const value = typeof this.y === 'number' ? formatCompact(this.y, 4) : '-';
      const spotPrice = this.point?.custom?.spotPrice;
      const spot = spotPrice == null ? null : `Price ${priceLabel(spotPrice)}`;
      const move = this.point?.custom?.shockLabel ? `Move ${this.point.custom.shockLabel}` : null;
      return [
        header(tooltipLabel(this)),
        pointLine(String(this.point?.colorIndex ?? '0'), `${label}: ${value}`),
        spot ? escapeSvgText(spot) : null,
        move ? escapeSvgText(move) : null,
      ].filter(Boolean).join(br);
    }),
    plotOptions: {
      series: {
        animation: { duration: 0 },
        states: { hover: { enabled: true, lineWidthPlus: 0, halo: { size: 3, opacity: 0.18 } } },
      },
      line: { marker: { symbol: 'circle', radius: 1.8, states: { hover: { radius: 3 } } }, lineWidth: 1.8 },
    },
    series: asSeries([
      {
        type: 'line',
        name: label,
        data: rows.map((row, index) => curvePointWithLabel(row, greekValue(row, metric), index)),
        threshold: null,
        colorIndex: 0,
      },
    ]),
  };
};

export const payoffCurveOption = (rows: GreekCurvePoint[]): Options => {
  const priceBounds = priceAxisBounds(rows);
  return {
    chart: {
      backgroundColor: 'transparent',
      className: 'hype-chart greek-curve-chart payoff-curve-chart',
      styledMode: true,
      animation: false,
      spacingTop: 13,
      spacingRight: 24,
      spacingBottom: 38,
      spacingLeft: 8,
    },
    title: { text: 'Payoff', align: 'left', x: 8, y: 15 },
    credits: { enabled: false },
    exporting: { enabled: false },
    legend: { enabled: false },
    xAxis: {
      type: 'linear',
      min: priceBounds.min,
      max: priceBounds.max,
      tickInterval: PRICE_TICK_INTERVAL,
      startOnTick: true,
      endOnTick: true,
      allowDecimals: false,
      title: { text: '' },
      crosshair: { className: 'highcharts-crosshair-x', snap: true },
      tickLength: 0,
      lineWidth: 1,
      labels: {
        style: axisLabelStyle,
        formatter: function () {
          const value = typeof this.value === 'number' ? this.value : Number(this.value);
          return Number.isFinite(value) ? priceLabel(value) : String(this.value);
        },
      },
      plotLines: currentPlotLine(rows),
    },
    yAxis: {
      opposite: true,
      title: { text: '' },
      tickLength: 0,
      lineWidth: 0,
      gridLineWidth: 1,
      plotLines: [{ width: 1, value: 0, zIndex: 4, className: 'zero-plot-line' }],
      labels: {
        style: axisLabelStyle,
        formatter: function () {
          const value = typeof this.value === 'number' ? this.value : Number(this.value);
          return Number.isFinite(value) ? formatUsdCompact(value, 2) : String(this.value);
        },
      },
    },
    tooltip: tooltip(function () {
      const value = typeof this.y === 'number' ? formatUsdCompact(this.y, 4) : '-';
      const spotPrice = this.point?.custom?.spotPrice;
      const spot = spotPrice == null ? null : `Price ${priceLabel(spotPrice)}`;
      const move = this.point?.custom?.shockLabel ? `Move ${this.point.custom.shockLabel}` : null;
      return [
        header(tooltipLabel(this)),
        pointLine(String(this.point?.colorIndex ?? '0'), `Payoff: ${value}`),
        spot ? escapeSvgText(spot) : null,
        move ? escapeSvgText(move) : null,
      ].filter(Boolean).join(br);
    }),
    plotOptions: {
      series: {
        animation: { duration: 0 },
        states: { hover: { enabled: true, lineWidthPlus: 0, halo: { size: 3, opacity: 0.18 } } },
      },
      line: { marker: { symbol: 'circle', radius: 1.8, states: { hover: { radius: 3 } } }, lineWidth: 1.8 },
    },
    series: asSeries([
      {
        type: 'line',
        name: 'Payoff',
        data: rows.map((row, index) => curvePointWithLabel(row, row.value, index)),
        threshold: 0,
        colorIndex: 1,
      },
    ]),
  };
};
