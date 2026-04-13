import { useReducer, useState } from 'react';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
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

// ---------------------------------------------------------------------------
// ClaimCard — local to this flow; no other consumers warrant a separate file
// ---------------------------------------------------------------------------
interface ClaimCardProps {
  claim: ReviewClaim;
  onChange: (updated: ReviewClaim) => void;
}

function ClaimCard({ claim, onChange }: ClaimCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ReviewClaim>(claim);

  function startEdit() {
    setDraft(claim);
    setEditing(true);
  }

  function saveEdit() {
    onChange(draft);
    setEditing(false);
  }

  function cancelEdit() {
    setDraft(claim);
    setEditing(false);
  }

  function reject() {
    onChange({ ...claim, status: 'rejected' });
  }

  function undo() {
    onChange({ ...claim, status: 'confirmed' });
  }

  const isRejected = claim.status === 'rejected';

  if (editing) {
    return (
      <Card className="border border-border">
        <CardContent className="pt-4 space-y-3">
          <Textarea
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            rows={3}
            className="resize-none"
          />
          <div className="flex gap-2">
            <Input
              placeholder="Asset (e.g. BTC)"
              value={draft.asset}
              onChange={(e) => setDraft({ ...draft, asset: e.target.value })}
            />
            <Input
              placeholder="Direction (e.g. bullish)"
              value={draft.direction}
              onChange={(e) => setDraft({ ...draft, direction: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={cancelEdit}>
              Cancel
            </Button>
            <Button className="flex-1" onClick={saveEdit}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={isRejected ? 'opacity-50 border-dashed' : 'border border-border'}>
      <CardContent className="pt-4 space-y-2">
        <p className={`text-sm ${isRejected ? 'line-through text-muted-foreground' : ''}`}>
          {claim.text}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          {claim.asset && (
            <Badge variant="secondary">{claim.asset}</Badge>
          )}
          {claim.direction && (
            <Badge
              variant={claim.direction.toLowerCase() === 'bullish' ? 'success' : 'destructive'}
            >
              {claim.direction}
            </Badge>
          )}
        </div>
        <div className="flex gap-2 pt-1">
          {isRejected ? (
            <Button variant="outline" size="sm" onClick={undo}>
              Undo
            </Button>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={startEdit}>
                Edit
              </Button>
              <Button variant="destructive" size="sm" onClick={reject}>
                Reject
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
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
