import { QueryClient } from '@tanstack/react-query';

/**
 * Shared React Query client. Defaults tuned for a feed-style app:
 * - retry once (the API layer already falls back across base URLs)
 * - don't refetch on every window focus (avoids feed flicker / extra calls)
 * - keep cached pages around so back-navigation is instant
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      gcTime: 5 * 60_000,
    },
  },
});
