import { useInfiniteQuery, type InfiniteData, type QueryClient, type QueryKey } from '@tanstack/react-query';
import { getFeed, type PaginatedResponse } from '@/lib/api';
import type { PostItem } from '@/lib/types';

export interface FeedParams {
  feed?: string;
  channel?: number;
  assetIds?: number[];
  hasClaims?: boolean;
  hasPositions?: boolean;
  q?: string;
  viewerAddress?: string | null;
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
      viewerAddress: params.viewerAddress?.toLowerCase() ?? null,
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

type FeedData = InfiniteData<PaginatedResponse<PostItem>>;

export function updatePostInFeedData(
  old: FeedData | undefined,
  updatedPost: PostItem,
  options: { preserveViewerState?: boolean } = {},
): FeedData | undefined {
  if (!old) return old;
  return {
    ...old,
    pages: old.pages.map((page) => ({
      ...page,
      results: page.results.map((post) => {
        if (post.id !== updatedPost.id) return post;
        return options.preserveViewerState
          ? {
              ...updatedPost,
              liked_by_me: post.liked_by_me,
              saved_proof_by_me: post.saved_proof_by_me,
            }
          : updatedPost;
      }),
    })),
  };
}

function viewerAddressFromFeedKey(queryKey: QueryKey): string | null {
  const params = Array.isArray(queryKey) ? queryKey[1] : null;
  if (!params || typeof params !== 'object' || !('viewerAddress' in params)) {
    return null;
  }
  const viewerAddress = params.viewerAddress;
  return typeof viewerAddress === 'string' ? viewerAddress.toLowerCase() : null;
}

export function updatePostAcrossCachedFeeds(
  queryClient: QueryClient,
  updatedPost: PostItem,
  viewerAddress?: string | null,
): void {
  const normalizedViewerAddress = viewerAddress?.toLowerCase() ?? null;
  queryClient.getQueriesData<FeedData>({ queryKey: ['feed'] }).forEach(([queryKey, old]) => {
    queryClient.setQueryData<FeedData>(
      queryKey,
      updatePostInFeedData(old, updatedPost, {
        preserveViewerState: viewerAddressFromFeedKey(queryKey) !== normalizedViewerAddress,
      }),
    );
  });
}
