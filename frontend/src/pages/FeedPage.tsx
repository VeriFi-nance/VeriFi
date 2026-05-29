import { useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { useAuthState } from '@/lib/auth';
import { Info } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function FeedPage() {
  const { authenticated: authed } = useAuthState();
  const [feedType, setFeedType] = useState('global');

  return (
    <div className="space-y-5">
      {/* ── Header row — capped to match post card width ────────── */}
      <div className="flex items-center gap-4 justify-between max-w-2xl">
        <div className="space-y-0.5">
          <h2 className="text-2xl font-bold tracking-tight">Feed</h2>
          <p className="text-sm text-muted-foreground">
            Predictions backed by <span className="text-primary font-medium">reputation</span>
          </p>
        </div>
        <div className="shrink-0">
          <NewPostButton onPosted={() => window.dispatchEvent(new Event('post-created'))} />
        </div>
      </div>

      {/* ── Guest nudge ────────────────────────────────────────── */}
      {!authed && (
        <Alert className="border-dashed">
          <Info className="size-4" />
          <AlertDescription>
            Connect your wallet to create posts and participate in the community
          </AlertDescription>
        </Alert>
      )}

      {/* ── Feed Tabs ──────────────────────────────────────────── */}
      <Tabs defaultValue="global" value={feedType} onValueChange={setFeedType} className="max-w-2xl">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="global">Global</TabsTrigger>
          <TabsTrigger value="following" disabled={!authed}>Following</TabsTrigger>
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
