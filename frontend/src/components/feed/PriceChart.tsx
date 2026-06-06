import { useCallback, useEffect, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type AutoscaleInfoProvider,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type ITimeScaleApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { ClaimChartData, ChartCandleInterval } from '@/lib/types';
import { CHART_INTERVAL_OPTIONS, claimWindowForChart } from '@/lib/chart';
import { cn } from '@/lib/utils';

interface PriceChartProps {
  data: ClaimChartData;
  interval: ChartCandleInterval;
  onIntervalChange: (interval: ChartCandleInterval) => void;
  refetching?: boolean;
}

const CANDLE_UP = {
  color: '#22c55e',
  borderColor: '#16a34a',
  wickColor: '#16a34a',
} as const;

const CANDLE_DOWN = {
  color: '#f87171',
  borderColor: '#ef4444',
  wickColor: '#ef4444',
} as const;

const CANDLE_OUTSIDE = {
  color: '#475569',
  borderColor: '#334155',
  wickColor: '#334155',
} as const;

const ANCHOR_LINE_COLOR = 'rgba(59, 130, 246, 0.95)';

const CLAIM_MARKER_LABEL_CLASS =
  'absolute top-1.5 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-sm bg-[rgba(59,130,246,0.95)] px-2 py-1 text-[11px] font-medium leading-none text-white shadow-sm';

function toUtcTimestamp(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

function intervalBarDurationSec(interval?: string): number {
  switch (interval) {
    case '15m':
      return 15 * 60;
    case '1h':
      return 3600;
    case '1d':
      return 86400;
    default:
      return 4 * 3600;
  }
}

function barDurationSec(
  candles: CandlestickData<UTCTimestamp>[],
  chartInterval?: string,
): number {
  if (candles.length > 1) {
    return (candles[1].time as number) - (candles[0].time as number);
  }
  return intervalBarDurationSec(chartInterval);
}

function barWidthPx(
  timeScale: ITimeScaleApi<Time>,
  candles: CandlestickData<UTCTimestamp>[],
): number {
  if (candles.length >= 2) {
    const x0 = timeScale.timeToCoordinate(candles[0].time);
    const x1 = timeScale.timeToCoordinate(candles[1].time);
    if (x0 !== null && x1 !== null) return x1 - x0;
  }
  return timeScale.options().barSpacing;
}

/** Map any timestamp to an x-coordinate, interpolating between bar opens. */
function timeToPlotCoordinate(
  timeScale: ITimeScaleApi<Time>,
  time: UTCTimestamp,
  candles: CandlestickData<UTCTimestamp>[],
  chartInterval?: string,
): number | null {
  const direct = timeScale.timeToCoordinate(time);
  if (direct !== null) return direct;
  if (candles.length === 0) return null;

  const t = time as number;
  const firstTime = candles[0].time as number;
  const lastTime = candles[candles.length - 1].time as number;
  const barSec = barDurationSec(candles, chartInterval);
  const barPx = barWidthPx(timeScale, candles);

  if (t <= firstTime) {
    const anchor = timeScale.timeToCoordinate(candles[0].time);
    if (anchor === null) return null;
    return anchor - ((firstTime - t) / barSec) * barPx;
  }

  if (t >= lastTime) {
    const anchor = timeScale.timeToCoordinate(candles[candles.length - 1].time);
    if (anchor === null) return null;
    return anchor + ((t - lastTime) / barSec) * barPx;
  }

  for (let i = 0; i < candles.length - 1; i += 1) {
    const t0 = candles[i].time as number;
    const t1 = candles[i + 1].time as number;
    if (t < t0 || t > t1) continue;

    const x0 = timeScale.timeToCoordinate(candles[i].time);
    const x1 = timeScale.timeToCoordinate(candles[i + 1].time);
    if (x0 === null || x1 === null) return null;
    const ratio = (t - t0) / (t1 - t0);
    return x0 + ratio * (x1 - x0);
  }

  return null;
}

/** Logical bar index for any timestamp; extrapolates before first / after last candle. */
function timeToLogicalIndex(
  timeScale: ITimeScaleApi<Time>,
  time: UTCTimestamp,
  candles: CandlestickData<UTCTimestamp>[],
  chartInterval?: string,
): number | null {
  const exact = timeScale.timeToIndex(time, false);
  if (exact !== null) return exact as number;
  if (candles.length === 0) return null;

  const barSec = barDurationSec(candles, chartInterval);
  const firstTime = candles[0].time as number;
  const lastTime = candles[candles.length - 1].time as number;
  const firstIdx = timeScale.timeToIndex(candles[0].time, false);
  const lastIdx = timeScale.timeToIndex(candles[candles.length - 1].time, false);
  if (firstIdx === null || lastIdx === null) return null;

  const t = time as number;
  if (t <= firstTime) {
    return (firstIdx as number) - (firstTime - t) / barSec;
  }
  if (t >= lastTime) {
    return (lastIdx as number) + (t - lastTime) / barSec;
  }

  const nearest = timeScale.timeToIndex(time, true);
  return nearest !== null ? (nearest as number) : null;
}

function isInClaimWindow(
  candleTime: UTCTimestamp,
  windowStart: UTCTimestamp,
  windowEnd: UTCTimestamp,
): boolean {
  const t = candleTime as number;
  return t >= (windowStart as number) && t <= (windowEnd as number);
}

function toStyledCandles(
  data: ClaimChartData,
  windowStart: UTCTimestamp,
  windowEnd: UTCTimestamp,
): CandlestickData<UTCTimestamp>[] {
  return data.ohlc.map((row) => {
    const time = toUtcTimestamp(row.date);
    const inWindow = isInClaimWindow(time, windowStart, windowEnd);
    if (!inWindow) {
      return { time, open: row.open, high: row.high, low: row.low, close: row.close, ...CANDLE_OUTSIDE };
    }
    const up = row.close >= row.open;
    return {
      time,
      open: row.open,
      high: row.high,
      low: row.low,
      close: row.close,
      ...(up ? CANDLE_UP : CANDLE_DOWN),
    };
  });
}

function computeAutoscaleRange(
  data: ClaimChartData,
  windowStart: UTCTimestamp,
  windowEnd: UTCTimestamp,
) {
  const windowRows = data.ohlc.filter((row) => {
    const t = toUtcTimestamp(row.date) as number;
    return t >= (windowStart as number) && t <= (windowEnd as number);
  });
  const rows = windowRows.length > 0 ? windowRows : data.ohlc;
  const ohlcValues = rows.flatMap((c) => [c.open, c.high, c.low, c.close]);

  const anchors: number[] = [];
  if (typeof data.reference_price === 'number' && !Number.isNaN(data.reference_price)) {
    anchors.push(data.reference_price);
  }
  if (typeof data.target_price === 'number' && !Number.isNaN(data.target_price)) {
    anchors.push(data.target_price);
  }

  // Always frame entry + target together; include in-window OHLC so candles aren't clipped.
  const all = [...ohlcValues, ...anchors];
  if (all.length === 0) return null;

  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || max * 0.02;
  const padding = span * 0.12;

  return {
    priceRange: {
      minValue: min - padding,
      maxValue: max + padding,
    },
    margins: {
      above: 12,
      below: 12,
    },
  };
}

function focusClaimWindow(
  chart: IChartApi,
  windowStart: UTCTimestamp,
  windowEnd: UTCTimestamp | null,
  candles: CandlestickData<UTCTimestamp>[],
  chartInterval?: string,
) {
  const timeScale = chart.timeScale();
  const startIdx = timeToLogicalIndex(timeScale, windowStart, candles, chartInterval);
  let endIdx =
    windowEnd !== null
      ? timeToLogicalIndex(timeScale, windowEnd, candles, chartInterval)
      : null;

  if (endIdx === null && candles.length > 0) {
    endIdx = timeScale.timeToIndex(candles[candles.length - 1].time, false) as number | null;
  }

  if (startIdx === null || endIdx === null) {
    timeScale.fitContent();
    return;
  }

  const windowFrom = Math.min(startIdx, endIdx);
  const windowTo = Math.max(startIdx, endIdx);
  const windowBars = Math.max(windowTo - windowFrom, 1);
  
  // To keep the start line at 1/10th of the screen, left padding is 10% of total visible bars.
  // We cap total visible bars to 400 to prevent hitting the chart's max zoom out limit.
  const minBars = chartInterval === '15m' ? 60 : chartInterval === '1d' ? 14 : 30;
  const maxBars = 400; 
  
  let visibleBars = Math.max(windowBars / 0.8, minBars);
  if (visibleBars > maxBars) {
    visibleBars = maxBars;
  }
  
  const leftPadding = visibleBars * 0.1;
  const from = windowFrom - leftPadding;
  const to = from + visibleBars;

  timeScale.applyOptions({ rightOffset: 0 });
  timeScale.setVisibleLogicalRange({ from, to });
}

export function PriceChart({
  data,
  interval,
  onIntervalChange,
  refetching = false,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const startMarkerRef = useRef<HTMLDivElement>(null);
  const endMarkerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const candlesRef = useRef<CandlestickData<UTCTimestamp>[]>([]);
  const shouldRefocusRef = useRef(true);
  const prevDataIntervalRef = useRef(data.interval);

  const alignedWindow = claimWindowForChart(data.created_at, data.until, interval);
  const windowStart = alignedWindow.start as UTCTimestamp;
  const claimWindowEnd = alignedWindow.end as UTCTimestamp;

  const updateOverlay = useCallback(() => {
    const chart = chartRef.current;
    const overlay = overlayRef.current;
    const startMarker = startMarkerRef.current;
    const endMarker = endMarkerRef.current;
    const candles = candlesRef.current;
    if (!chart || !overlay || !startMarker || !endMarker) return;

    const windowEnd = claimWindowEnd as UTCTimestamp;

    const timeScale = chart.timeScale();
    const startX = timeToPlotCoordinate(timeScale, windowStart, candles, interval);
    const endX =
      windowEnd !== null
        ? timeToPlotCoordinate(timeScale, windowEnd, candles, interval)
        : null;

    if (startX === null && endX === null) {
      overlay.style.display = 'none';
      return;
    }

    overlay.style.display = 'block';

    const plotWidth = overlay.clientWidth;
    const showAt = (x: number | null) => x !== null && x >= 0 && x <= plotWidth;

    startMarker.style.display = showAt(startX) ? 'block' : 'none';
    endMarker.style.display = showAt(endX) ? 'block' : 'none';
    if (startX !== null && showAt(startX)) startMarker.style.left = `${startX}px`;
    if (endX !== null && showAt(endX)) endMarker.style.left = `${endX}px`;
  }, [windowStart, claimWindowEnd, interval]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    shouldRefocusRef.current = true;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.06)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.06)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(99, 102, 241, 0.35)', labelBackgroundColor: '#334155' },
        horzLine: { color: 'rgba(99, 102, 241, 0.35)', labelBackgroundColor: '#334155' },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.12 },
        autoScale: true,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      width: container.clientWidth,
      height: 320,
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });

    const autoscaleRange = computeAutoscaleRange(data, windowStart, claimWindowEnd);

    const series = chart.addSeries(CandlestickSeries, {
      upColor: CANDLE_UP.color,
      downColor: CANDLE_DOWN.color,
      borderUpColor: CANDLE_UP.borderColor,
      borderDownColor: CANDLE_DOWN.borderColor,
      wickUpColor: CANDLE_UP.wickColor,
      wickDownColor: CANDLE_DOWN.wickColor,
      autoscaleInfoProvider: autoscaleRange
        ? () => autoscaleRange
        : ((original: Parameters<AutoscaleInfoProvider>[0]) => original()),
    });
    seriesRef.current = series;

    if (data.reference_price != null && !Number.isNaN(data.reference_price)) {
      series.createPriceLine({
        price: data.reference_price,
        color: ANCHOR_LINE_COLOR,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'Entry',
      });
    }

    if (data.target_price != null && !Number.isNaN(data.target_price)) {
      series.createPriceLine({
        price: data.target_price,
        color: ANCHOR_LINE_COLOR,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'Target',
      });
    }

    chartRef.current = chart;

    const onRangeChange = () => updateOverlay();
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRangeChange);
    chart.timeScale().subscribeVisibleTimeRangeChange(onRangeChange);

    const resizeObserver = new ResizeObserver(() => {
      if (container) {
        chart.applyOptions({ width: container.clientWidth });
        updateOverlay();
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRangeChange);
      chart.timeScale().unsubscribeVisibleTimeRangeChange(onRangeChange);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      candlesRef.current = [];
    };
  }, [data, interval, updateOverlay, windowStart, claimWindowEnd]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const styledCandles = toStyledCandles(data, windowStart, claimWindowEnd);
    candlesRef.current = styledCandles;
    if (styledCandles.length > 0) {
      series.setData(styledCandles);
    }

    const intervalChanged = prevDataIntervalRef.current !== data.interval;

    if ((shouldRefocusRef.current || intervalChanged) && styledCandles.length > 0) {
      focusClaimWindow(
        chart,
        windowStart,
        claimWindowEnd as UTCTimestamp,
        styledCandles,
        interval,
      );
      shouldRefocusRef.current = false;
      prevDataIntervalRef.current = data.interval;
    }

    chart.priceScale('right').applyOptions({ autoScale: true });
    requestAnimationFrame(() => {
      requestAnimationFrame(updateOverlay);
    });
  }, [data, windowStart, claimWindowEnd, interval, updateOverlay]);

  if (data.ohlc.length === 0) {
    return (
      <div className="mt-4 rounded-lg border bg-card p-3 h-[320px] flex items-center justify-center text-sm text-muted-foreground">
        No price data available for this period.
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-lg border bg-card p-3">
      <div className="mb-2 flex items-center justify-end gap-1">
        {CHART_INTERVAL_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onIntervalChange(opt.value)}
            className={cn(
              'rounded-md px-2 py-0.5 text-[10px] font-medium num transition-colors',
              interval === opt.value
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <div className={cn('relative h-[320px] overflow-hidden', refetching && 'opacity-90')}>
        <div ref={containerRef} className="absolute inset-0" />
        <div
          ref={overlayRef}
          className="absolute inset-0 pointer-events-none overflow-hidden z-10"
        >
          <div
            ref={startMarkerRef}
            className="absolute top-0 bottom-[28px] w-0"
            style={{ left: 0, display: 'none' }}
          >
            <span className={CLAIM_MARKER_LABEL_CLASS}>Start</span>
            <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px border-l border-dashed border-blue-400/90" />
          </div>
          <div
            ref={endMarkerRef}
            className="absolute top-0 bottom-[28px] w-0"
            style={{ left: 0, display: 'none' }}
          >
            <span className={CLAIM_MARKER_LABEL_CLASS}>End</span>
            <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px border-l border-dashed border-blue-400/90" />
          </div>
        </div>
      </div>
    </div>
  );
}
