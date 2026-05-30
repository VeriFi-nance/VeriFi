import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PenSquare, Plus, X, TrendingUp, TrendingDown, CalendarDays, AlertTriangle, ListChecks, DollarSign, Pencil, RotateCcw, ArrowLeftRight } from 'lucide-react';
import { createPost, createHardClaim, getAssets, extractClaims } from '@/lib/api';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';
import type { AssetItem, ReviewClaim, ClaimValueType } from '@/lib/types';
import { toReviewClaim, isClaimIncomplete, isClaimComplete, missingFields } from '@/lib/claims';

const DEBOUNCE_MS = 250;

const MAX_CHARS = 500;

const NO_DENOMINATOR = '__none__';

interface ClaimDraft {
  asset_id: string;            // asset id (for HardClaim)
  assetSymbol: string;         // numerator display (pay)
  payda: string;               // denominator ticker ('' = none)
  valueType: ClaimValueType;   // PRICE | PERCENTAGE_UP | PERCENTAGE_DOWN
  value: string;               // magnitude (price or percentage move)
  until: string;
  stakeRep: string;
}

interface AttachedClaim {
  asset_id: string;
  assetSymbol: string;
  payda: string;
  valueType: ClaimValueType;
  value: string;
  until: string;
  stakeRep: string;
}

function emptyDraft(): ClaimDraft {
  return {
    asset_id: '', assetSymbol: '', payda: '', valueType: 'PERCENTAGE_UP',
    value: '', until: '', stakeRep: '10',
  };
}

/** HardClaim.direction is still a bullish/bearish string; derive it from value type. */
function directionForValueType(vt: ClaimValueType): 'Bullish' | 'Bearish' {
  return vt === 'PERCENTAGE_DOWN' ? 'Bearish' : 'Bullish';
}

/**
 * Identity used for dismiss / restore and the "smart cleanup" pass: asset +
 * direction + magnitude. The deadline is intentionally excluded so editing only
 * the date does not strand a dismissed claim, while changing the value or asset
 * makes it disappear from the detections (and so gets cleaned up).
 */
function dismissKey(c: { asset?: string; direction?: string; percentage?: string }): string {
  return `${(c.asset || '').toLowerCase()}|${(c.direction || '').toLowerCase()}|${(c.percentage || '').toString().trim()}`;
}

/** Convert an attached claim back into a review claim (for the dismissed pool). */
function reviewFromAttached(c: AttachedClaim): ReviewClaim {
  return {
    text: '',
    asset: c.assetSymbol,
    direction: directionForValueType(c.valueType).toLowerCase(),
    status: 'confirmed',
    percentage: c.value,
    until: c.until,
    payda: c.payda,
    valueType: c.valueType,
  };
}

const VALUE_TYPE_CHOICES: { value: ClaimValueType; label: string }[] = [
  { value: 'PRICE', label: 'Price' },
  { value: 'PERCENTAGE_UP', label: '% Up' },
  { value: 'PERCENTAGE_DOWN', label: '% Down' },
];

interface ClaimViewerProps {
  assetSymbol: string;
  direction: 'Bullish' | 'Bearish' | 'bullish' | 'bearish';
  percentage: string;
  until: string;
  payda?: string;
  valueType?: ClaimValueType;
  incomplete?: boolean;
}

