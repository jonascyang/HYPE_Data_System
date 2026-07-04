import type { Options, SeriesOptionsType } from 'highcharts';
import type { AtmTerm, GexExpiryPoint, GexPoint, IvSmilePoint, OiExpiry, OiStrikePoint } from '../types';
import { formatCompact, formatContracts, formatExpiry, formatGex, formatStrike, formatVol } from '../format';
import { formatChartValue, MULTI_SERIES_TOOLTIP_LIMIT, sortExpiries } from '../display';

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
  title: { text: title, style: axisTitleStyle, margin: 5 },
  crosshair: { className: 'highcharts-crosshair-x', snap: true },
  tickLength: 0,
  lineWidth: 1,
  labels: { style: axisLabelStyle, y: 14 },
  plotLines,
});

const valueAxis = (formatter: (value: number) => string, _title: string, plotLines?: any[]): Options['yAxis'] => ({
  opposite: true,
  title: { text: '' },
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
    spacingTop: 8,
    spacingRight: 14,
    spacingBottom: 12,
    spacingLeft: 4,
  },
  title: { text: title, align: 'left', x: 8, y: 14 },
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

const expiryLegend: Options['legend'] = {
  layout: 'vertical',
  align: 'right',
  verticalAlign: 'middle',
  floating: false,
  symbolRadius: 0,
  symbolHeight: 7,
  symbolWidth: 12,
  itemMarginTop: 1,
  itemMarginBottom: 1,
  padding: 0,
  x: 2,
  y: 10,
  itemStyle: { fontWeight: '200', fontSize: '0.62rem' },
};

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

const strikeNavigator = (values: Array<number | null | undefined>): Pick<Options, 'navigator' | 'scrollbar' | 'rangeSelector'> => ({
  rangeSelector: { enabled: false },
  scrollbar: { enabled: false },
  navigator: {
    enabled: true,
    baseSeries: '__hype_navigator_data__',
    adaptToUpdatedData: true,
    height: 20,
    margin: 4,
    maskInside: false,
    outlineWidth: 1,
    handles: {
      enabled: true,
      width: 8,
      height: 16,
      borderRadius: 0,
    },
    series: {
      type: 'areaspline',
      data: values.map((value, index) => [index, value ?? 0]),
      dataGrouping: { enabled: false },
      lineWidth: 1,
      fillOpacity: 0.08,
      marker: { enabled: false },
      enableMouseTracking: false,
    } as any,
    xAxis: {
      labels: { enabled: false },
      tickLength: 0,
      lineWidth: 0,
      gridLineWidth: 0,
    },
    yAxis: {
      labels: { enabled: false },
      gridLineWidth: 0,
      title: { text: '' },
    },
  },
});

export const termStructureOption = (rows: AtmTerm[]): Options => ({
  ...base('ATM IV Term Structure', 'term-structure-chart'),
  legend: { enabled: false },
  xAxis: categoryAxis(rows.map((row) => row.tenor), undefined, 'DTE'),
  yAxis: valueAxis(percentAxis, 'IV (%)'),
  tooltip: linePointTooltip((value) => formatVol(value / 100)),
  series: asSeries([
    { type: 'spline', name: 'ATM', data: rows.map((row) => pointWithLabel(row.tenor, pct(row.atmIv))), threshold: null, colorIndex: 0 },
  ]),
});

export const ivSmileOption = (rows: IvSmilePoint[], expiry: string, atmStrike: number | null | undefined): Options => {
  const labels = strikeLabels(rows);
  const atmIndex = nearestStrikeIndex(rows, atmStrike);
  const smile = rows.map((row, index) => pointWithLabel(formatStrike(row.strike), pct(atmSmileIv(row, atmStrike, index === atmIndex)), { strike: row.strike }));
  return {
    ...base(`ATM IV Smile | ${formatExpiry(expiry)}`, 'iv-smile-chart'),
    legend: { enabled: false },
    xAxis: categoryAxis(labels, atmPlotLine(rows, atmStrike), 'Strike'),
    yAxis: valueAxis(percentAxis, 'IV (%)'),
    tooltip: linePointTooltip((value) => formatVol(value / 100)),
    series: asSeries([
      { type: 'spline', name: 'ATM Smile IV', data: smile, threshold: null, connectNulls: false, className: 'series-atm-smile', colorIndex: 0 },
    ]),
  };
};

const atmSmileIv = (row: IvSmilePoint, atmStrike: number | null | undefined, isNearestAtm: boolean) => {
  if (isNearestAtm || atmStrike == null || row.strike === atmStrike) return averageAvailable(row.callIv, row.putIv);
  if (row.strike < atmStrike) return row.putIv ?? row.callIv;
  return row.callIv ?? row.putIv;
};

const averageAvailable = (left: number | null | undefined, right: number | null | undefined) => {
  if (left != null && right != null) return (left + right) / 2;
  return left ?? right ?? null;
};

export const gexByStrikeOption = (rows: GexPoint[], atmStrike: number | null | undefined): Options => ({
  ...base('GEX by Strike | All Expiries', 'gex-chart'),
  ...strikeNavigator(rows.map((row) => row.netGex)),
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
    legend: expiryLegend,
    xAxis: categoryAxis(strikeRows.map((row) => formatStrike(row.strike)), atmPlotLine(strikeRows, atmStrike), 'Strike'),
    yAxis: valueAxis(compactAxis, 'Net GEX', [{ width: 1, value: 0, zIndex: 4, className: 'zero-plot-line' }]),
    tooltip: sharedSeriesTooltip('gex', 'expiry GEX', 'Net total'),
    plotOptions: {
      ...base('').plotOptions,
      column: { stacking: 'normal', borderRadius: 0, pointPadding: 0.1, groupPadding: 0.05, borderWidth: 0 },
    },
    series: asSeries(
      expiries.map((expiry, expiryIndex) => {
        const byStrike = new Map(rows.filter((row) => row.expiry === expiry).map((row) => [row.strike, row.netGex]));
        return {
          type: 'column',
          name: formatExpiry(expiry),
          data: strikes.map((strike) => pointWithLabel(formatStrike(strike), byStrike.get(strike) ?? null, { strike, expiry })),
          colorIndex: expiryIndex % 12,
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
    legend: expiryLegend,
    xAxis: categoryAxis(strikeRows.map((row) => formatStrike(row.strike)), atmPlotLine(strikeRows, atmStrike), 'Strike'),
    yAxis: valueAxis(compactAxis, 'Contracts'),
    tooltip: sharedSeriesTooltip('contracts', `${valueLabel} by expiry`, 'Total OI'),
    plotOptions: {
      ...base('').plotOptions,
      column: { stacking: 'normal', borderRadius: 0, pointPadding: 0.1, groupPadding: 0.05, borderWidth: 0 },
    },
    series: asSeries(
      expiries.map((expiry, expiryIndex) => {
        const byStrike = new Map(rows.filter((row) => row.expiry === expiry).map((row) => [row.strike, valueForSide(row)]));
        return {
          type: 'column',
          name: formatExpiry(expiry),
          data: strikes.map((strike) => pointWithLabel(formatStrike(strike), byStrike.get(strike) ?? null, { strike, expiry })),
          colorIndex: expiryIndex % 12,
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
    spacingBottom: 40,
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
