import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PenSquare, Plus, Pencil, X, TrendingUp, ChevronDown } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { createPost, getAssets } from '@/lib/api';
import type { AssetItem, ReviewClaim } from '@/lib/types';
import { getClaimType } from '@/lib/claims';
import { PostComposer, MAX_CHARS } from './PostComposer';
import { ClaimForm } from './ClaimForm';
import { ClaimRow } from './ClaimRow';
import {
  emptyDraft,
  validateDraft,
  type AttachedClaim,
  type ClaimDraft,
} from './types';
import { buildClaimPayload, buildPositionPayload } from '@/lib/payloads';
import { signPayload, resolveUsername } from '@/lib/signing';

interface PositionDraft {
  assetId: string;
  direction: 'long' | 'short';
  entryPrice: string;
  stopLoss: string;
  takeProfit: string;
  entryInterval: string;
  lifetime: string;
}

function defaultPositionDraft(): PositionDraft {
  const entry = new Date();
  entry.setDate(entry.getDate() + 2);
  const life = new Date();
  life.setDate(life.getDate() + 7);
  return {
    assetId: '',
    direction: 'long',
    entryPrice: '',
    stopLoss: '',
    takeProfit: '',
    entryInterval: entry.toISOString().slice(0, 16),
    lifetime: life.toISOString().slice(0, 16),
  };
}

interface NewPostModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPosted: () => void;
  channelId?: number;
  /** Pre-fetched channel creator address to enable position attachment UI */
  channelCreatorAddress?: string;
}

