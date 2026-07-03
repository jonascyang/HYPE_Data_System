import type { Options, SeriesOptionsType } from 'highcharts';
import type { AtmTerm, GexExpiryPoint, GexPoint, IvSmilePoint, OiExpiry, OiStrikePoint } from '../types';
import { formatCompact, formatContracts, formatExpiry, formatGex, formatStrike, formatVol } from '../format';
import { expiryColorIndex, formatChartValue, MULTI_SERIES_TOOLTIP_LIMIT, sortExpiries } from '../display';

const br = '<tspan class="highcharts-br">&ZeroWidthSpace;</tspan>';

const pct = (value: number | null) => (value == null ? null : value * 100);
const strikeLabels = (rows: Array<{ strike: number }>) => rows.map((row) => formatStrike(row.strike));
const asSeries = (series: SeriesOptionsType[]) => series;

const escapeSvgText = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const pointLine = (colorClass: string, text: string) =>
  `<tspan class="highcharts-color-${colorClass}">●</tspan> ${escapeSvgText(text)}`;

const mutedLine = (text: string) => `<tspan class="tooltip-total">${escapeSvgText(text)}</tspan>`;

const tooltip = (formatter: (this: any) => string): Options['tooltip'] => ({
  className: 'highcharts-tooltip',
  borderRadius: 2,
  valueDecimals: 2,
  animation: false,
  useHTML: false,
  formatter,
});

const axisLabelStyle = { fontSize: '0.7rem', fontWeight: '400' };
const axisTitleStyle = { fontSize: '0.62rem', fontWeight: '400', textTransform: 'uppercase' as const };

const categoryAxis = (categories: string[], plotLines?: any[], title = 'Strike'): Options['xAxis'] => ({
  categories,
  title: { text: title, style: axisTitleStyle },
  crosshair: { className: 'highcharts-crosshair-x', snap: true },
  tickLength: 0,
  lineWidth: 1,
  labels: { style: axisLabelStyle },
  plotLines,
});

const valueAxis = (formatter: (value: number) => string, title: string, plotLines?: any[]): Options['yAxis'] => ({
  opposite: true,
  title: { text: title, align: 'high', rotation: 0, offset: 0, y: -7, style: axisTitleStyle },
  tickLength: 0,
  lineWidth: 0,
  gridLineWidth: 1,
  plotLines,
  labels: {
    style: axisLabelStyle,
    formatter: function () {
      const value = typeof this.value === 'number' ? this.value : Number(this.value);
      return Number.isFinite(value) ? formatter(value) : String(this.value);
    },
  },
});

const base = (title: string, className = ''): Options => ({
  chart: {
    backgroundColor: 'transparent',
    className: ['hype-chart', className].filter(Boolean).join(' '),
    styledMode: true,
    animation: false,
    spacingTop: 13,
    spacingRight: 24,
    spacingBottom: 38,
    spacingLeft: 8,
  },
  title: { text: title, align: 'left', x: 8, y: 15 },
  credits: { enabled: false },
  exporting: { enabled: false },
  legend: {
    layout: 'horizontal',
    align: 'left',
    verticalAlign: 'bottom',
    itemStyle: { fontWeight: '200' },
    symbolRadius: 0,
    symbolHeight: 7,
    symbolWidth: 14,
    x: 2,
  },
  plotOptions: {
    series: {
      animation: { duration: 0 },
      states: { hover: { enabled: true, lineWidthPlus: 0, halo: { size: 3, opacity: 0.18 } } },
    },
    line: { marker: { symbol: 'circle', radius: 1.8, states: { hover: { radius: 3 } } }, lineWidth: 1.8 },
    spline: { marker: { symbol: 'circle', enabled: true, radius: 1.8, states: { hover: { radius: 3 } } }, lineWidth: 1.8 },
    column: { borderRadius: 0, pointPadding: 0.16, groupPadding: 0.08, borderWidth: 0 },
  },
});

const percentAxis = (value: number) => `${formatCompact(value, 1)}%`;
const compactAxis = (value: number) => formatCompact(value);

const header = (label: string) => `<tspan class="highcharts-header tooltip-date">${escapeSvgText(label)}</tspan>`;

const tooltipLabel = (context: any) => String(
  context?.point?.custom?.xLabel
    ?? context?.points?.[0]?.point?.custom?.xLabel
    ?? context?.point?.category
    ?? context?.points?.[0]?.point?.category
    ?? context?.key
    ?? context?.x
    ?? ''
);
const categoryLabel = tooltipLabel;

const pointWithLabel = (xLabel: string, y: number | null, custom: Record<string, unknown> = {}) => ({
  y,
  custom: { xLabel, ...custom },
}) as any;

