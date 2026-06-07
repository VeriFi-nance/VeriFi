import { useQuery } from '@tanstack/react-query';
import { getAssets } from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import type { AssetItem } from '@/lib/types';

const ASSETS_KEY = ['assets'];
const ASSETS_STALE = 10 * 60_000; // 10 min — assets rarely change

/**
 * Imperative cached fetch for callers that need assets inside a Promise.all and
 * can't use the hook. Shares the same cache entry as useAssets, so a value
 * already loaded by either path is reused instead of re-fetched.
 */
export function fetchAssets(): Promise<AssetItem[]> {
  return queryClient.fetchQuery({
    queryKey: ASSETS_KEY,
    queryFn: getAssets,
    staleTime: ASSETS_STALE,
  });
}

/**
 * Shared assets query. Assets are reference data that barely change, so a single
 * cached query replaces the ~6 independent getAssets() calls that previously
 * fired on every page mount (FeedPage, FeedList, PostDetailPage, UserPage,
 * ClaimDetailPage, NewPostModal).
 */
export function useAssets(): AssetItem[] {
  const { data } = useQuery({
    queryKey: ASSETS_KEY,
    queryFn: getAssets,
    staleTime: ASSETS_STALE,
  });
  return data ?? [];
}
