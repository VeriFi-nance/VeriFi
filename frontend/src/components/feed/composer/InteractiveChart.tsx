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
  priceLines?: { price: number; color: string; title: string }[];
  dateLines?: { dateStr: string; color: string; title: string }[];
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
  priceLines = [],
  dateLines = [],
  onSelectTarget,
  refetching = false,
}: InteractiveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const selectModeRef = useRef(selectMode);
  const allTimesRef = useRef<number[]>([]);
  
  const startLineRef = useRef<HTMLDivElement>(null);
  // We will generate vertical lines dynamically
  const dateLineElsRef = useRef<Map<string, HTMLDivElement>>(new Map());

  // Sync refs so the click handler closure gets the latest values without recreating the chart
  useEffect(() => {
    selectModeRef.current = selectMode;
  }, [selectMode]);

  const onSelectTargetRef = useRef(onSelectTarget);
  useEffect(() => {
    onSelectTargetRef.current = onSelectTarget;
  }, [onSelectTarget]);

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
        const timeScale = chart.timeScale();
        const time = timeScale.coordinateToTime(param.point.x);
        
        if (time !== null) {
          if (typeof time === 'object') {
            const b = time as any;
            logicalTime = new Date(Date.UTC(b.year, b.month - 1, b.day)).getTime() / 1000;
          } else if (typeof time === 'string') {
            logicalTime = new Date(time).getTime() / 1000;
          } else {
            logicalTime = time as number;
          }
        }

        if (price !== null && logicalTime !== null) {
          // Convert lightweight-charts timestamp back to ISO date string
          // logicalTime is seconds since epoch for UTCTimestamp
          const dateStr = new Date(logicalTime * 1000).toISOString().split('T')[0];
          onSelectTargetRef.current(price, dateStr);
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
  }, []);

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
      allTimesRef.current = [
        ...styledCandles.map(c => c.time as number),
        ...futureWhitespace.map(w => w.time as number)
      ];
      series.setData([...styledCandles, ...futureWhitespace]);
      chart.timeScale().fitContent();
    }
  }, [data, interval]);

  // Manage target price lines
  const priceLineRefs = useRef<any[]>([]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    // Remove existing lines
    priceLineRefs.current.forEach(line => {
      try { series.removePriceLine(line); } catch (e) {}
    });
    priceLineRefs.current = [];

    if (priceLines && priceLines.length > 0) {
      priceLines.forEach(pl => {
        if (!Number.isNaN(pl.price)) {
          const line = series.createPriceLine({
            price: pl.price,
            color: pl.color,
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: pl.title,
          });
          priceLineRefs.current.push(line);
        }
      });
    }
  }, [priceLines]);

  // Manage time markers (vertical lines via DOM overlays)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    function updateLines() {
      if (!chart) return;
      const timeScale = chart.timeScale();
      
      // Start Line
      if (startLineRef.current && data.ohlc.length > 0) {
        const lastCandleTime = toUtcTimestamp(data.ohlc[data.ohlc.length - 1].date);
        const x = timeScale.timeToCoordinate(lastCandleTime);
        if (x !== null) {
          startLineRef.current.style.left = `${x}px`;
          startLineRef.current.style.display = 'block';
        } else {
          startLineRef.current.style.display = 'none';
        }
      }

      // Target Lines (Dynamic)
      dateLines.forEach((dl) => {
        const el = dateLineElsRef.current.get(dl.title);
        if (el) {
          let targetTime = toUtcTimestamp(dl.dateStr) as number;
          const allTimes = allTimesRef.current;
          if (allTimes.length > 0) {
            targetTime = allTimes.reduce((prev, curr) => 
              Math.abs(curr - targetTime) < Math.abs(prev - targetTime) ? curr : prev
            );
          }
          const x = timeScale.timeToCoordinate(targetTime as UTCTimestamp);
          if (x !== null) {
            el.style.left = `${x}px`;
            el.style.display = 'block';
          } else {
            el.style.display = 'none';
          }
        }
      });
    }

    chart.timeScale().subscribeVisibleTimeRangeChange(updateLines);
    chart.timeScale().subscribeVisibleLogicalRangeChange(updateLines);
    // initial render update
    updateLines();

    return () => {
      chart.timeScale().unsubscribeVisibleTimeRangeChange(updateLines);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(updateLines);
    };
  }, [data.ohlc, dateLines, interval]);

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
        
        {/* Start Vertical Line Overlay */}
        <div 
          ref={startLineRef} 
          className="absolute top-0 bottom-0 w-[2px] bg-indigo-500/40 pointer-events-none hidden z-10" 
          style={{ transform: 'translateX(-50%)' }}
        >
          <div className="absolute top-2 left-2 text-[10px] font-bold text-indigo-500 uppercase tracking-wider bg-background/90 px-1.5 py-0.5 rounded shadow-sm border border-indigo-500/20 whitespace-nowrap">
            Start
          </div>
        </div>

        {/* Dynamic Vertical Line Overlays */}
        {dateLines.map((dl) => (
          <div 
            key={dl.title}
            ref={(el) => {
              if (el) dateLineElsRef.current.set(dl.title, el);
              else dateLineElsRef.current.delete(dl.title);
            }}
            className="absolute top-0 bottom-0 w-[2px] pointer-events-none hidden z-10" 
            style={{ transform: 'translateX(-50%)', backgroundColor: dl.color }}
          >
            <div 
               className="absolute top-8 left-2 text-[10px] font-bold uppercase tracking-wider bg-background/90 px-1.5 py-0.5 rounded shadow-sm border whitespace-nowrap"
               style={{ color: dl.color.replace('/40', ''), borderColor: dl.color.replace('/40', '/20') }}
            >
              {dl.title}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
