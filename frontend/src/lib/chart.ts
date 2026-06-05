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
