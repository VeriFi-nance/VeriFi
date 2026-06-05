import { useCallback, useEffect, useRef, useState } from 'react';
import { getClaimChartData } from '@/lib/api';
import {
  chartPollIntervalMs,
  defaultChartInterval,
  isLiveClaimStatus,
} from '@/lib/chart';
import type { ClaimChartData, ChartCandleInterval } from '@/lib/types';

export function useClaimChartData(
  claimId: number | undefined,
  createdAt: string | undefined,
  until: string | undefined,
  claimStatus?: string,
) {
  const [interval, setInterval] = useState<ChartCandleInterval>(() =>
    createdAt && until ? defaultChartInterval(createdAt, until) : '4h',
  );
  const [data, setData] = useState<ClaimChartData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refetching, setRefetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const live = isLiveClaimStatus(claimStatus);

  const loadChart = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!claimId) return Promise.resolve();

      const isRefetch = hasLoadedRef.current;
      if (isRefetch && opts?.silent) {
        return getClaimChartData(claimId, interval)
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

      return getClaimChartData(claimId, interval)
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
    [claimId, interval],
  );

  useEffect(() => {
    if (!claimId) {
      setData(null);
      hasLoadedRef.current = false;
      return;
    }
    void loadChart();
  }, [claimId, interval, loadChart]);

  useEffect(() => {
    if (!claimId || !live) return;

    const pollMs = chartPollIntervalMs(interval);
    const timer = window.setInterval(() => {
      void loadChart({ silent: true });
    }, pollMs);

    return () => window.clearInterval(timer);
  }, [claimId, interval, live, loadChart]);

  useEffect(() => {
    if (!createdAt || !until) return;
    setInterval(defaultChartInterval(createdAt, until));
    hasLoadedRef.current = false;
    setData(null);
  }, [claimId, createdAt, until]);

  return { data, loading, refetching, error, interval, setInterval, live };
}
