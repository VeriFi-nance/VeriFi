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
import { PenSquare, Plus, X, TrendingUp, TrendingDown, CalendarDays } from 'lucide-react';
import { createPost, createHardClaim, getAssets, extractClaims } from '@/lib/api';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';
import type { AssetItem, ReviewClaim, ExtractedClaimContract } from '@/lib/types';

const DEBOUNCE_MS = 700;

function toReviewClaim(c: ExtractedClaimContract): ReviewClaim {
  return {
    text: c.text,
    asset: c.pay || '',
    direction: c.value_type === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish',
    status: 'confirmed',
    percentage: c.value !== null ? c.value.toString() : '',
    until: c.deadline || '',
  };
}

const MAX_CHARS = 500;

type ClaimDirection = 'Bullish' | 'Bearish';

interface ClaimDraft {
  asset_id: string;       // asset id (for HardClaim)
  assetSymbol: string;    // display
  direction: ClaimDirection | '';
  percentage: string;
  until: string;
  stakeRep: string;
}

interface AttachedClaim {
  asset_id: string;
  assetSymbol: string;
  direction: ClaimDirection;
  percentage: string;
  until: string;
  stakeRep: string;
}

function emptyDraft(): ClaimDraft {
  return {
    asset_id: '', assetSymbol: '', direction: '', percentage: '', until: '',
    stakeRep: '10',
  };
}

interface ClaimViewerProps {
  assetSymbol: string;
  direction: 'Bullish' | 'Bearish' | 'bullish' | 'bearish';
  percentage: string;
  until: string;
}

