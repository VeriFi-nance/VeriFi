import { useEffect, useMemo, useReducer, useState } from 'react';
import { useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { AlertTriangle, ArrowRight, CalendarDays, Pencil, RotateCcw, ArrowLeftRight } from 'lucide-react';
import { createPost, getAssets } from '@/lib/api';
import type { AssetItem, ClaimValueType, ReviewClaim } from '@/lib/types';
import {
  VALUE_TYPE_OPTIONS,
  deriveClaimStatus,
  directionForValueType,
  formatClaimValue,
  getValueType,
  isClaimComplete,
  isClaimIncomplete,
  missingFields,
} from '@/lib/claims';

type ClaimsAction = { type: 'update'; index: number; claim: ReviewClaim };

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

const NO_DENOMINATOR = '__none__';

// ---------------------------------------------------------------------------
// ClaimCard — one card per extracted claim, with an inline completion editor
// ---------------------------------------------------------------------------
interface ClaimCardProps {
  index: number;
  claim: ReviewClaim;
  assets: AssetItem[];
  onChange: (updated: ReviewClaim) => void;
}

function ClaimCard({ index, claim, assets, onChange }: ClaimCardProps) {
  const incomplete = isClaimIncomplete(claim);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ReviewClaim>(claim);

  const symbols = useMemo(() => assets.map((a) => a.symbol), [assets]);
  const isRejected = claim.status === 'rejected';
  const draftValueType = getValueType(draft);
  const draftMissing = missingFields(draft);

  function startEdit() {
    setDraft(claim);
    setEditing(true);
  }

  function setValueType(vt: ClaimValueType) {
    setDraft((d) => ({ ...d, valueType: vt, direction: directionForValueType(vt) }));
  }

  function swapAssets() {
    setDraft((d) => ({
      ...d,
      asset: d.payda || '',
      payda: d.asset || '',
    }));
  }

  function saveEdit() {
    const cleaned: ReviewClaim = { ...draft };
    cleaned.claimStatus = deriveClaimStatus(cleaned);
    onChange(cleaned);
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

  // ── Editor ──────────────────────────────────────────────────
  if (editing) {
    return (
      <Card className="border border-primary/40 ring-1 ring-primary/20">
        <CardContent className="pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Editing claim #{index + 1}
            </span>
            {!isClaimComplete(draft) && (
              <Badge variant="outline" className="text-amber-600 border-amber-500/50">
                Incomplete
              </Badge>
            )}
          </div>

          <Textarea
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            rows={2}
            className="resize-none text-sm"
            placeholder="Claim summary"
          />

          {/* Value type */}
          <div className="space-y-1">
            <Label className="text-xs">Claim type</Label>
            <div className="flex gap-2">
              {VALUE_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  title={opt.hint}
                  onClick={() => setValueType(opt.value)}
                  className={[
                    'flex-1 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-150',
                    draftValueType === opt.value
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Asset (pay) + Denominator (payda) */}
          <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
            <div className="space-y-1">
              <Label className="text-xs">Asset (numerator)</Label>
              <Select
                value={draft.asset || undefined}
                onValueChange={(v) => setDraft((d) => ({ ...d, asset: v }))}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select asset" />
                </SelectTrigger>
                <SelectContent>
                  {symbols.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8 shrink-0"
              title="Swap asset and denominator"
              disabled={!draft.asset && !draft.payda}
              onClick={swapAssets}
            >
              <ArrowLeftRight className="size-3.5" />
            </Button>
            <div className="space-y-1">
              <Label className="text-xs">Denominator (payda)</Label>
              <Select
                value={draft.payda || NO_DENOMINATOR}
                onValueChange={(v) =>
                  setDraft((d) => ({ ...d, payda: v === NO_DENOMINATOR ? '' : v }))
                }
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select denominator" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_DENOMINATOR}>— None —</SelectItem>
                  {symbols.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Value + Deadline */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">
                {draftValueType === 'PRICE' ? 'Target price' : 'Target move (%)'}
              </Label>
              <Input
                type="number"
                min="0"
                step="0.1"
                placeholder={draftValueType === 'PRICE' ? 'e.g. 103000' : 'e.g. 10'}
                value={draft.percentage ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, percentage: e.target.value }))}
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Deadline</Label>
              <Input
                type="date"
                value={draft.until ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, until: e.target.value }))}
                className="h-8 text-sm"
              />
            </div>
          </div>

          {draftMissing.length > 0 && (
            <p className="text-[11px] text-amber-600">
              Still missing: {draftMissing.join(', ')}. You can still save — incomplete
              claims are dropped when you post.
            </p>
          )}

          <div className="flex gap-2 pt-1">
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

  // ── Read-only view ──────────────────────────────────────────
  const valueType = getValueType(claim);
  const isBearish = valueType === 'PERCENTAGE_DOWN';

  return (
    <Card
      className={
        isRejected
          ? 'opacity-50 border-dashed'
          : incomplete
          ? 'border border-amber-500/50'
          : 'border border-border'
      }
    >
      <CardContent className="pt-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className={`text-sm ${isRejected ? 'line-through text-muted-foreground' : ''}`}>
            {claim.text || 'Untitled claim'}
          </p>
          <span className="text-[10px] font-mono text-muted-foreground shrink-0">
            #{index + 1}
          </span>
        </div>

        {/* Structured summary */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="secondary" className="font-mono">
            {claim.asset || 'Unknown'}
            {claim.payda ? ` / ${claim.payda}` : ''}
          </Badge>
          <Badge variant={isBearish ? 'destructive' : 'success'}>
            {valueType === 'PRICE' ? '◎' : isBearish ? '▼' : '▲'} {formatClaimValue(claim)}
          </Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <CalendarDays className="size-3" />
            {claim.until
              ? new Date(claim.until).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })
              : 'No deadline'}
          </span>
        </div>

        {/* Incomplete warning */}
        {incomplete && !isRejected && (
          <Alert className="border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-400">
            <AlertTriangle className="size-4" />
            <AlertTitle className="text-amber-700 dark:text-amber-400">
              Incomplete claim
            </AlertTitle>
            <AlertDescription className="text-amber-700/90 dark:text-amber-400/90">
              Missing: {missingFields(claim).join(', ')}. Complete it to include it in your
              post — otherwise it will be discarded on submit.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex gap-2 pt-1">
          {isRejected ? (
            <Button variant="outline" size="sm" onClick={undo} className="gap-1.5">
              <RotateCcw className="size-3.5" />
              Undo
            </Button>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={startEdit} className="gap-1.5">
                <Pencil className="size-3.5" />
                {incomplete ? 'Complete' : 'Edit'}
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
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getAssets().then(setAssets).catch(console.error);
  }, []);

  if (!state) {
    return <Navigate to="/app" replace />;
  }

  const { content } = state;

  const activeClaims = claims.filter((c) => c.status !== 'rejected');
  // Only fully-completed claims are eligible for submission.
  const completeClaims = activeClaims.filter(isClaimComplete);
  const incompleteCount = activeClaims.length - completeClaims.length;

  async function handleSubmit() {
    setError('');
    setSubmitting(true);
    try {
      // Silently drop any claim still flagged INCOMPLETE_CLAIM.
      const submittable = claims.filter((c) => c.status !== 'rejected' && isClaimComplete(c));
      await createPost(content, submittable);
      navigate('/app', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit post');
      setSubmitting(false);
    }
  }

  function handleBack() {
    navigate('/app', { replace: true });
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
            {claims.length} claim{claims.length !== 1 ? 's' : ''} detected. Edit or reject
            each one before submitting.
          </p>
          {claims.map((claim, i) => (
            <ClaimCard
              key={i}
              index={i}
              claim={claim}
              assets={assets}
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

      {incompleteCount > 0 && (
        <p className="text-xs text-amber-600 flex items-center gap-1.5">
          <AlertTriangle className="size-3.5" />
          {incompleteCount} incomplete claim{incompleteCount !== 1 ? 's' : ''} will be
          discarded — {completeClaims.length} will be posted.
        </p>
      )}

      <Button className="w-full gap-1.5" disabled={submitting} onClick={handleSubmit}>
        {submitting ? 'Submitting…' : 'Submit Post'}
        {!submitting && <ArrowRight className="size-4" />}
      </Button>
    </div>
  );
}
