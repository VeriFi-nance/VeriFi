import { useEffect, useRef, useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { AlertTriangle, RotateCcw, ImagePlus } from 'lucide-react';
import { ClaimRow } from './ClaimRow';
import { extractClaims } from '@/lib/api';
import { cn, imageFileFromClipboard } from '@/lib/utils';
import type { AssetItem, ReviewClaim } from '@/lib/types';
import {
  dismissKey,
  isClaimComplete,
  isClaimIncomplete,
  toReviewClaim,
} from '@/lib/claims';
import { attachedKey, type AttachedClaim } from './types';

const DEBOUNCE_MS = 700;
export const MAX_CHARS = 500;

interface PostComposerProps {
  content: string;
  onContentChange: (next: string) => void;
  attached: AttachedClaim[];
  assets: AssetItem[];
  onAddExtracted: (claim: AttachedClaim) => void;
  onEditExtracted: (claim: ReviewClaim) => void;
  /** Opens the image file picker. Rendered as an icon inside the input area. */
  onAttachImage?: () => void;
  /** Receives an image pasted into the textarea, treated as an upload. */
  onPasteImage?: (file: File) => void;
}

/**
 * Textarea + auto-extracted claim preview. Doesn't own the attached-claim
 * list; the orchestrator does. The "Add" button on a row forwards to the
 * orchestrator via `onAddExtracted`.
 */
export function PostComposer({
  content,
  onContentChange,
  attached,
  assets,
  onAddExtracted,
  onEditExtracted,
  onAttachImage,
  onPasteImage,
}: PostComposerProps) {
  const [extracted, setExtracted] = useState<ReviewClaim[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState('');
  const [dismissedClaims, setDismissedClaims] = useState<ReviewClaim[]>([]);
  const [showDismissed, setShowDismissed] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!content.trim()) {
      setExtracted([]);
      setDismissedClaims([]);
      setExtractError('');
      return;
    }
    debounceRef.current = setTimeout(async () => {
      if (!active) return;
      setExtracting(true);
      const startTime = Date.now();
      try {
        const res = await extractClaims(content);
        if (!active) return;
        const fresh = res.claims.map(toReviewClaim);

        const elapsed = Date.now() - startTime;
        const delay = Math.max(0, 500 - elapsed);
        if (delay > 0) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
        if (!active) return;

        setExtracted(fresh);
        const freshKeys = new Set(fresh.map(dismissKey));
        setDismissedClaims((prev) => prev.filter((d) => freshKeys.has(dismissKey(d))));
        setExtractError('');
      } catch (e) {
        if (!active) return;
        const elapsed = Date.now() - startTime;
        const delay = Math.max(0, 500 - elapsed);
        if (delay > 0) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
        if (!active) return;
        setExtracted([]);
        setExtractError(e instanceof Error ? e.message : 'Could not analyse claims.');
      } finally {
        if (active) {
          setExtracting(false);
        }
      }
    }, DEBOUNCE_MS);
    return () => {
      active = false;
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [content]);

  function dismissClaim(c: ReviewClaim) {
    setDismissedClaims((prev) =>
      prev.some((d) => dismissKey(d) === dismissKey(c)) ? prev : [...prev, c],
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

  const dismissedKeySet = new Set(dismissedClaims.map(dismissKey));
  const visible = extracted.filter((c) => {
    if (dismissedKeySet.has(dismissKey(c))) return false;
    const key = attachedKey({
      assetSymbol: c.asset,
      direction: c.direction,
      claim_type: c.claim_type,
      percentage: c.percentage,
      until: c.until,
    });
    return !attached.some((ac) =>
      attachedKey({
        assetSymbol: ac.assetSymbol,
        direction: ac.direction,
        claim_type: ac.claim_type,
        percentage: ac.percentage,
        until: ac.until,
      }) === key,
    );
  });

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;

  return (
    <div className="space-y-4">
      <div className="space-y-1.5 p-1">
        <div className="relative">
          <Textarea
            placeholder="What's your financial take?"
            value={content}
            onChange={(e) => onContentChange(e.target.value)}
            onPaste={(e) => {
              const file = imageFileFromClipboard(e.clipboardData);
              if (file && onPasteImage) {
                e.preventDefault();
                onPasteImage(file);
              }
            }}
            rows={4}
            className="resize-none text-sm pb-11"
            maxLength={MAX_CHARS + 50}
            autoFocus
          />
          {onAttachImage && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onAttachImage}
              aria-label="Add image"
              title="Add image"
              className="absolute bottom-2 left-2 size-8 text-primary hover:bg-primary/10 hover:text-primary"
            >
              <ImagePlus className="size-5" />
            </Button>
          )}
        </div>
        <p
          className={cn(
            'text-xs text-right num',
            overLimit
              ? 'text-destructive font-medium'
              : remaining <= 50
              ? 'text-danger'
              : 'text-muted-foreground',
          )}
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

      {extracted.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between h-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Detected claims{visible.length > 0 ? ` (${visible.length})` : ''}
            </p>
          </div>
          <div className={cn('space-y-1.5 transition-opacity duration-200', extracting && 'opacity-50')}>
            {visible.map((c, i) => {
              const complete = isClaimComplete(c);
              const incomplete = isClaimIncomplete(c);
              return (
                <div key={i} className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <ClaimRow
                      assetSymbol={c.asset}
                      direction={c.direction as 'Bullish' | 'Bearish' | 'bullish' | 'bearish'}
                      percentage={c.percentage ?? ''}
                      until={c.until ?? ''}
                      parity={c.parity}
                      claim_type={c.claim_type}
                      incomplete={incomplete}
                      reviewClaim={incomplete ? c : undefined}
                    />
                  </div>
                  <div className="flex items-center shrink-0 pt-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      disabled={!complete}
                      onClick={() => {
                        const asset = assets.find((a) => a.symbol === c.asset);
                        if (!asset) return;
                        onAddExtracted({
                          asset_id: asset.id.toString(),
                          assetSymbol: asset.symbol,
                          claim_type: c.claim_type || 'PERCENTAGE_UP',
                          direction:
                            c.claim_type === 'PERCENTAGE_DOWN' ||
                            c.direction?.toLowerCase() === 'bearish'
                              ? 'Bearish'
                              : 'Bullish',
                          percentage: c.percentage ?? '',
                          until: c.until ?? '',
                          stakeRep: '10',
                        });
                        undismiss(dismissKey(c));
                      }}
                    >
                      Add
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => {
                        onEditExtracted(c);
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
              );
            })}
          </div>

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
                    <div key={i} className="flex items-start gap-2 opacity-75">
                      <div className="flex-1 min-w-0">
                        <ClaimRow
                          assetSymbol={c.asset}
                          direction={c.direction as 'Bullish' | 'Bearish' | 'bullish' | 'bearish'}
                          percentage={c.percentage ?? ''}
                          until={c.until ?? ''}
                          parity={c.parity}
                          claim_type={c.claim_type}
                          incomplete={isClaimIncomplete(c)}
                          reviewClaim={isClaimIncomplete(c) ? c : undefined}
                        />
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs shrink-0"
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
    </div>
  );
}
