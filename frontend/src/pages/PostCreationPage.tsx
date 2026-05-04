import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { extractClaims, createPost } from '@/lib/api';
import type { ReviewClaim, ExtractedClaimContract } from '@/lib/types';

const MAX_CHARS = 500;
const WARN_THRESHOLD = 450;
const DEBOUNCE_MS = 700;

function toReviewClaim(c: ExtractedClaimContract): ReviewClaim {
  return {
    text: c.text,
    asset: c.pay,
    direction: c.value_type === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish',
    status: 'confirmed',
  };
}

function ClaimPill({
  claim,
  onReject,
  onUndo,
}: {
  claim: ReviewClaim;
  onReject: () => void;
  onUndo: () => void;
}) {
  const rejected = claim.status === 'rejected';
  return (
    <div
      className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm transition-opacity ${
        rejected ? 'opacity-40' : ''
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 min-w-0">
        <span className={`truncate ${rejected ? 'line-through text-muted-foreground' : ''}`}>
          {claim.text}
        </span>
        {!rejected && (
          <>
            <Badge variant="secondary">{claim.asset}</Badge>
            <Badge variant={claim.direction === 'bullish' ? 'success' : 'destructive'}>
              {claim.direction}
            </Badge>
          </>
        )}
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="shrink-0 h-6 px-2 text-xs"
        onClick={rejected ? onUndo : onReject}
      >
        {rejected ? 'Undo' : '✕'}
      </Button>
    </div>
  );
}

export default function PostCreationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const restored = (location.state as { restoredContent?: string } | null)?.restoredContent ?? '';

  const [content, setContent] = useState(restored);
  const [claims, setClaims] = useState<ReviewClaim[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!content.trim()) {
      setClaims([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setExtracting(true);
      try {
        const response = await extractClaims(content);
        setClaims(response.claims.map(toReviewClaim));
      } catch {
        setClaims([]);
      } finally {
        setExtracting(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [content]);

  function toggleClaim(index: number) {
    setClaims((prev) =>
      prev.map((c, i) =>
        i === index ? { ...c, status: c.status === 'rejected' ? 'confirmed' : 'rejected' } : c
      )
    );
  }

  async function handlePost() {
    if (!content.trim()) return;
    setError('');
    setSubmitting(true);
    try {
      await createPost(content, claims);
      navigate('/app', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit post');
      setSubmitting(false);
    }
  }

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;
  const confirmedCount = claims.filter((c) => c.status === 'confirmed').length;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m15 18-6-6 6-6"/>
          </svg>
        </Button>
        <h1 className="text-xl font-semibold">New Post</h1>
      </div>

      <Textarea
        placeholder="What's your financial take?"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={5}
        className="resize-none"
        maxLength={MAX_CHARS}
      />
      <p
        className={`text-xs text-right tabular-nums ${
          overLimit
            ? 'text-destructive font-medium'
            : remaining <= MAX_CHARS - WARN_THRESHOLD
            ? 'text-amber-500'
            : 'text-muted-foreground'
        }`}
      >
        {remaining} / {MAX_CHARS}
      </p>

      {/* Claim extraction results */}
      {(extracting || claims.length > 0) && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            {extracting
              ? 'Analysing claims…'
              : confirmedCount > 0
              ? `${confirmedCount} claim${confirmedCount !== 1 ? 's' : ''} detected`
              : 'No financial claims detected'}
          </p>
          {claims.map((claim, i) => (
            <ClaimPill
              key={i}
              claim={claim}
              onReject={() => toggleClaim(i)}
              onUndo={() => toggleClaim(i)}
            />
          ))}
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        className="w-full"
        disabled={!content.trim() || overLimit || submitting || extracting}
        onClick={handlePost}
      >
        {submitting ? 'Posting…' : 'Post'}
      </Button>
    </div>
  );
}