const sharedSeriesTooltip = (
  unit: 'contracts' | 'gex',
  valueLabel: string,
  totalLabel: string,
  includeZero = false
): Options['tooltip'] => ({
  className: 'highcharts-tooltip',
  borderRadius: 2,
  animation: false,
  shared: true,
  useHTML: false,
  formatter: function () {
    const points = (this.points ?? [this])
      .filter((point: any) => typeof point.y === 'number' && (includeZero || point.y !== 0))
      .sort((left: any, right: any) => Math.abs(right.y) - Math.abs(left.y));
    const visible = points.slice(0, MULTI_SERIES_TOOLTIP_LIMIT);
    const hidden = points.length - visible.length;
    const total = points.reduce((sum: number, point: any) => sum + point.y, 0);
    const lines = visible.map((point: any) => {
      const colorClass = String(point.series?.colorIndex ?? point.point?.colorIndex ?? '0');
      return pointLine(colorClass, `${point.series.name}: ${formatChartValue(unit, point.y)}`);
    });
    if (points.length > 1) lines.push(mutedLine(`${totalLabel}: ${formatChartValue(unit, total)}`));
    if (hidden > 0) lines.push(mutedLine(`+${hidden} more ${valueLabel}`));
    return [header(`${tooltipLabel(this)} · ${valueLabel}`), ...lines].join(br);
  },
});

const nearestStrikeIndex = (rows: Array<{ strike: number }>, target: number | null | undefined) => {
  if (target == null || rows.length === 0) return -1;
  let bestIndex = 0;
  for (let index = 1; index < rows.length; index += 1) {
    if (Math.abs(rows[index].strike - target) < Math.abs(rows[bestIndex].strike - target)) bestIndex = index;
  }
  return bestIndex;
};

const atmPlotLine = (rows: Array<{ strike: number }>, atmStrike: number | null | undefined): any[] | undefined => {
  const index = nearestStrikeIndex(rows, atmStrike);
  if (index < 0 || atmStrike == null) return undefined;
  return [{
    value: index,
    width: 1,
    zIndex: 5,
    dashStyle: 'Dash',
    className: 'atm-plot-line',
    label: {
      text: `ATM ${formatStrike(atmStrike)}`,
      rotation: 0,
      align: 'left',
      x: 4,
      y: 13,
      style: { fontSize: '0.72rem', fontWeight: '300' },
    },
  }];
};

const linePointTooltip = (unitFormatter: (value: number) => string) => tooltip(function () {
  const colorClass = this.point?.colorIndex ?? this.series?.colorIndex ?? '0';
  const label = categoryLabel(this);
  const value = typeof this.y === 'number' ? unitFormatter(this.y) : '-';
  return `${header(label)}${br}${pointLine(String(colorClass), `${this.series.name}: ${value}`)}`;
});

export const termStructureOption = (rows: AtmTerm[]): Options => ({
  ...base('ATM IV Term Structure', 'term-structure-chart'),
  xAxis: categoryAxis(rows.map((row) => row.tenor), undefined, 'DTE'),
  yAxis: valueAxis(percentAxis, 'IV (%)'),
  tooltip: linePointTooltip((value) => formatVol(value / 100)),
  series: asSeries([
    { type: 'spline', name: 'ATM', data: rows.map((row) => pointWithLabel(row.tenor, pct(row.atmIv))), threshold: null, colorIndex: 0 },
  ]),
});

export const ivSmileOption = (rows: IvSmilePoint[], expiry: string, atmStrike: number | null | undefined): Options => {
  const labels = strikeLabels(rows);
  const putWing = rows.map((row) => pointWithLabel(formatStrike(row.strike), atmStrike == null || row.strike <= atmStrike ? pct(row.putIv) : null, { strike: row.strike }));
  const callWing = rows.map((row) => pointWithLabel(formatStrike(row.strike), atmStrike == null || row.strike >= atmStrike ? pct(row.callIv) : null, { strike: row.strike }));
  return {
    ...base(`OTM IV Smile | ${formatExpiry(expiry)}`, 'iv-smile-chart'),
    xAxis: categoryAxis(labels, atmPlotLine(rows, atmStrike), 'Strike'),
    yAxis: valueAxis(percentAxis, 'IV (%)'),
    tooltip: linePointTooltip((value) => formatVol(value / 100)),
    series: asSeries([
      { type: 'spline', name: 'Put Wing IV', data: putWing, threshold: null, connectNulls: false, className: 'series-put', colorIndex: 1 },
      { type: 'spline', name: 'Call Wing IV', data: callWing, threshold: null, connectNulls: false, className: 'series-call', colorIndex: 2 },
    ]),
  };
};

export const gexByStrikeOption = (rows: GexPoint[], atmStrike: number | null | undefined): Options => ({
  ...base('GEX by Strike | All Expiries', 'gex-chart'),
  legend: { enabled: false },
  xAxis: categoryAxis(strikeLabels(rows), atmPlotLine(rows, atmStrike), 'Strike'),
  yAxis: valueAxis(compactAxis, 'Net GEX', [{ width: 1, value: 0, zIndex: 4, className: 'zero-plot-line' }]),
  tooltip: tooltip(function () {
    return `${header(tooltipLabel(this))}${br}${pointLine(String(this.point?.colorIndex ?? '0'), `Net GEX: ${formatGex(this.point?.y ?? this.y)}`)}`;
  }),
  series: asSeries([
    {
      type: 'column',
      name: 'Net GEX',
      data: rows.map((row) => ({
        ...pointWithLabel(formatStrike(row.strike), row.netGex, { strike: row.strike }),
        colorIndex: row.netGex >= 0 ? 'green' : 'red',
      }) as any),
    },
  ]),
});

