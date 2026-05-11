import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PenSquare, Plus, X, TrendingUp, TrendingDown, CalendarDays } from 'lucide-react';
import { createPost, createHardClaim, getAssets } from '@/lib/api';
import { isAuthenticated } from '@/lib/auth';
import type { AssetItem } from '@/lib/types';

const MAX_CHARS = 500;

interface ClaimDraft {
  asset_id: string;       // asset id (for HardClaim)
  assetSymbol: string;    // display
  direction: 'Bullish' | 'Bearish' | '';
  percentage: string;
  until: string;
}

function emptyDraft(): ClaimDraft {
  return { asset_id: '', assetSymbol: '', direction: '', percentage: '', until: '' };
}

interface NewPostModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPosted: () => void;
}

export function NewPostModal({ open, onOpenChange, onPosted }: NewPostModalProps) {
  const [content, setContent] = useState('');
  const [claims, setClaims] = useState<ClaimDraft[]>([]);
  const [showClaimForm, setShowClaimForm] = useState(false);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft());
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      getAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  function resetModal() {
    setContent('');
    setClaims([]);
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
    setError('');
    setClaims((prev) => [...prev, { ...draft }]);
    setDraft(emptyDraft());
    setShowClaimForm(false);
  }

  function removeClaim(idx: number) {
    setClaims((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit() {
    if (!content.trim()) return;
    setError('');
    setSubmitting(true);
    try {
      // 1. Create the post (no attached claims on the post itself)
      const newPost = await createPost(content.trim(), []);

      // 2. Create each HardClaim, linked to the new post
      await Promise.all(
        claims.map((c) =>
          createHardClaim({
            asset_id: parseInt(c.asset_id, 10),
            post_id: newPost.id,
            direction: c.direction,
            percentage: parseFloat(c.percentage),
            until: c.until,
          })
        )
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

          {/* ── Added claims ────────────────────────────────── */}
          {claims.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Attached Claims
              </p>
              {claims.map((c, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-lg border px-3 py-2 bg-muted/40"
                >
                  {/* Direction dot */}
                  <span
                    className={`size-2 rounded-full shrink-0 ${
                      c.direction === 'Bullish' ? 'bg-emerald-500' : 'bg-red-500'
                    }`}
                  />
                  <span className="font-mono font-semibold text-xs">{c.assetSymbol}</span>
                  <Badge
                    variant={c.direction === 'Bullish' ? 'success' : 'destructive'}
                    className="text-[10px] px-1.5 py-0"
                  >
                    {c.direction === 'Bullish' ? '▲' : '▼'} {parseFloat(c.percentage).toFixed(1)}%
                  </Badge>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground flex-1">
                    <CalendarDays className="size-3" />
                    {new Date(c.until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </span>
                  <button
                    onClick={() => removeClaim(i)}
                    className="ml-auto size-5 flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
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
export function NewPostButton({ onPosted }: { onPosted: () => void }) {
  const [open, setOpen] = useState(false);
  const authed = isAuthenticated();
  if (!authed) return null;

  return (
    <>
      <Button
        size="sm"
        className="gap-2 font-semibold bg-emerald-300/90 text-gray-900 border border-emerald-500/50 hover:bg-emerald-500/90 shadow-[0_0_18px_rgba(16,185,129,0.5)] rounded-xl"
        onClick={() => setOpen(true)}
      >
        <PenSquare className="size-4" />
        New Post
      </Button>
      <NewPostModal open={open} onOpenChange={setOpen} onPosted={onPosted} />
    </>
  );
}
