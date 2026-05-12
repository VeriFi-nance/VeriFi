import { useRef, useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  type ChartOptions,
  type Plugin,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { ClaimChartData } from '@/lib/types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface PriceChartProps {
  data: ClaimChartData;
}

export function PriceChart({ data }: PriceChartProps) {
  const chartRef = useRef<ChartJS<'line'>>(null);

  const isBullish = data.direction === 'bullish';
  const hitDaySet = useMemo(() => new Set(data.hit_days), [data.hit_days]);

  const labels = data.ohlc.map((c) =>
    new Date(c.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  );
  const closePrices = data.ohlc.map((c) => c.close);
  const highPrices = data.ohlc.map((c) => c.high);
  const lowPrices = data.ohlc.map((c) => c.low);

  // Determine chart boundaries
  const allValues = [...closePrices, ...highPrices, ...lowPrices, data.target_price, data.reference_price].filter(Boolean);
  const dataMin = Math.min(...allValues);
  const dataMax = Math.max(...allValues);
  const padding = (dataMax - dataMin) * 0.1 || dataMax * 0.05;

  // Target line plugin
  const targetLinePlugin: Plugin<'line'> = useMemo(
    () => ({
      id: 'targetLine',
      afterDraw(chart) {
        if (!data.target_price) return;
        const { ctx, scales } = chart;
        const yScale = scales.y;
        const xScale = scales.x;
        if (!yScale || !xScale) return;

        const yPos = yScale.getPixelForValue(data.target_price);
        const left = xScale.left;
        const right = xScale.right;
        const top = yScale.top;
        const bottom = yScale.bottom;

        // Draw gradient fill for target zone
        ctx.save();

        if (isBullish) {
          // Fill above target line with green gradient (slower, subtler)
          const gradient = ctx.createLinearGradient(0, Math.max(top, yPos - 120), 0, yPos);
          gradient.addColorStop(0, 'rgba(16, 185, 129, 0)');
          gradient.addColorStop(1, 'rgba(16, 185, 129, 0.06)');
          ctx.fillStyle = gradient;
          ctx.fillRect(left, top, right - left, Math.max(0, yPos - top));
        } else {
          // Fill below target line with red gradient (slower, subtler)
          const gradient = ctx.createLinearGradient(0, yPos, 0, Math.min(bottom, yPos + 120));
          gradient.addColorStop(0, 'rgba(239, 68, 68, 0.06)');
          gradient.addColorStop(1, 'rgba(239, 68, 68, 0)');
          ctx.fillStyle = gradient;
          ctx.fillRect(left, yPos, right - left, Math.max(0, bottom - yPos));
        }

        // Draw target dashed line
        ctx.beginPath();
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = isBullish ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)';
        ctx.lineWidth = 1.5;
        ctx.moveTo(left, yPos);
        ctx.lineTo(right, yPos);
        ctx.stroke();

        // Target price label
        ctx.setLineDash([]);
        ctx.font = '10px Inter, system-ui, sans-serif';
        ctx.fillStyle = isBullish ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
        ctx.textAlign = 'right';
        ctx.fillText(`Target: $${data.target_price.toLocaleString()}`, right - 4, yPos - 4);

        ctx.restore();
      },
    }),
    [data.target_price, isBullish]
  );

  // Reference price line plugin
  const refLinePlugin: Plugin<'line'> = useMemo(
    () => ({
      id: 'refLine',
      afterDraw(chart) {
        if (!data.reference_price) return;
        const { ctx, scales } = chart;
        const yScale = scales.y;
        const xScale = scales.x;
        if (!yScale || !xScale) return;

        const yPos = yScale.getPixelForValue(data.reference_price);

        ctx.save();
        ctx.beginPath();
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
        ctx.lineWidth = 1;
        ctx.moveTo(xScale.left, yPos);
        ctx.lineTo(xScale.right, yPos);
        ctx.stroke();

        ctx.setLineDash([]);
        ctx.font = '10px Inter, system-ui, sans-serif';
        ctx.fillStyle = 'rgb(148, 163, 184)';
        ctx.textAlign = 'left';
        ctx.fillText(`Ref: $${data.reference_price.toLocaleString()}`, xScale.left + 4, yPos - 4);
        ctx.restore();
      },
    }),
    [data.reference_price]
  );

  const chartData = useMemo(() => {
    // Build segment coloring: thicker + brighter on hit days
    const segmentBorderColor = (ctx: any) => {
      const idx = ctx.p1DataIndex;
      const dateStr = data.ohlc[idx]?.date;
      if (dateStr && hitDaySet.has(dateStr)) {
        return isBullish ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
      }
      return 'rgb(99, 102, 241)';
    };

    const segmentBorderWidth = (ctx: any) => {
      const idx = ctx.p1DataIndex;
      const dateStr = data.ohlc[idx]?.date;
      if (dateStr && hitDaySet.has(dateStr)) {
        return 3.5;
      }
      return 1.5;
    };

    return {
      labels,
      datasets: [
        {
          label: 'High Price',
          data: highPrices,
          borderColor: 'rgb(99, 102, 241)',
          backgroundColor: 'rgba(99, 102, 241, 0.05)',
          borderWidth: 1.5,
          pointRadius: highPrices.map((_, i) => {
            const dateStr = data.ohlc[i]?.date;
            return dateStr && hitDaySet.has(dateStr) ? 4 : 1.5;
          }),
          pointBackgroundColor: highPrices.map((_, i) => {
            const dateStr = data.ohlc[i]?.date;
            if (dateStr && hitDaySet.has(dateStr)) {
              return isBullish ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
            }
            return 'rgb(99, 102, 241)';
          }),
          pointBorderColor: highPrices.map((_, i) => {
            const dateStr = data.ohlc[i]?.date;
            if (dateStr && hitDaySet.has(dateStr)) {
              return isBullish ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
            }
            return 'rgb(99, 102, 241)';
          }),
          pointHoverRadius: 5,
          tension: 0.3,
          fill: false,
          segment: {
            borderColor: segmentBorderColor,
            borderWidth: segmentBorderWidth,
          },
        },
        // Close-to-High as a subtle range band
        {
          label: 'Close',
          data: closePrices,
          borderColor: 'rgba(148, 163, 184, 0.25)',
          borderWidth: 0,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: '+1',
          backgroundColor: 'rgba(99, 102, 241, 0.04)',
          tension: 0.3,
        },
        {
          label: 'Low',
          data: lowPrices,
          borderColor: 'rgba(148, 163, 184, 0.25)',
          borderWidth: 0,
          pointRadius: 0,
          pointHoverRadius: 0,
          fill: false,
          tension: 0.3,
        },
      ],
    };
  }, [labels, highPrices, lowPrices, data.ohlc, hitDaySet, isBullish]);

  const options: ChartOptions<'line'> = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.9)',
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          borderColor: 'rgba(99, 102, 241, 0.3)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          titleFont: { size: 11 },
          bodyFont: { size: 11 },
          callbacks: {
            title(items) {
              const idx = items[0]?.dataIndex;
              if (idx === undefined) return '';
              const d = data.ohlc[idx];
              if (!d) return '';
              const isHit = hitDaySet.has(d.date);
              const dateStr = new Date(d.date).toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
              });
              return isHit ? `${dateStr}  🎯 TARGET HIT` : dateStr;
            },
            label(ctx) {
              const idx = ctx.dataIndex;
              const d = data.ohlc[idx];
              if (!d) return '';
              if (ctx.datasetIndex === 0) {
                return [
                  `Open:  $${d.open.toLocaleString()}`,
                  `High:  $${d.high.toLocaleString()}`,
                  `Low:   $${d.low.toLocaleString()}`,
                  `Close: $${d.close.toLocaleString()}`,
                ];
              }
              return '';
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(148, 163, 184, 0.08)' },
          ticks: {
            color: 'rgb(148, 163, 184)',
            font: { size: 10 },
            maxRotation: 45,
            autoSkip: true,
            maxTicksLimit: 12,
          },
        },
        y: {
          min: dataMin - padding,
          max: dataMax + padding,
          grid: { color: 'rgba(148, 163, 184, 0.08)' },
          ticks: {
            color: 'rgb(148, 163, 184)',
            font: { size: 10 },
            callback: (value) => `$${Number(value).toLocaleString()}`,
          },
        },
      },
    }),
    [data.ohlc, hitDaySet, dataMin, dataMax, padding]
  );

  return (
    <div className="mt-4 rounded-lg border bg-card p-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Price History
        </h4>
        {data.hit_days.length > 0 && (
          <span className="text-[10px] text-emerald-500 font-medium">
            🎯 Target hit on {data.hit_days.length} day{data.hit_days.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
      <div className="h-[220px]">
        <Line ref={chartRef} data={chartData} options={options} plugins={[targetLinePlugin, refLinePlugin]} />
      </div>
    </div>
  );
}