function ClaimViewer({
  assetSymbol,
  direction,
  percentage,
  until,
}: ClaimViewerProps) {
  const isDirectionBullish = direction === 'Bullish' || direction === 'bullish';
  return (
    <div className="flex items-center gap-2 rounded-lg border px-3 py-2 bg-muted/40">
      {/* Direction dot */}
      <span
        className={`size-2 rounded-full shrink-0 ${
          isDirectionBullish ? 'bg-emerald-500' : 'bg-red-500'
        }`}
      />
      <span className="font-mono font-semibold text-xs">{assetSymbol || 'Unknown Asset'}</span>
      <Badge
        variant={isDirectionBullish ? 'success' : 'destructive'}
        className="text-[10px] px-1.5 py-0"
      >
        {isDirectionBullish ? '▲' : '▼'} {percentage ? `${parseFloat(percentage).toFixed(1)}%` : '? %'}
      </Badge>
      <span className="flex items-center gap-1 text-xs text-muted-foreground flex-1">
        <CalendarDays className="size-3" />
        {until ? new Date(until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Unknown Date'}
      </span>
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
  const [ignoredClaimKeys, setIgnoredClaimKeys] = useState<Set<string>>(new Set());
  const [extracting, setExtracting] = useState(false);
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
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setExtracting(true);
      try {
        const response = await extractClaims(content);
        setExtractedClaims(response.claims.map(toReviewClaim));
      } catch {
        setExtractedClaims([]);
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
    setIgnoredClaimKeys(new Set());
    setShowClaimForm(false);
    setDraft(emptyDraft());
    setError('');
  }

  function handleClose(val: boolean) {
    if (!val) resetModal();
    onOpenChange(val);
  }

  function addClaim() {
    if (!draft.asset_id || !draft.direction || !draft.percentage || !draft.until) {
      setError('Fill all claim fields before adding.');
      return;
    }
    const pct = parseFloat(draft.percentage);
    if (isNaN(pct) || pct < 0.1 || pct > 1000) {
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
    setClaims((prev) => [...prev, { ...draft, direction: draft.direction as ClaimDirection }]);
    setDraft(emptyDraft());
    setShowClaimForm(false);
  }

  function removeClaim(idx: number) {
    setClaims((prev) => {
      const target = prev[idx];
      const key = `${target.assetSymbol || 'null'}-${target.direction.toLowerCase()}-${target.percentage || 'null'}-${target.until || 'null'}`;
      setIgnoredClaimKeys(keys => new Set(keys).add(key));
      return prev.filter((_, i) => i !== idx);
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
            direction: c.direction,
            percentage: parseFloat(c.percentage),
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
          </div>

          {/* ── Auto-extracted claims ───────────────────────── */}
          {(extracting || extractedClaims.length > 0) && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                {extracting ? 'Analysing…' : 'Detected Claims'}
              </p>

              {/* Waiting to be added */}
              <div className="space-y-1.5">
                {extractedClaims
                  .filter((c) => {
                    const key = `${c.asset || 'null'}-${c.direction}-${c.percentage || 'null'}-${c.until || 'null'}`;
                    if (ignoredClaimKeys.has(key)) return false;
                    const isAttached = claims.some((ac) => {
                      const dir = ac.direction.toLowerCase();
                      return `${ac.assetSymbol || 'null'}-${dir}-${ac.percentage || 'null'}-${ac.until || 'null'}` === key;
                    });
                    return !isAttached;
                  })
                  .map((c, i) => {
                    const hasMissingFields = !c.asset || !c.percentage || !c.until;
                    return (
                      <div key={i} className="flex items-center gap-2">
                        <div className="flex-1">
                          <ClaimViewer
                            assetSymbol={c.asset}
                            direction={c.direction as any}
                            percentage={c.percentage!}
                            until={c.until!}
                          />
                        </div>
                        <div className="flex items-center">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            disabled={hasMissingFields}
                            onClick={() => {
                              const asset = assets.find((a) => a.symbol === c.asset);
                              if (asset) {
                                const newClaim: AttachedClaim = {
                                  asset_id: asset.id.toString(),
                                  assetSymbol: asset.symbol,
                                  direction: c.direction === 'bullish' ? 'Bullish' : 'Bearish',
                                  percentage: c.percentage!,
                                  until: c.until!,
                                  stakeRep: '10',
                                };
                                setClaims((prev) => [...prev, newClaim]);
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
                                direction: c.direction === 'bullish' ? 'Bullish' : 'Bearish',
                                percentage: c.percentage || '',
                                until: c.until || '',
                                stakeRep: '10',
                              });
                              setShowClaimForm(true);
                              const key = `${c.asset || 'null'}-${c.direction}-${c.percentage || 'null'}-${c.until || 'null'}`;
                              setIgnoredClaimKeys((keys) => new Set(keys).add(key));
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            onClick={() => {
                              const key = `${c.asset || 'null'}-${c.direction}-${c.percentage || 'null'}-${c.until || 'null'}`;
                              setIgnoredClaimKeys((keys) => new Set(keys).add(key));
                            }}
                          >
                            Dismiss
                          </Button>
                        </div>
                      </div>
                    );
                  })}
              </div>
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
                        direction={c.direction}
                        percentage={c.percentage}
                        until={c.until}
                      />
                    </div>
                    <button
                      onClick={() => removeClaim(i)}
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

              {/* Asset */}
              <div className="space-y-1">
                <Label className="text-xs">Asset</Label>
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

              {/* Direction */}
              <div className="space-y-1">
                <Label className="text-xs">Direction</Label>
                <div className="flex gap-2">
                  {(['Bullish', 'Bearish'] as const).map((dir) => (
                    <button
                      key={dir}
                      onClick={() => setDraft((d) => ({ ...d, direction: dir }))}
                      className={[
                        'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg border text-xs font-semibold transition-all duration-150',
                        draft.direction === dir
                          ? dir === 'Bullish'
                            ? 'bg-emerald-500 text-white border-emerald-500'
                            : 'bg-red-500 text-white border-red-500'
                          : 'border-border text-muted-foreground hover:text-foreground',
                      ].join(' ')}
                    >
                      {dir === 'Bullish' ? (
                        <TrendingUp className="size-3.5" />
                      ) : (
                        <TrendingDown className="size-3.5" />
                      )}
                      {dir}
                    </button>
                  ))}
                </div>
              </div>

              {/* Percentage + Date — side by side */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Target move (%)</Label>
                  <Input
                    type="number"
                    min="0.1"
                    max="1000"
                    step="0.1"
                    placeholder="e.g. 25"
                    value={draft.percentage}
                    onChange={(e) => setDraft((d) => ({ ...d, percentage: e.target.value }))}
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
