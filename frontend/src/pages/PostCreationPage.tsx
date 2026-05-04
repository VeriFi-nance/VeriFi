import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { extractClaims } from '@/lib/api';
import type { ReviewClaim } from '@/lib/types';
import type { ExtractedClaimContract } from '@/lib/types';

const MAX_CHARS = 500;
const WARN_THRESHOLD = 450;

function toReviewClaim(c: ExtractedClaimContract): ReviewClaim {
  return {
    text: c.text,
    asset: c.pay,
    direction: c.value_type === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish',
    status: 'confirmed',
  };
}

export default function PostCreationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const restored = (location.state as { restoredContent?: string } | null)?.restoredContent ?? '';

  const [content, setContent] = useState(restored);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState('');

  async function handleNext() {
    if (!content.trim()) return;
    setError('');
    setExtracting(true);
    try {
      const response = await extractClaims(content);
      const claims: ReviewClaim[] = response.claims.map(toReviewClaim);
      navigate('/app/post/review', { state: { content, claims } });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to extract claims');
      setExtracting(false);
    }
  }

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
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

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button
        className="w-full"
        disabled={!content.trim() || overLimit || extracting}
        onClick={handleNext}
      >
        {extracting ? 'Analysing…' : 'Next'}
      </Button>
    </div>
  );
}
