import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type UTCTimestamp,
  type WhitespaceData,
} from 'lightweight-charts';
import type { AssetChartData, ChartCandleInterval } from '@/lib/types';
import { CHART_INTERVAL_OPTIONS } from '@/lib/chart';
import { cn } from '@/lib/utils';
import { MousePointer2, Move } from 'lucide-react';

interface InteractiveChartProps {
  data: AssetChartData;
  interval: ChartCandleInterval;
  onIntervalChange: (interval: ChartCandleInterval) => void;
  selectedPrice: number | null;
  selectedDate: string | null;
  onSelectTarget: (price: number, dateStr: string) => void;
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

function toUtcTimestamp(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

function getIntervalSeconds(interval: string): number {
  if (interval === '15m') return 15 * 60;
  if (interval === '1h') return 3600;
  if (interval === '4h') return 4 * 3600;
  if (interval === '1d') return 24 * 3600;
  return 24 * 3600;
}

export function InteractiveChart({
  data,
  interval,
  onIntervalChange,
  selectedPrice,
  onSelectTarget,
  refetching = false,
}: InteractiveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const selectModeRef = useRef(selectMode);

  // Sync ref so the click handler closure gets the latest value
  useEffect(() => {
    selectModeRef.current = selectMode;
  }, [selectMode]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

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

    const series = chart.addSeries(CandlestickSeries, {
      upColor: CANDLE_UP.color,
      downColor: CANDLE_DOWN.color,
      borderUpColor: CANDLE_UP.borderColor,
      borderDownColor: CANDLE_DOWN.borderColor,
      wickUpColor: CANDLE_UP.wickColor,
      wickDownColor: CANDLE_DOWN.wickColor,
    });
    seriesRef.current = series;
    chartRef.current = chart;

    // Click to select
    chart.subscribeClick((param: MouseEventParams) => {
      if (!selectModeRef.current) return;
      if (param.point) {
        const price = series.coordinateToPrice(param.point.y);
        
        let logicalTime: number | null = null;
        if (param.time) {
          logicalTime = param.time as number;
        } else {
          const timeScale = chart.timeScale();
          const time = timeScale.coordinateToTime(param.point.x);
          if (time !== null) {
            logicalTime = time as number;
          }
        }

        if (price !== null && logicalTime !== null) {
          // Convert lightweight-charts timestamp back to ISO date string
          // logicalTime is seconds since epoch for UTCTimestamp
          const dateStr = new Date(logicalTime * 1000).toISOString().split('T')[0];
          onSelectTarget(price, dateStr);
          // Auto-disable select mode after a successful tap for a better mobile experience
          setSelectMode(false);
        }
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      if (container) {
        chart.applyOptions({ width: container.clientWidth });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [onSelectTarget]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const styledCandles = data.ohlc.map((row) => {
      const time = toUtcTimestamp(row.date);
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

    const futureWhitespace: WhitespaceData<UTCTimestamp>[] = [];
    if (styledCandles.length > 0) {
      const lastTime = styledCandles[styledCandles.length - 1].time as number;
      const intervalSecs = getIntervalSeconds(interval);
      // Add 180 days of future data
      const futureBars = Math.floor((180 * 24 * 3600) / intervalSecs);
      
      for (let i = 1; i <= futureBars; i++) {
        futureWhitespace.push({ time: (lastTime + i * intervalSecs) as UTCTimestamp });
      }
    }

    if (styledCandles.length > 0) {
      series.setData([...styledCandles, ...futureWhitespace]);
      chart.timeScale().fitContent();
    }
  }, [data, interval]);

  // Manage target price line
  const priceLineRef = useRef<any>(null);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    if (selectedPrice !== null && !Number.isNaN(selectedPrice)) {
      if (priceLineRef.current) {
        series.removePriceLine(priceLineRef.current);
      }
      priceLineRef.current = series.createPriceLine({
        price: selectedPrice,
        color: '#f59e0b',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: 'Target',
      });
    } else {
      if (priceLineRef.current) {
        series.removePriceLine(priceLineRef.current);
        priceLineRef.current = null;
      }
    }
  }, [selectedPrice]);

  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setSelectMode(!selectMode)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors',
            selectMode 
              ? 'bg-primary text-primary-foreground' 
              : 'bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground'
          )}
        >
          {selectMode ? <MousePointer2 className="size-3.5" /> : <Move className="size-3.5" />}
          {selectMode ? 'Tap chart to select' : 'Pan & Zoom'}
        </button>

        <div className="flex items-center gap-1">
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
      </div>
      <div className={cn('relative h-[320px] overflow-hidden', refetching && 'opacity-90', selectMode && 'cursor-crosshair')}>
        <div ref={containerRef} className="absolute inset-0" />
      </div>
    </div>
  );
}
