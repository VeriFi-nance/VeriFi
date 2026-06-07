import { useInfiniteQuery } from '@tanstack/react-query';
import { getFeed } from '@/lib/api';
import type { PostItem } from '@/lib/types';

export interface FeedParams {
  feed?: string;
  channel?: number;
  assetIds?: number[];
  hasClaims?: boolean;
  hasPositions?: boolean;
  q?: string;
}

/** Stable query key for a given feed view. Used for fetching and cache updates. */
export function feedQueryKey(params: FeedParams) {
  return [
    'feed',
    {
      feed: params.feed ?? null,
      channel: params.channel ?? null,
      assetIds: params.assetIds && params.assetIds.length > 0 ? [...params.assetIds].sort() : null,
      hasClaims: params.hasClaims || false,
      hasPositions: params.hasPositions || false,
      q: params.q || '',
    },
  ] as const;
}

/**
 * Paginated feed via useInfiniteQuery. Cached per view, so navigating away and
 * back serves the loaded pages instantly instead of refetching from scratch.
 */
export function useFeed(params: FeedParams, enabled = true) {
  return useInfiniteQuery({
    queryKey: feedQueryKey(params),
    enabled,
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      getFeed({
        feed: params.feed,
        channel: params.channel,
        page: pageParam,
        asset_ids: params.assetIds && params.assetIds.length > 0 ? params.assetIds : undefined,
        has_claims: params.hasClaims || undefined,
        has_positions: params.hasPositions || undefined,
        q: params.q,
      }),
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
  });
}

/** Flatten the infinite-query pages into a single post list. */
export function flattenFeed(pages: { results: PostItem[] }[] | undefined): PostItem[] {
  return pages ? pages.flatMap((p) => p.results) : [];
}