export const gexByExpiryOption = (rows: GexExpiryPoint[], atmStrike: number | null | undefined): Options => {
  const strikes = Array.from(new Set(rows.map((row) => row.strike))).sort((a, b) => a - b);
  const expiries = sortExpiries(rows.map((row) => row.expiry));
  const strikeRows = strikes.map((strike) => ({ strike }));
  const option: Options = {
    ...base('GEX by Expiry | Strike Distribution', 'gex-expiry-chart'),
    xAxis: categoryAxis(strikeRows.map((row) => formatStrike(row.strike)), atmPlotLine(strikeRows, atmStrike), 'Strike'),
    yAxis: valueAxis(compactAxis, 'Net GEX', [{ width: 1, value: 0, zIndex: 4, className: 'zero-plot-line' }]),
    tooltip: sharedSeriesTooltip('gex', 'expiry GEX', 'Net total'),
    plotOptions: {
      ...base('').plotOptions,
      column: { stacking: 'normal', borderRadius: 0, pointPadding: 0.1, groupPadding: 0.05, borderWidth: 0 },
    },
    series: asSeries(
      expiries.map((expiry) => {
        const byStrike = new Map(rows.filter((row) => row.expiry === expiry).map((row) => [row.strike, row.netGex]));
        return {
          type: 'column',
          name: formatExpiry(expiry),
          data: strikes.map((strike) => pointWithLabel(formatStrike(strike), byStrike.get(strike) ?? null, { strike, expiry })),
          colorIndex: expiryColorIndex(expiry),
        } as any;
      })
    ),
  };
  return option;
};

export const oiByStrikeOption = (rows: OiStrikePoint[], side: 'total' | 'call' | 'put', atmStrike: number | null | undefined): Options => {
  const strikes = Array.from(new Set(rows.map((row) => row.strike))).sort((a, b) => a - b);
  const expiries = sortExpiries(rows.map((row) => row.expiry));
  const strikeRows = strikes.map((strike) => ({ strike }));
  const valueLabel = side === 'call' ? 'Call OI' : side === 'put' ? 'Put OI' : 'Total OI';
  const valueForSide = (row: OiStrikePoint) => side === 'call' ? row.callOi : side === 'put' ? row.putOi : row.totalOi;
  const option: Options = {
    ...base(`OI by Strike | ${valueLabel} (contracts)`, 'oi-strike-chart'),
    xAxis: categoryAxis(strikeRows.map((row) => formatStrike(row.strike)), atmPlotLine(strikeRows, atmStrike), 'Strike'),
    yAxis: valueAxis(compactAxis, 'Contracts'),
    tooltip: sharedSeriesTooltip('contracts', `${valueLabel} by expiry`, 'Total OI'),
    plotOptions: {
      ...base('').plotOptions,
      column: { stacking: 'normal', borderRadius: 0, pointPadding: 0.1, groupPadding: 0.05, borderWidth: 0 },
    },
    series: asSeries(
      expiries.map((expiry) => {
        const byStrike = new Map(rows.filter((row) => row.expiry === expiry).map((row) => [row.strike, valueForSide(row)]));
        return {
          type: 'column',
          name: formatExpiry(expiry),
          data: strikes.map((strike) => pointWithLabel(formatStrike(strike), byStrike.get(strike) ?? null, { strike, expiry })),
          colorIndex: expiryColorIndex(expiry),
        } as any;
      })
    ),
  };
  return option;
};

export const oiByExpiryOption = (rows: OiExpiry[], side: 'total' | 'call' | 'put'): Options => ({
  ...base('OI by Expiry (contracts)', 'oi-expiry-chart'),
  chart: {
    ...base('', 'oi-expiry-chart').chart,
    spacingBottom: 58,
  },
  legend: { enabled: false },
  xAxis: {
    ...categoryAxis(rows.map((row) => formatExpiry(row.expiry)), undefined, 'Expiry'),
    labels: { style: axisLabelStyle, rotation: -35, align: 'right', y: 18, reserveSpace: true },
  },
  yAxis: valueAxis(compactAxis, 'Contracts'),
  tooltip: tooltip(function () {
    const value = typeof this.point?.y === 'number' ? this.point.y : this.y;
    const colorClass = side === 'call' ? 'green' : side === 'put' ? 'red' : '0';
    return `${header(tooltipLabel(this))}${br}${pointLine(colorClass, `${side.toUpperCase()} OI: ${formatContracts(value)}`)}`;
  }),
  series: asSeries([
    {
      type: 'column',
      name: `${side.toUpperCase()} OI`,
      data: rows.map((row) => pointWithLabel(
        formatExpiry(row.expiry),
        side === 'call' ? row.callOi : side === 'put' ? row.putOi : row.totalOi,
        { expiry: row.expiry }
      )),
      colorIndex: (side === 'call' ? 'green' : side === 'put' ? 'red' : 0) as any,
    },
  ]),
});
