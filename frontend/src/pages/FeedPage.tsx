import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { PageContent } from '@/components/PageContent';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { FeedFilterPopover, type FeedFilter } from '@/components/feed/FeedFilterPopover';
import { getAssets } from '@/lib/api';
import type { AssetItem } from '@/lib/types';

const DEFAULT_FILTER: FeedFilter = {
  assetIds: [],
  hasClaims: false,
  hasPositions: false,
};

export default function FeedPage() {
  const { authenticated: authed } = useAuthState();
  const openLogin = useOpenLogin();
  const [feedType, setFeedType] = useState('global');
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [activeFilter, setActiveFilter] = useState<FeedFilter>(DEFAULT_FILTER);
  const [searchParams] = useSearchParams();
  const q = searchParams.get('q') || '';

  useEffect(() => {
    getAssets()
      .then(setAssets)
      .catch(() => {});
  }, []);

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
          <FeedFilterPopover
            assets={assets}
            filter={activeFilter}
            onApply={setActiveFilter}
          />
          <TabsList className="grid flex-1 grid-cols-2">
            <TabsTrigger value="global">Global</TabsTrigger>
            <TabsTrigger value="following">Following</TabsTrigger>
          </TabsList>
          <NewPostButton
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
