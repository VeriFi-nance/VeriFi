import { useReducer, useState } from 'react';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import ClaimCard from '@/components/ClaimCard';
import { createPost } from '@/lib/api';
import type { ReviewClaim } from '@/lib/types';

type ClaimsAction =
  | { type: 'update'; index: number; claim: ReviewClaim };

function claimsReducer(state: ReviewClaim[], action: ClaimsAction): ReviewClaim[] {
  if (action.type === 'update') {
    return state.map((c, i) => (i === action.index ? action.claim : c));
  }
  return state;
}

interface LocationState {
  content: string;
  claims: ReviewClaim[];
}

export default function ClaimReviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;

  const [claims, dispatch] = useReducer(claimsReducer, state?.claims ?? []);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!state) {
    return <Navigate to="/app/post/new" replace />;
  }

  const { content } = state;

  async function handleSubmit() {
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

  function handleBack() {
    navigate('/app/post/new', { state: { restoredContent: content } });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={handleBack}>
          ← Back
        </Button>
        <h1 className="text-xl font-semibold">Review Claims</h1>
      </div>

      {/* Post preview */}
      <Card className="bg-muted/40">
        <CardContent className="pt-4">
          <p className="text-sm whitespace-pre-wrap">{content}</p>
        </CardContent>
      </Card>

      {claims.length === 0 ? (
        <Alert>
          <AlertDescription>
            No financial claims detected — post will be submitted as-is.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {claims.length} claim{claims.length !== 1 ? 's' : ''} detected. Edit or reject before submitting.
          </p>
          {claims.map((claim, i) => (
            <ClaimCard
              key={i}
              claim={claim}
              onChange={(updated) => dispatch({ type: 'update', index: i, claim: updated })}
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
        disabled={submitting}
        onClick={handleSubmit}
      >
        {submitting ? 'Submitting…' : 'Submit Post'}
      </Button>
    </div>
  );
}
