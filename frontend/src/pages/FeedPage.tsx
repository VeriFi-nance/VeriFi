import { Alert, AlertDescription } from '@/components/ui/alert';
import { FeedList } from '@/components/feed/FeedList';
import { NewPostButton } from '@/components/feed/NewPostModal';
import { isAuthenticated } from '@/lib/auth';
import { Info } from 'lucide-react';

export default function FeedPage() {
  const authed = isAuthenticated();

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

      {/* ── Post list ──────────────────────────────────────────── */}
      <FeedList />
    </div>
  );
}
