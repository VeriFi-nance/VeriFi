import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PenSquare, Plus, Pencil, X, TrendingUp, ArrowLeft, ArrowRight } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { createPost } from '@/lib/api';
import { fetchAssets } from '@/hooks/useAssets';
import type { AssetItem, ReviewClaim } from '@/lib/types';
import { getClaimType } from '@/lib/claims';
import { AssetCombobox } from '@/components/AssetCombobox';
import { PostComposer, MAX_CHARS } from './PostComposer';
import { ClaimForm } from './ClaimForm';
import { ClaimWizard } from './ClaimWizard';
import { ClaimRow } from './ClaimRow';
import {
  emptyDraft,
  validateDraft,
  type AttachedClaim,
  type ClaimDraft,
  type WizardNavState,
} from './types';
import { buildClaimPayload, buildPositionPayload } from '@/lib/payloads';
import { signPayload, resolveUsername } from '@/lib/signing';
import { PositionWizard, defaultPositionDraft, type PositionDraft } from './PositionWizard';
import { cn, safeImageSrc } from '@/lib/utils';

interface NewPostModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPosted: () => void;
  channelId?: number;
}

export function NewPostModal({ open, onOpenChange, onPosted, channelId }: NewPostModalProps) {
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const [phase, setPhase] = useState<'compose' | 'attach'>('compose');
  const [content, setContent] = useState('');
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attached, setAttached] = useState<AttachedClaim[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft());
  const [showDraft, setShowDraft] = useState(false);
  const [wizardMode, setWizardMode] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  // Position draft state
  const [showPositionForm, setShowPositionForm] = useState(false);
  const [posWizardMode, setPosWizardMode] = useState(true);
  const [posDraft, setPosDraft] = useState<PositionDraft>(defaultPositionDraft());
  const [posError, setPosError] = useState('');
  const [posAttached, setPosAttached] = useState<PositionDraft | null>(null);
  // Nav state reported up by whichever sub-wizard is open, so the modal footer
  // can render Previous/Next instead of Cancel/Post.
  const [claimNav, setClaimNav] = useState<WizardNavState | null>(null);
  const [posNav, setPosNav] = useState<WizardNavState | null>(null);



  useEffect(() => {
    if (open) {
      fetchAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  // Revoke the object URL when the preview changes or the modal unmounts.
  useEffect(() => {
    return () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview);
    };
  }, [imagePreview]);

  function pickImage(file: File | null) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Image must be 10 MB or smaller.');
      return;
    }
    setError('');
    setImage(file);
    setImagePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
  }

  function clearImage() {
    setImage(null);
    setImagePreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function reset() {
    setPhase('compose');
    setContent('');
    clearImage();
    setAttached([]);
    setDraft(emptyDraft());
    setShowDraft(false);
    setError('');
    setShowPositionForm(false);
    setPosWizardMode(true);
    setPosDraft(defaultPositionDraft());
    setPosError('');
    setPosAttached(null);
    setClaimNav(null);
    setPosNav(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function patchDraft(patch: Partial<ClaimDraft>) {
    setDraft((d) => ({ ...d, ...patch }));
  }

  // Merge an asset selected/resolved via the search combobox into the known
  // list so validateDraft and the symbol/parity lookups below can find it.
  function registerAsset(asset: AssetItem) {
    setAssets((prev) => (prev.some((a) => a.id === asset.id) ? prev : [...prev, asset]));
  }

  function addDraft(customDraft?: ClaimDraft): boolean {
    const d = customDraft || draft;
    const result = validateDraft(d, assets);
    if (!result.ok) {
      setError(result.error);
      return false;
    }
    setError('');
    setAttached((prev) => [
      ...prev,
      {
        asset_id: d.asset_id,
        assetSymbol: d.assetSymbol,
        claim_type: result.value.claim_type,
        direction: result.value.direction,
        percentage: d.percentage,
        until: d.until,
        stakeRep: d.stakeRep,
      },
    ]);
    setDraft(emptyDraft());
    setShowDraft(false);
    return true;
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
    setWizardMode(true);
    setError('');
    setPhase('attach');
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
    setWizardMode(true);
    setPhase('attach');
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
      if (posAttached) {
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

      const shouldRefreshEnergy = hardClaimsPayload.some((claim) => claim.market);
      await createPost(
        content.trim(),
        channelId,
        hardClaimsPayload,
        positionsPayload.length > 0 ? (positionsPayload as any) : undefined,
        image,
      );
      if (shouldRefreshEnergy) {
        window.dispatchEvent(new Event('energy-updated'));
      }
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
  const canAdvanceToAttach = content.trim().length > 0 && !overLimit;

  // Footer routing: a sub-wizard drives nav; manual forms own their buttons.
  const wizardActive = (showDraft && wizardMode) || (showPositionForm && posWizardMode);
  const manualFormOpen = (showDraft && !wizardMode) || (showPositionForm && !posWizardMode);
  const activeNav: WizardNavState | null = showDraft ? claimNav : showPositionForm ? posNav : null;

  function cancelActiveWizard() {
    if (showDraft) {
      setShowDraft(false);
      setDraft(emptyDraft());
      setError('');
      setClaimNav(null);
    } else if (showPositionForm) {
      setShowPositionForm(false);
      setPosDraft(defaultPositionDraft());
      setPosError('');
      setPosNav(null);
    }
  }

  return (
    <RD.Root open={open} onOpenChange={handleOpenChange}>
      <RD.Content className="md:max-w-lg">
        <RD.Header>
          <RD.Title>New Post</RD.Title>
          <RD.Description>
            Share a take, attach verifiable claims, open a reputation market.
          </RD.Description>
        </RD.Header>

        <div className="space-y-4 max-h-[60dvh] md:max-h-[65vh] overflow-y-auto -mx-5 px-5 md:-mx-6 md:px-6 pt-2">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {phase === 'compose' && (
            <>
              <PostComposer
                content={content}
                onContentChange={setContent}
                attached={attached}
                assets={assets}
                onAddExtracted={(c) => setAttached((prev) => [...prev, c])}
                onEditExtracted={loadExtractedIntoDraft}
                onAttachImage={() => fileInputRef.current?.click()}
                onPasteImage={(file) => pickImage(file)}
              />

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pickImage(e.target.files?.[0] ?? null)}
              />
              {imagePreview && (
                <div className="relative w-full overflow-hidden rounded-lg border border-border">
                  <img src={safeImageSrc(imagePreview)} alt="" className="w-full max-h-72 object-cover" />
                  <button
                    type="button"
                    onClick={clearImage}
                    aria-label="Remove image"
                    className="absolute top-2 right-2 size-7 flex items-center justify-center rounded-full bg-background/80 text-foreground hover:bg-background transition-colors"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              )}
            </>
          )}

          {phase === 'attach' && (
          <>
          {/* Post recap so the user keeps context while attaching. */}
          <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Your post</p>
            <p className="text-sm whitespace-pre-wrap break-words line-clamp-3">{content || <span className="text-muted-foreground">No text</span>}</p>
            {imagePreview && (
              <img src={safeImageSrc(imagePreview)} alt="" className="w-full max-h-32 object-cover rounded-md border border-border" />
            )}
          </div>

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

          {/* ── Attached Position Display ──────────────── */}
          {posAttached && !showPositionForm && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-position-badge">
                Attached position
              </p>
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0 flex items-center justify-between border border-position-badge/20 bg-position-badge/5 rounded-md px-3 py-2">
                  <div className="flex items-center gap-2 text-xs">
                    <TrendingUp className="size-3.5 text-position-badge" />
                    <span className="font-semibold text-position-badge">
                      {assets.find((a) => a.id.toString() === posAttached.assetId)?.symbol || 'Asset'}
                    </span>
                    <span className="text-muted-foreground uppercase font-medium">
                      {posAttached.direction}
                    </span>
                    <span className="text-muted-foreground ml-2">Entry: <span className="text-foreground">{posAttached.entryPrice}</span></span>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setPosDraft(posAttached);
                    setPosAttached(null);
                    setShowPositionForm(true);
                    setPosWizardMode(false);
                  }}
                  title="Edit position"
                  className="size-6 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  aria-label="Edit position"
                >
                  <Pencil className="size-3.5" />
                </button>
                <button
                  onClick={() => setPosAttached(null)}
                  title="Remove position"
                  className="size-6 flex items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                  aria-label="Remove position"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* ── Position Form ──────────────── */}
          {showPositionForm && (
            <div className="space-y-3">
              {posWizardMode ? (
                <PositionWizard
                  registerAsset={registerAsset}
                  initialDraft={posDraft}
                  onNav={setPosNav}
                  onComplete={(pd) => {
                    setPosAttached(pd);
                    setShowPositionForm(false);
                    setPosError('');
                    setPosNav(null);
                  }}
                  onCancel={() => {
                    setShowPositionForm(false);
                    setPosDraft(defaultPositionDraft());
                    setPosError('');
                    setPosNav(null);
                  }}
                  onFillManually={() => { setPosWizardMode(false); setPosNav(null); }}
                />
              ) : (
                <div className="p-3 border border-position-badge/20 rounded-lg space-y-3 bg-position-badge/5">
                  {posError && (
                    <p className="text-[11px] text-destructive">{posError}</p>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-[11px]">Asset</Label>
                      <AssetCombobox
                        size="sm"
                        placeholder="Select"
                        selectedLabel={posDraft.assetSymbol}
                        onSelect={(a) => {
                          registerAsset(a);
                          setPosDraft((p) => ({ ...p, assetId: a.id.toString(), assetSymbol: a.symbol }));
                        }}
                      />
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
                      className="flex-1 text-xs h-7 bg-indigo-500 hover:bg-indigo-600 text-white"
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
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs text-muted-foreground hover:bg-muted"
                      onClick={() => { setShowPositionForm(false); setPosDraft(defaultPositionDraft()); }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Claim Form ──────────────── */}
          {showDraft && (
            wizardMode ? (
              <ClaimWizard
                registerAsset={registerAsset}
                initialDraft={draft}
                onNav={setClaimNav}
                onComplete={(d) => { if (addDraft(d)) setClaimNav(null); }}
                onCancel={() => {
                  setShowDraft(false);
                  setDraft(emptyDraft());
                  setError('');
                  setClaimNav(null);
                }}
                onFillManually={() => { setWizardMode(false); setClaimNav(null); }}
              />
            ) : (
              <ClaimForm
                value={draft}
                registerAsset={registerAsset}
                onChange={patchDraft}
                onSubmit={() => addDraft()}
                onCancel={() => {
                  setShowDraft(false);
                  setDraft(emptyDraft());
                  setError('');
                }}
              />
            )
          )}

          {/* ── Buttons ──────────────── */}
          {(!showDraft && !showPositionForm) && (
            <div className="flex gap-2">
              {!posAttached && (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 gap-2 border-dashed border-claim-badge/30 text-claim-badge hover:text-claim-badge/80 hover:border-claim-badge/50 hover:bg-claim-badge/10"
                  onClick={() => {
                    setShowDraft(true);
                    setWizardMode(true);
                    setError('');
                  }}
                >
                  <Plus className="size-3.5" />
                  {attached.length > 0 ? 'Add another claim' : 'Add claim'}
                </Button>
              )}

              {attached.length === 0 && !posAttached && (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 gap-2 border-dashed border-position-badge/30 text-position-badge hover:text-position-badge/80 hover:border-position-badge/50 hover:bg-position-badge/10"
                  onClick={() => {
                    setShowPositionForm(true);
                    setPosWizardMode(true);
                    setPosError('');
                  }}
                >
                  <TrendingUp className="size-3.5" />
                  Add position
                </Button>
              )}
            </div>
          )}
          </>
          )}
        </div>

        <RD.Footer className="border-t border-border pt-4 md:pt-5 -mx-5 px-5 md:-mx-6 md:px-6 sm:items-center">
          {wizardActive ? (
            // A sub-wizard owns navigation: Cancel | Previous | Next.
            <>
              <div className="sm:mr-auto" />
              <Button variant="ghost" size="sm" onClick={cancelActiveWizard}>
                Cancel
              </Button>
              {activeNav && !activeNav.isFirstStep && (
                <Button variant="outline" size="sm" onClick={activeNav.back} className="gap-1.5">
                  <ArrowLeft className="size-3.5" />
                  Previous
                </Button>
              )}
              <Button
                size="sm"
                disabled={!activeNav?.canNext}
                onClick={() => activeNav?.next()}
                className="gap-1.5"
              >
                {activeNav?.nextLabel ?? 'Next'}
                <ArrowRight className="size-3.5" />
              </Button>
            </>
          ) : manualFormOpen ? (
            // Manual claim/position forms render their own buttons inline.
            <div className="sm:mr-auto" />
          ) : phase === 'compose' ? (
            <>
              <div className="sm:mr-auto" />
              <Button variant="outline" size="sm" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button size="sm" disabled={!canAdvanceToAttach} onClick={() => setPhase('attach')} className="gap-1.5">
                Next
                <ArrowRight className="size-3.5" />
              </Button>
            </>
          ) : (
            <>
              <div className="sm:mr-auto" />
              <Button variant="outline" size="sm" onClick={() => setPhase('compose')} className="gap-1.5">
                <ArrowLeft className="size-3.5" />
                Back
              </Button>
              <Button size="sm" disabled={!canSubmit} onClick={submit} className="gap-1.5">
                <PenSquare className="size-3.5" />
                {submitting ? 'Posting…' : 'Post'}
              </Button>
            </>
          )}
        </RD.Footer>
      </RD.Content>
    </RD.Root>
  );
}

/** Trigger button — opens the modal or redirects to login if unauthenticated. */
export function NewPostButton({
  onPosted,
  channelId,
  compactOnMobile = false,
}: {
  onPosted: () => void;
  channelId?: number;
  compactOnMobile?: boolean;
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
      <Button
        size="sm"
        className="shrink-0 gap-2 font-medium"
        onClick={handleClick}
        aria-label="New post"
      >
        <PenSquare className="size-4" />
        <span className={cn(compactOnMobile && 'hidden sm:inline')}>New post</span>
      </Button>
      <NewPostModal
        open={open}
        onOpenChange={setOpen}
        onPosted={onPosted}
        channelId={channelId}
      />
    </>
  );
}
