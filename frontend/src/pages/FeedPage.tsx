import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { PageContent } from '@/components/PageContent';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import type { FeedFilter } from '@/components/feed/FeedFilterPopover';

/** Parse the comma-separated `assets` query param into a list of asset ids. */
function parseAssetIds(raw: string | null): number[] {
  if (!raw) return [];
  return raw.split(',').map(Number).filter((n) => Number.isFinite(n) && n > 0);
}

export default function FeedPage() {
  const { authenticated: authed } = useAuthState();
  const openLogin = useOpenLogin();
  const [feedType, setFeedType] = useState('global');
  const [searchParams] = useSearchParams();
  const q = searchParams.get('q') || '';

  // All feed filtering lives in the header SearchBar and is expressed through
  // the URL, so this page is a pure reader of that state.
  const activeFilter: FeedFilter = {
    assetIds: parseAssetIds(searchParams.get('assets')),
    hasClaims: searchParams.get('claims') === '1',
    hasPositions: searchParams.get('positions') === '1',
  };

  function handleFeedChange(value: string) {
    if (value === 'following' && !authed) {
      openLogin('/feed');
      return;
    }
    setFeedType(value);
  }

  return (
    <PageContent className="space-y-5">
      <Tabs value={feedType} onValueChange={handleFeedChange}>
        <div className="flex items-center gap-3">
          <TabsList className="grid flex-1 grid-cols-2">
            <TabsTrigger value="global">Global</TabsTrigger>
            <TabsTrigger value="following">Following</TabsTrigger>
          </TabsList>
          <NewPostButton
            compactOnMobile
            onPosted={() => window.dispatchEvent(new Event('post-created'))}
          />
        </div>
        <TabsContent value="global" className="mt-4">
          <FeedList feed="global" filter={activeFilter} hideFilterToolbar q={q} />
        </TabsContent>
        <TabsContent value="following" className="mt-4">
          {authed ? <FeedList feed="following" filter={activeFilter} hideFilterToolbar q={q} /> : null}
        </TabsContent>
      </Tabs>
    </PageContent>
  );
}