function ClaimViewer({
  assetSymbol,
  direction,
  percentage,
  until,
  payda,
  valueType,
  incomplete,
}: ClaimViewerProps) {
  const isPrice = valueType === 'PRICE';
  const isDirectionBullish = valueType
    ? valueType !== 'PERCENTAGE_DOWN'
    : direction === 'Bullish' || direction === 'bullish';
  const valueLabel = percentage
    ? isPrice
      ? parseFloat(percentage).toLocaleString()
      : `${parseFloat(percentage).toFixed(1)}%`
    : isPrice
    ? '? '
    : '? %';
  return (
    <div
      className={[
        'flex items-center gap-2 rounded-lg border px-3 py-2',
        incomplete ? 'border-amber-500/50 bg-amber-500/5' : 'bg-muted/40',
      ].join(' ')}
    >
      {/* Direction dot */}
      <span
        className={`size-2 rounded-full shrink-0 ${
          isDirectionBullish ? 'bg-emerald-500' : 'bg-red-500'
        }`}
      />
      <span className="font-mono font-semibold text-xs">
        {assetSymbol || 'Unknown Asset'}
        {payda ? <span className="text-muted-foreground">/{payda}</span> : null}
      </span>
      <Badge
        variant={isDirectionBullish ? 'success' : 'destructive'}
        className="text-[10px] px-1.5 py-0"
      >
        {isPrice ? '◎' : isDirectionBullish ? '▲' : '▼'} {valueLabel}
      </Badge>
      <span className="flex items-center gap-1 text-xs text-muted-foreground flex-1">
        <CalendarDays className="size-3" />
        {until ? new Date(until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Unknown Date'}
      </span>
      {incomplete && <AlertTriangle className="size-3.5 text-amber-500 shrink-0" />}
    </div>
  );
}

interface NewPostModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPosted: () => void;
  communityId?: number;
}

export function NewPostModal({ open, onOpenChange, onPosted, communityId }: NewPostModalProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuthState();
  const [content, setContent] = useState('');
  const [claims, setClaims] = useState<AttachedClaim[]>([]);
  const [showClaimForm, setShowClaimForm] = useState(false);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft());
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [extractedClaims, setExtractedClaims] = useState<ReviewClaim[]>([]);
  // Claims the user explicitly set aside. Kept in memory so they can be reverted
  // and so the auto-scan never re-surfaces them — but pruned by smart cleanup
  // once they no longer appear in a fresh detection.
  const [dismissedClaims, setDismissedClaims] = useState<ReviewClaim[]>([]);
  const [showDismissed, setShowDismissed] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open) {
      getAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!content.trim()) {
      setExtractedClaims([]);
      setDismissedClaims([]);  // nothing detected -> no ghosts to remember
      setExtractError('');
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setExtracting(true);
      try {
        const response = await extractClaims(content);
        const fresh = response.claims.map(toReviewClaim);
        setExtractedClaims(fresh);
        // Smart cleanup: keep a dismissed claim only while it still has a
        // matching (asset + direction + value) detection in the fresh scan.
        const freshKeys = new Set(fresh.map(dismissKey));
        setDismissedClaims((prev) => prev.filter((d) => freshKeys.has(dismissKey(d))));
        setExtractError('');
      } catch (e) {
        setExtractedClaims([]);
        setExtractError(e instanceof Error ? e.message : 'Could not analyse claims.');
      } finally {
        setExtracting(false);
      }
    }, DEBOUNCE_MS);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [content]);

  function resetModal() {
    setContent('');
    setClaims([]);
    setExtractedClaims([]);
    setDismissedClaims([]);
    setShowDismissed(false);
    setExtractError('');
    setShowClaimForm(false);
    setDraft(emptyDraft());
    setError('');
  }

  // ── Dismiss / restore helpers ──────────────────────────────
  function dismissClaim(c: ReviewClaim) {
    setDismissedClaims((prev) =>
      prev.some((d) => dismissKey(d) === dismissKey(c)) ? prev : [...prev, c]
    );
  }
  function undismiss(key: string) {
    setDismissedClaims((prev) => prev.filter((d) => dismissKey(d) !== key));
  }
  function revertLastDismissed() {
    setDismissedClaims((prev) => prev.slice(0, -1));
  }
  function restoreDismissed(idx: number) {
    setDismissedClaims((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleClose(val: boolean) {
    if (!val) resetModal();
    onOpenChange(val);
  }

  function addClaim() {
    if (!draft.asset_id || !draft.value || !draft.until) {
      setError('Fill in the asset, value and target date before adding.');
      return;
    }
    const val = parseFloat(draft.value);
    if (draft.valueType === 'PRICE') {
      if (isNaN(val) || val <= 0) {
        setError('Target price must be greater than 0.');
        return;
      }
    } else if (isNaN(val) || val < 0.1 || val > 1000) {
      setError('Percentage must be between 0.1 and 1000.');
      return;
    }

    // Ensure the date is strictly in the future (tomorrow or later) to match backend constraints
    const todayStr = new Date().toISOString().split('T')[0];
    if (draft.until <= todayStr) {
      setError('Target date must be tomorrow or later.');
      return;
    }
    const stakeRepNum = parseFloat(draft.stakeRep);
    if (isNaN(stakeRepNum) || stakeRepNum < 10 || stakeRepNum > 100) {
      setError('Stake must be between 10 and 100 rep.');
      return;
    }
    setError('');
    // A claim that is now attached should no longer count as dismissed.
    undismiss(dismissKey({
      asset: draft.assetSymbol,
      direction: directionForValueType(draft.valueType).toLowerCase(),
      percentage: draft.value,
    }));
    setClaims((prev) => [...prev, { ...draft }]);
    setDraft(emptyDraft());
    setShowClaimForm(false);
  }

  function attachedKey(c: AttachedClaim): string {
    const dir = directionForValueType(c.valueType).toLowerCase();
    return `${c.assetSymbol || 'null'}-${dir}-${c.value || 'null'}-${c.until || 'null'}`;
  }

  function removeClaim(idx: number) {
    setClaims((prev) => {
      const target = prev[idx];
      // Removing an attached claim dismisses it so the auto-scan won't re-suggest it.
      if (target) dismissClaim(reviewFromAttached(target));
      return prev.filter((_, i) => i !== idx);
    });
  }

  // Pull an attached claim back into the editor so it can be modified, then re-added.
  function editClaim(idx: number) {
    const c = claims[idx];
    if (!c) return;
    setDraft({
      asset_id: c.asset_id,
      assetSymbol: c.assetSymbol,
      payda: c.payda,
      valueType: c.valueType,
      value: c.value,
      until: c.until,
      stakeRep: c.stakeRep,
    });
    // Hide it from the detected list while it sits in the editor.
    dismissClaim(reviewFromAttached(c));
    setClaims((prev) => prev.filter((_, i) => i !== idx));
    setShowClaimForm(true);
    setError('');
  }

  function swapDraftAssets() {
    setDraft((d) => {
      const newSymbol = d.payda || '';
      const newPayda = d.assetSymbol || '';
      const newAsset = assets.find((a) => a.symbol === newSymbol);
      return {
        ...d,
        asset_id: newAsset ? newAsset.id.toString() : '',
        assetSymbol: newSymbol,
        payda: newPayda,
      };
    });
  }

  async function handleSubmit() {
    if (!content.trim()) return;
    if (!auth.authenticated) {
      navigate(loginPathWithReturn(location.pathname), { replace: true });
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      // 1. Create the post (no attached claims on the post itself)
      const newPost = await createPost(content.trim(), [], communityId);

      // 2. Create each HardClaim, linked to the new post
      await Promise.all(
        claims.map((c) => {
          const stakeRepNum = parseFloat(c.stakeRep);
          const market =
            !isNaN(stakeRepNum) && stakeRepNum >= 10 && stakeRepNum <= 100
              ? { side: 'YES' as const, stake_rep: stakeRepNum }
              : undefined;
          return createHardClaim({
            asset_id: parseInt(c.asset_id, 10),
            post_id: newPost.id,
            community_id: communityId,
            direction: directionForValueType(c.valueType),
            value_type: c.valueType,
            payda: c.payda || undefined,
            percentage: parseFloat(c.value),
            until: c.until,
            ...(market ? { market } : {}),
          });
        })
      );

      resetModal();
      onOpenChange(false);
      onPosted();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to post.');
    } finally {
      setSubmitting(false);
    }
  }

  // Detected claims that are neither dismissed nor already attached.
  const dismissedKeySet = new Set(dismissedClaims.map(dismissKey));
  const visibleExtractedClaims = extractedClaims.filter((c) => {
    if (dismissedKeySet.has(dismissKey(c))) return false;
    const fullKey = `${c.asset || 'null'}-${c.direction}-${c.percentage || 'null'}-${c.until || 'null'}`;
    return !claims.some((ac) => attachedKey(ac) === fullKey);
  });

  function openReviewer() {
    if (!auth.authenticated) {
      navigate(loginPathWithReturn(location.pathname), { replace: true });
      return;
    }
    navigate('/app/post/review', {
      state: { content: content.trim(), claims: visibleExtractedClaims },
    });
    resetModal();
    onOpenChange(false);
  }

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;
  const canSubmit = content.trim().length > 0 && !overLimit && !submitting;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg w-full p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <DialogTitle className="text-base font-semibold">New Post</DialogTitle>
        </DialogHeader>

        <div className="px-6 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* ── Content textarea ────────────────────────────── */}
          <div className="space-y-1.5">
            <Textarea
              placeholder="What's your financial take?"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              className="resize-none text-sm"
              maxLength={MAX_CHARS + 50}
              autoFocus
            />
            <p
              className={`text-xs text-right tabular-nums ${
                overLimit
                  ? 'text-destructive font-medium'
                  : remaining <= 50
                  ? 'text-amber-500'
                  : 'text-muted-foreground'
              }`}
            >
              {remaining} / {MAX_CHARS}
            </p>
            {extractError && (
              <p className="flex items-center gap-1.5 text-[11px] text-destructive">
                <AlertTriangle className="size-3 shrink-0" />
                Couldn't analyse claims: {extractError}
              </p>
            )}
          </div>

          {/* ── Auto-extracted claims ───────────────────────── */}
          {(extracting || extractedClaims.length > 0) && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  {extracting
                    ? 'Analysing…'
                    : `Detected Claims${visibleExtractedClaims.length > 1 ? ` (${visibleExtractedClaims.length})` : ''}`}
                </p>
                {!extracting && visibleExtractedClaims.length > 0 && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs gap-1.5"
                    onClick={openReviewer}
                  >
                    <ListChecks className="size-3.5" />
                    Review {visibleExtractedClaims.length}
                  </Button>
                )}
              </div>

              {/* Waiting to be added */}
              <div className="space-y-1.5">
                {visibleExtractedClaims.map((c, i) => {
                  const marketReady = isClaimComplete(c);
                  const incomplete = isClaimIncomplete(c);
                  return (
                    <div key={i} className="space-y-1">
                      <div className="flex items-center gap-2">
                        <div className="flex-1">
                          <ClaimViewer
                            assetSymbol={c.asset}
                            direction={c.direction as any}
                            percentage={c.percentage!}
                            until={c.until!}
                            payda={c.payda}
                            valueType={c.valueType}
                            incomplete={incomplete}
                          />
                        </div>
                        <div className="flex items-center">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            disabled={!marketReady}
                            onClick={() => {
                              const asset = assets.find((a) => a.symbol === c.asset);
                              if (asset) {
                                const newClaim: AttachedClaim = {
                                  asset_id: asset.id.toString(),
                                  assetSymbol: asset.symbol,
                                  payda: c.payda || '',
                                  valueType: c.valueType || 'PERCENTAGE_UP',
                                  value: c.percentage!,
                                  until: c.until!,
                                  stakeRep: '10',
                                };
                                setClaims((prev) => [...prev, newClaim]);
                                undismiss(dismissKey(c));
                              }
                            }}
                          >
                            Add
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            onClick={() => {
                              const asset = assets.find((a) => a.symbol === c.asset);
                              setDraft({
                                asset_id: asset ? asset.id.toString() : '',
                                assetSymbol: asset ? asset.symbol : '',
                                payda: c.payda || '',
                                valueType: c.valueType || 'PERCENTAGE_UP',
                                value: c.percentage || '',
                                until: c.until || '',
                                stakeRep: '10',
                              });
                              setShowClaimForm(true);
                              dismissClaim(c);
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            onClick={() => dismissClaim(c)}
                          >
                            Dismiss
                          </Button>
                        </div>
                      </div>
                      {incomplete && (
                        <p className="flex items-center gap-1 text-[11px] text-amber-600 pl-1">
                          <AlertTriangle className="size-3 shrink-0" />
                          Missing {missingFields(c).join(', ')} — open Review to complete it.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* ── Dismissed claims (revert / see all) ──────── */}
              {dismissedClaims.length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="flex items-center gap-4">
                    <button
                      type="button"
                      onClick={revertLastDismissed}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                      <RotateCcw className="size-3" />
                      Revert last dismissed claim
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowDismissed((s) => !s)}
                      className="text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                      {showDismissed
                        ? 'Hide dismissed claims'
                        : `See all dismissed claims (${dismissedClaims.length})`}
                    </button>
                  </div>
                  {showDismissed && (
                    <div className="space-y-1.5 rounded-lg border border-dashed bg-muted/20 p-2">
                      {dismissedClaims.map((c, i) => (
                        <div key={i} className="flex items-center gap-2 opacity-75">
                          <div className="flex-1">
                            <ClaimViewer
                              assetSymbol={c.asset}
                              direction={c.direction as any}
                              percentage={c.percentage!}
                              until={c.until!}
                              payda={c.payda}
                              valueType={c.valueType}
                              incomplete={isClaimIncomplete(c)}
                            />
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            onClick={() => restoreDismissed(i)}
                          >
                            Restore
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── Added claims ────────────────────────────────── */}
          {claims.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Attached Claims
              </p>
              <div className="space-y-1.5">
                {claims.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1">
                      <ClaimViewer
                        assetSymbol={c.assetSymbol}
                        direction={directionForValueType(c.valueType)}
                        percentage={c.value}
                        until={c.until}
                        payda={c.payda}
                        valueType={c.valueType}
                      />
                    </div>
                    <button
                      onClick={() => editClaim(i)}
                      title="Edit claim"
                      className="size-5 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                    <button
                      onClick={() => removeClaim(i)}
                      title="Remove claim"
                      className="size-5 flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Add Claim form ──────────────────────────────── */}
          {showClaimForm ? (
            <div className="rounded-xl border bg-muted/20 p-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Add Claim
              </p>

              {/* Asset (pay) + Denominator (payda) */}
              <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
                <div className="space-y-1">
                  <Label className="text-xs">Asset (numerator)</Label>
                  <Select
                    value={draft.asset_id}
                    onValueChange={(v) => {
                      const a = assets.find((a) => a.id.toString() === v);
                      setDraft((d) => ({ ...d, asset_id: v, assetSymbol: a?.symbol ?? '' }));
                    }}
                  >
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue placeholder="Select asset" />
                    </SelectTrigger>
                    <SelectContent>
                      {assets.map((a) => (
                        <SelectItem key={a.id} value={a.id.toString()}>
                          {a.symbol} — {a.name}
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
                  disabled={!draft.assetSymbol && !draft.payda}
                  onClick={swapDraftAssets}
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
                      {assets.map((a) => (
                        <SelectItem key={a.id} value={a.symbol}>
                          {a.symbol} — {a.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Claim type (value_type) */}
              <div className="space-y-1">
                <Label className="text-xs">Claim type</Label>
                <div className="flex gap-2">
                  {VALUE_TYPE_CHOICES.map((opt) => {
                    const active = draft.valueType === opt.value;
                    const tone =
                      opt.value === 'PERCENTAGE_DOWN'
                        ? 'bg-red-500 text-white border-red-500'
                        : opt.value === 'PERCENTAGE_UP'
                        ? 'bg-emerald-500 text-white border-emerald-500'
                        : 'bg-foreground text-background border-foreground';
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setDraft((d) => ({ ...d, valueType: opt.value }))}
                        className={[
                          'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-150',
                          active ? tone : 'border-border text-muted-foreground hover:text-foreground',
                        ].join(' ')}
                      >
                        {opt.value === 'PERCENTAGE_UP' && <TrendingUp className="size-3.5" />}
                        {opt.value === 'PERCENTAGE_DOWN' && <TrendingDown className="size-3.5" />}
                        {opt.value === 'PRICE' && <DollarSign className="size-3.5" />}
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Value + Date — side by side */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">
                    {draft.valueType === 'PRICE' ? 'Target price' : 'Target move (%)'}
                  </Label>
                  <Input
                    type="number"
                    min={draft.valueType === 'PRICE' ? '0' : '0.1'}
                    {...(draft.valueType === 'PRICE' ? {} : { max: '1000' })}
                    step={draft.valueType === 'PRICE' ? '0.01' : '0.1'}
                    placeholder={draft.valueType === 'PRICE' ? 'e.g. 103000' : 'e.g. 25'}
                    value={draft.value}
                    onChange={(e) => setDraft((d) => ({ ...d, value: e.target.value }))}
                    className="h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Target date</Label>
                  <Input
                    type="date"
                    min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
                    value={draft.until}
                    onChange={(e) => setDraft((d) => ({ ...d, until: e.target.value }))}
                    className="h-8 text-sm"
                  />
                </div>
              </div>

              {/* ── Reputation market (Model G) ──────────────── */}
              <div className="rounded-lg border bg-background/60 p-3 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Reputation market (Model G)
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Creator side is auto-set to <span className="font-semibold text-emerald-600">YES</span>.
                </p>
                <div className="space-y-1">
                  <Label className="text-xs">Stake (10–100 rep)</Label>
                  <Input
                    type="number"
                    min={10}
                    max={100}
                    step={1}
                    value={draft.stakeRep}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, stakeRep: e.target.value }))
                    }
                    className="h-8 text-sm"
                  />
                </div>
                <p className="text-[10px] text-muted-foreground leading-snug">
                  Plus 2-rep listing fee (burned) and 5% trade burn. Costs 2 energy.
                </p>
              </div>

              {/* Form actions */}
              <div className="flex gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => { setShowClaimForm(false); setDraft(emptyDraft()); setError(''); }}
                >
                  Cancel
                </Button>
                <Button size="sm" className="flex-1" onClick={addClaim}>
                  Add Claim
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 border-dashed text-muted-foreground hover:text-foreground"
              onClick={() => { setShowClaimForm(true); setError(''); }}
            >
              <Plus className="size-3.5" />
              Add Claim
            </Button>
          )}
        </div>

        {/* ── Footer actions ───────────────────────────────── */}
        <div className="px-6 py-4 border-t flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            {claims.length > 0
              ? `${claims.length} claim${claims.length !== 1 ? 's' : ''} attached`
              : 'No claims yet'}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => handleClose(false)}>
              Cancel
            </Button>
            <Button size="sm" disabled={!canSubmit} onClick={handleSubmit} className="gap-1.5">
              <PenSquare className="size-3.5" />
              {submitting ? 'Posting…' : 'Post'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Trigger button — place anywhere to open the modal */
export function NewPostButton({ onPosted, communityId }: { onPosted: () => void, communityId?: number }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const auth = useAuthState();

  return (
    <>
      <Button
        size="sm"
        className="gap-2 font-semibold bg-emerald-300/90 text-gray-900 border border-emerald-500/50 hover:bg-emerald-500/90 shadow-[0_0_18px_rgba(16,185,129,0.5)] rounded-xl"
        onClick={() => {
          if (!auth.authenticated) {
            navigate(loginPathWithReturn(location.pathname), { replace: true });
            return;
          }
          setOpen(true);
        }}
      >
        <PenSquare className="size-4" />
        New Post
      </Button>
      <NewPostModal open={open} onOpenChange={setOpen} onPosted={onPosted} communityId={communityId} />
    </>
  );
}
