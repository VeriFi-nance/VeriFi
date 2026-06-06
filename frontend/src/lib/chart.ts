import type { ChartCandleInterval } from './types';

export type { ChartCandleInterval };

export const CHART_INTERVAL_OPTIONS: { value: ChartCandleInterval; label: string }[] = [
  { value: '15m', label: '15m' },
  { value: '4h', label: '4h' },
  { value: '1d', label: '1d' },
];

export function defaultChartInterval(createdAt: string, until: string): ChartCandleInterval {
  const startMs = new Date(createdAt).getTime();
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(until.trim());
  const endMs = match
    ? Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 23, 59, 59)
    : new Date(until).getTime();
  const windowSec = (endMs - startMs) / 1000;
  if (windowSec < 7 * 86400) return '15m';
  if (windowSec < 30 * 86400) return '4h';
  return '1d';
}

export function isChartCandleInterval(value: string): value is ChartCandleInterval {
  return value === '15m' || value === '4h' || value === '1d';
}

export function chartPollIntervalMs(interval: ChartCandleInterval): number {
  switch (interval) {
    case '15m':
      return 60_000;
    case '4h':
      return 300_000;
    default:
      return 900_000;
  }
}

export function isLiveClaimStatus(status?: string): boolean {
  return status?.toLowerCase() === 'undetermined';
}

/** Floor a UTC instant to the open of its candle bucket for chart overlays. */
export function floorToChartInterval(
  iso: string,
  interval: ChartCandleInterval,
): number {
  const d = new Date(iso);
  const y = d.getUTCFullYear();
  const mo = d.getUTCMonth();
  const day = d.getUTCDate();
  let h = d.getUTCHours();
  let mi = d.getUTCMinutes();

  switch (interval) {
    case '15m':
      mi = Math.floor(mi / 15) * 15;
      return Math.floor(Date.UTC(y, mo, day, h, mi, 0) / 1000);
    case '4h':
      h = Math.floor(h / 4) * 4;
      return Math.floor(Date.UTC(y, mo, day, h, 0, 0) / 1000);
    default:
      return Math.floor(Date.UTC(y, mo, day, 0, 0, 0) / 1000);
  }
}

function claimEndInstantIso(until: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(until.trim());
  if (match) {
    return new Date(
      Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 23, 59, 59),
    ).toISOString();
  }
  const end = new Date(until);
  return new Date(
    Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate(), 23, 59, 59),
  ).toISOString();
}

/** Claim window snapped to candle opens so Start/End align with visible bars. */
export function claimWindowForChart(
  createdAt: string,
  until: string,
  interval: ChartCandleInterval,
): { start: number; end: number } {
  return {
    start: floorToChartInterval(createdAt, interval),
    end: floorToChartInterval(claimEndInstantIso(until), interval),
  };
}


