import { useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Info } from 'lucide-react';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { useAuthState } from '@/lib/auth';

export default function FeedPage() {
  const { authenticated: authed } = useAuthState();
  const [feedType, setFeedType] = useState('global');

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5">
      <div className="flex items-center justify-end">
        <NewPostButton
          onPosted={() => window.dispatchEvent(new Event('post-created'))}
        />
      </div>

      {!authed && (
        <Alert className="border-dashed">
          <Info className="size-4" />
          <AlertDescription>
            Connect your wallet to create posts and participate.
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={feedType} onValueChange={setFeedType}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="global">Global</TabsTrigger>
          <TabsTrigger value="following" disabled={!authed}>
            Following
          </TabsTrigger>
        </TabsList>
        <TabsContent value="global" className="mt-4">
          <FeedList feed="global" />
        </TabsContent>
        <TabsContent value="following" className="mt-4">
          {authed ? <FeedList feed="following" /> : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
