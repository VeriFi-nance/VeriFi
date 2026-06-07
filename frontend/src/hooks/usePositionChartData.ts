import { useCallback, useEffect, useRef, useState } from 'react';
import { getPositionChartData } from '@/lib/api';
import {
  chartPollIntervalMs,
  defaultChartInterval,
  isLiveClaimStatus,
} from '@/lib/chart';
import type { PositionChartData, ChartCandleInterval } from '@/lib/types';

export function usePositionChartData(
  positionId: number | undefined,
  createdAt: string | undefined,
  lifetime: string | undefined,
  positionStatus?: string,
) {
  const [interval, setInterval] = useState<ChartCandleInterval>(() =>
    createdAt && lifetime ? defaultChartInterval(createdAt, lifetime) : '4h',
  );
  const [data, setData] = useState<PositionChartData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refetching, setRefetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const live = isLiveClaimStatus(positionStatus);

  const loadChart = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!positionId) return Promise.resolve();

      const isRefetch = hasLoadedRef.current;
      if (isRefetch && opts?.silent) {
        return getPositionChartData(positionId, interval)
          .then((next) => {
            setData(next);
            hasLoadedRef.current = true;
          })
          .catch(() => undefined);
      }

      if (isRefetch) {
        setRefetching(true);
      } else {
        setLoading(true);
      }
      setError(null);

      return getPositionChartData(positionId, interval)
        .then((next) => {
          setData(next);
          hasLoadedRef.current = true;
        })
        .catch((err) => setError(err.message || 'Failed to load chart data'))
        .finally(() => {
          setLoading(false);
          setRefetching(false);
        });
    },
    [positionId, interval],
  );

  useEffect(() => {
    if (!positionId) {
      setData(null);
      hasLoadedRef.current = false;
      return;
    }
    void loadChart();
  }, [positionId, interval, loadChart]);

  useEffect(() => {
    if (!positionId || !live) return;

    const pollMs = chartPollIntervalMs(interval);
    const timer = window.setInterval(() => {
      void loadChart({ silent: true });
    }, pollMs);

    return () => window.clearInterval(timer);
  }, [positionId, interval, live, loadChart]);

  useEffect(() => {
    if (!createdAt || !lifetime) return;
    setInterval(defaultChartInterval(createdAt, lifetime));
    hasLoadedRef.current = false;
    setData(null);
  }, [positionId, createdAt, lifetime]);

  return { data, loading, refetching, error, interval, setInterval, live };
}