export function NewPostModal({ open, onOpenChange, onPosted, channelId, channelCreatorAddress }: NewPostModalProps) {
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const [content, setContent] = useState('');
  const [attached, setAttached] = useState<AttachedClaim[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft());
  const [showDraft, setShowDraft] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  // Position draft state
  const [showPositionForm, setShowPositionForm] = useState(false);
  const [posDraft, setPosDraft] = useState<PositionDraft>(defaultPositionDraft());
  const [posError, setPosError] = useState('');
  const [posAttached, setPosAttached] = useState<PositionDraft | null>(null);

  const isChannelCreator =
    !!channelId &&
    !!channelCreatorAddress &&
    !!auth.address &&
    auth.address.toLowerCase() === channelCreatorAddress.toLowerCase();

  useEffect(() => {
    if (open) {
      getAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  function reset() {
    setContent('');
    setAttached([]);
    setDraft(emptyDraft());
    setShowDraft(false);
    setError('');
    setShowPositionForm(false);
    setPosDraft(defaultPositionDraft());
    setPosError('');
    setPosAttached(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function patchDraft(patch: Partial<ClaimDraft>) {
    setDraft((d) => ({ ...d, ...patch }));
  }

  function addDraft() {
    const result = validateDraft(draft, assets);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError('');
    setAttached((prev) => [
      ...prev,
      {
        asset_id: draft.asset_id,
        assetSymbol: draft.assetSymbol,
        claim_type: result.value.claim_type,
        direction: result.value.direction,
        percentage: draft.percentage,
        until: draft.until,
        stakeRep: draft.stakeRep,
      },
    ]);
    setDraft(emptyDraft());
    setShowDraft(false);
  }

  function removeAttached(idx: number) {
    setAttached((prev) => prev.filter((_, i) => i !== idx));
  }

  function editAttached(idx: number) {
    const c = attached[idx];
    if (!c) return;
    setDraft({
      asset_id: c.asset_id,
      assetSymbol: c.assetSymbol,
      claim_type: c.claim_type,
      direction: c.direction,
      percentage: c.percentage,
      until: c.until,
      stakeRep: c.stakeRep,
    });
    setAttached((prev) => prev.filter((_, i) => i !== idx));
    setShowDraft(true);
    setError('');
  }

  function loadExtractedIntoDraft(c: ReviewClaim) {
    let combinedSymbol = c.asset;
    if (c.parity) {
      combinedSymbol = `${c.asset}/${c.parity}`;
    }
    const asset = assets.find((a) => a.symbol === combinedSymbol) || assets.find((a) => a.symbol === c.asset);
    const claimType = getClaimType(c);
    setDraft({
      asset_id: asset ? asset.id.toString() : '',
      assetSymbol: asset?.symbol ?? combinedSymbol,
      claim_type: claimType,
      direction: claimType === 'PERCENTAGE_DOWN' ? 'Bearish' : 'Bullish',
      percentage: c.percentage ?? '',
      until: c.until ?? '',
      stakeRep: '10',
    });
    setShowDraft(true);
  }

  async function submit() {
    if (!content.trim()) return;
    if (!auth.authenticated) {
      openLogin();
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      const hardClaimsPayload = [];
      for (const c of attached) {
        const payloadObj = {
          asset_symbol: c.assetSymbol,
          author_username: await resolveUsername(),
          direction: c.direction,
          percentage: parseFloat(c.percentage),
          until: c.until,
          created_at: new Date().toISOString(),
        };
        const payloadStr = buildClaimPayload(payloadObj);
        const signature = await signPayload(payloadStr);

        const stakeNum = parseFloat(c.stakeRep);
        const market =
          !isNaN(stakeNum) && stakeNum >= 10 && stakeNum <= 100
            ? { side: 'YES' as const, stake_rep: stakeNum }
            : undefined;

        hardClaimsPayload.push({
          asset_id: parseInt(c.asset_id, 10),
          channel_id: channelId,
          direction: c.direction,
          value_type: c.claim_type,
          percentage: parseFloat(c.percentage),
          until: c.until,
          signature,
          claim_payload: payloadObj,
          ...(market ? { market } : {}),
        });
      }

      // Build positions payload
      let positionsPayload: Record<string, unknown>[] = [];
      if (posAttached && channelId && isChannelCreator) {
        const pd = posAttached;
        const selectedAsset = assets.find((a) => a.id.toString() === pd.assetId);
        const entry = parseFloat(pd.entryPrice);
        const sl = parseFloat(pd.stopLoss);
        const tp = parseFloat(pd.takeProfit);
        const payloadObj = {
          asset_symbol: selectedAsset?.symbol || '',
          author_username: await resolveUsername(),
          direction: pd.direction,
          entry_price: entry,
          stop_loss: sl,
          take_profit: tp,
          lifetime: new Date(pd.lifetime).toISOString(),
          created_at: new Date().toISOString(),
        };
        const payloadStr = buildPositionPayload(payloadObj);
        const signature = await signPayload(payloadStr);
        positionsPayload = [{
          channel_id: channelId,
          asset_id: parseInt(pd.assetId, 10),
          direction: pd.direction,
          entry_price: entry,
          entry_interval: new Date(pd.entryInterval).toISOString(),
          stop_loss: sl,
          take_profit: tp,
          lifetime: new Date(pd.lifetime).toISOString(),
          signature,
          position_payload: payloadObj,
        }];
      }

      await createPost(content.trim(), channelId, hardClaimsPayload, positionsPayload.length > 0 ? positionsPayload as any : undefined);
      reset();
      onOpenChange(false);
      onPosted();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to post.');
    } finally {
      setSubmitting(false);
    }
  }

  const overLimit = content.length > MAX_CHARS;
  const canSubmit = content.trim().length > 0 && !overLimit && !submitting;

  return (
    <RD.Root open={open} onOpenChange={handleOpenChange}>
      <RD.Content className="md:max-w-lg">
        <RD.Header>
          <RD.Title>New Post</RD.Title>
          <RD.Description>
            Share a take, attach verifiable claims, open a reputation market.
          </RD.Description>
        </RD.Header>

        <div className="space-y-4 max-h-[60dvh] md:max-h-[65vh] overflow-y-auto -mx-5 px-5 md:-mx-6 md:px-6">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <PostComposer
            content={content}
            onContentChange={setContent}
            attached={attached}
            assets={assets}
            onAddExtracted={(c) => setAttached((prev) => [...prev, c])}
            onEditExtracted={loadExtractedIntoDraft}
          />

          {attached.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Attached claims
              </p>
              <div className="space-y-1.5">
                {attached.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <ClaimRow
                        assetSymbol={c.assetSymbol}
                        direction={c.direction}
                        percentage={c.percentage}
                        until={c.until}
                        claim_type={c.claim_type}
                        parity={assets.find(a => a.id.toString() === c.asset_id)?.quote_currency}
                      />
                    </div>
                    <button
                      onClick={() => editAttached(i)}
                      title="Edit claim"
                      className="size-6 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      aria-label="Edit claim"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                    <button
                      onClick={() => removeAttached(i)}
                      className="size-6 flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                      aria-label="Remove claim"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Position attachment (channel creator only) ──────────────── */}
          {isChannelCreator && (
            <div className="border border-dashed border-indigo-500/20 rounded-lg">
              <button
                type="button"
                onClick={() => setShowPositionForm((s) => !s)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <TrendingUp className="size-3.5" />
                  {posAttached ? 'Position attached ✓' : 'Attach a position'}
                </span>
                <ChevronDown className={`size-3.5 transition-transform ${showPositionForm ? 'rotate-180' : ''}`} />
              </button>

              {showPositionForm && (
                <div className="px-3 pb-3 space-y-3 border-t border-indigo-500/10 pt-3">
                  {posError && (
                    <p className="text-[11px] text-destructive">{posError}</p>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-[11px]">Asset</Label>
                      <Select
                        value={posDraft.assetId}
                        onValueChange={(v) => setPosDraft((p) => ({ ...p, assetId: v }))}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                        <SelectContent>
                          {assets.map((a) => (
                            <SelectItem key={a.id} value={a.id.toString()} className="text-xs">
                              {a.symbol}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-[11px]">Direction</Label>
                      <Select
                        value={posDraft.direction}
                        onValueChange={(v: 'long' | 'short') => setPosDraft((p) => ({ ...p, direction: v }))}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="long" className="text-xs">Long ↑</SelectItem>
                          <SelectItem value="short" className="text-xs">Short ↓</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    {([
                      ['entryPrice', 'Entry Price'],
                      ['stopLoss', 'Stop Loss'],
                      ['takeProfit', 'Take Profit'],
                    ] as const).map(([field, label]) => (
                      <div key={field} className="space-y-1">
                        <Label className="text-[11px]">{label}</Label>
                        <Input
                          type="number"
                          step="any"
                          className="h-8 text-xs"
                          value={posDraft[field]}
                          onChange={(e) => setPosDraft((p) => ({ ...p, [field]: e.target.value }))}
                        />
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-[11px]">Entry By</Label>
                      <Input
                        type="datetime-local"
                        className="h-8 text-xs"
                        value={posDraft.entryInterval}
                        onChange={(e) => setPosDraft((p) => ({ ...p, entryInterval: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[11px]">Expires At</Label>
                      <Input
                        type="datetime-local"
                        className="h-8 text-xs"
                        value={posDraft.lifetime}
                        onChange={(e) => setPosDraft((p) => ({ ...p, lifetime: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      className="flex-1 text-xs h-7"
                      onClick={() => {
                        setPosError('');
                        if (!posDraft.assetId) { setPosError('Select an asset.'); return; }
                        const en = parseFloat(posDraft.entryPrice);
                        const sl = parseFloat(posDraft.stopLoss);
                        const tp = parseFloat(posDraft.takeProfit);
                        if (isNaN(en) || isNaN(sl) || isNaN(tp)) { setPosError('Enter valid prices.'); return; }
                        if (posDraft.direction === 'long' && !(sl < en && en < tp)) { setPosError('SL < Entry < TP for LONG.'); return; }
                        if (posDraft.direction === 'short' && !(tp < en && en < sl)) { setPosError('TP < Entry < SL for SHORT.'); return; }
                        if (new Date(posDraft.entryInterval) <= new Date()) { setPosError('Entry must be in the future.'); return; }
                        if (new Date(posDraft.lifetime) <= new Date(posDraft.entryInterval)) { setPosError('Lifetime must be after entry interval.'); return; }
                        setPosAttached({ ...posDraft });
                        setShowPositionForm(false);
                      }}
                    >
                      Attach Position
                    </Button>
                    {posAttached && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-destructive hover:bg-destructive/10"
                        onClick={() => { setPosAttached(null); }}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {showDraft ? (
            <ClaimForm
              value={draft}
              assets={assets}
              onChange={patchDraft}
              onSubmit={addDraft}
              onCancel={() => {
                setShowDraft(false);
                setDraft(emptyDraft());
                setError('');
              }}
            />
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 border-dashed text-muted-foreground hover:text-foreground"
              onClick={() => {
                setShowDraft(true);
                setError('');
              }}
            >
              <Plus className="size-3.5" />
              Add claim
            </Button>
          )}
        </div>

        <RD.Footer className="border-t border-border pt-3 -mx-5 px-5 md:-mx-6 md:px-6">
          <p className="text-xs text-muted-foreground sm:mr-auto">
            {attached.length > 0
              ? `${attached.length} claim${attached.length !== 1 ? 's' : ''} attached`
              : 'No claims yet'}
          </p>
          <Button variant="outline" size="sm" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button size="sm" disabled={!canSubmit} onClick={submit} className="gap-1.5">
            <PenSquare className="size-3.5" />
            {submitting ? 'Posting…' : 'Post'}
          </Button>
        </RD.Footer>
      </RD.Content>
    </RD.Root>
  );
}

/** Trigger button — opens the modal or redirects to login if unauthenticated. */
export function NewPostButton({
  onPosted,
  channelId,
  channelCreatorAddress,
}: {
  onPosted: () => void;
  channelId?: number;
  channelCreatorAddress?: string;
}) {
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const [open, setOpen] = useState(false);

  function handleClick() {
    if (!auth.authenticated) {
      openLogin();
      return;
    }
    setOpen(true);
  }

  return (
    <>
      <Button size="sm" className="gap-2 font-medium" onClick={handleClick}>
        <PenSquare className="size-4" />
        New post
      </Button>
      <NewPostModal
        open={open}
        onOpenChange={setOpen}
        onPosted={onPosted}
        channelId={channelId}
        channelCreatorAddress={channelCreatorAddress}
      />
    </>
  );
}
