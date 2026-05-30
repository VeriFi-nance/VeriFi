import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { PageContent } from '@/components/PageContent';
import { useAuthState, useOpenLogin } from '@/lib/auth';

export default function FeedPage() {
  const { authenticated: authed } = useAuthState();
  const openLogin = useOpenLogin();
  const [feedType, setFeedType] = useState('global');

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
            onPosted={() => window.dispatchEvent(new Event('post-created'))}
          />
        </div>
        <TabsContent value="global" className="mt-4">
          <FeedList feed="global" />
        </TabsContent>
        <TabsContent value="following" className="mt-4">
          {authed ? <FeedList feed="following" /> : null}
        </TabsContent>
      </Tabs>
    </PageContent>
  );
}
