import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PenSquare, Plus, X } from 'lucide-react';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';
import { createPost, createHardClaim, getAssets } from '@/lib/api';
import type { AssetItem, ReviewClaim } from '@/lib/types';
import { PostComposer, MAX_CHARS } from './PostComposer';
import { ClaimForm } from './ClaimForm';
import { ClaimRow } from './ClaimRow';
import { emptyDraft, validateDraft, type AttachedClaim, type ClaimDraft } from './types';

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
  const [attached, setAttached] = useState<AttachedClaim[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft);
  const [showDraft, setShowDraft] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

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
      { ...draft, direction: result.value.direction },
    ]);
    setDraft(emptyDraft());
    setShowDraft(false);
  }

  function removeAttached(idx: number) {
    setAttached((prev) => prev.filter((_, i) => i !== idx));
  }

  function loadExtractedIntoDraft(c: ReviewClaim) {
    const asset = assets.find((a) => a.symbol === c.asset);
    setDraft({
      asset_id: asset ? asset.id.toString() : '',
      assetSymbol: asset?.symbol ?? '',
      direction: c.direction === 'bullish' ? 'Bullish' : 'Bearish',
      percentage: c.percentage ?? '',
      until: c.until ?? '',
      stakeRep: '10',
    });
    setShowDraft(true);
  }

  async function submit() {
    if (!content.trim()) return;
    if (!auth.authenticated) {
      navigate(loginPathWithReturn(location.pathname), { replace: true });
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      const newPost = await createPost(content.trim(), [], communityId);
      await Promise.all(
        attached.map((c) => {
          const stakeNum = parseFloat(c.stakeRep);
          const market =
            !isNaN(stakeNum) && stakeNum >= 10 && stakeNum <= 100
              ? { side: 'YES' as const, stake_rep: stakeNum }
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
        }),
      );
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
                      />
                    </div>
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
  communityId,
}: {
  onPosted: () => void;
  communityId?: number;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuthState();
  const [open, setOpen] = useState(false);

  function handleClick() {
    if (!auth.authenticated) {
      navigate(loginPathWithReturn(location.pathname), { replace: true });
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
        communityId={communityId}
      />
    </>
  );
}
