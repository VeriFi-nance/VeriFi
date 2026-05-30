import { useEffect, useRef, useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { ClaimRow } from './ClaimRow';
import { extractClaims } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { AssetItem, ExtractedClaimContract, ReviewClaim } from '@/lib/types';
import type { AttachedClaim } from './types';

const DEBOUNCE_MS = 700;
const MAX_CHARS = 500;

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

function claimKey(parts: {
  asset: string;
  direction: string;
  percentage?: string;
  until?: string;
}): string {
  return `${parts.asset || 'null'}-${parts.direction.toLowerCase()}-${parts.percentage || 'null'}-${parts.until || 'null'}`;
}

interface PostComposerProps {
  content: string;
  onContentChange: (next: string) => void;
  attached: AttachedClaim[];
  assets: AssetItem[];
  onAddExtracted: (claim: AttachedClaim) => void;
  onEditExtracted: (claim: ReviewClaim) => void;
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
}: PostComposerProps) {
  const [extracted, setExtracted] = useState<ReviewClaim[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [ignored, setIgnored] = useState<Set<string>>(new Set());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!content.trim()) {
      setExtracted([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setExtracting(true);
      try {
        const res = await extractClaims(content);
        setExtracted(res.claims.map(toReviewClaim));
      } catch {
        setExtracted([]);
      } finally {
        setExtracting(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [content]);

  const remaining = MAX_CHARS - content.length;
  const overLimit = content.length > MAX_CHARS;

  const visible = extracted.filter((c) => {
    const key = claimKey({ asset: c.asset, direction: c.direction, percentage: c.percentage, until: c.until });
    if (ignored.has(key)) return false;
    return !attached.some((ac) =>
      claimKey({
        asset: ac.assetSymbol,
        direction: ac.direction,
        percentage: ac.percentage,
        until: ac.until,
      }) === key,
    );
  });

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Textarea
          placeholder="What's your financial take?"
          value={content}
          onChange={(e) => onContentChange(e.target.value)}
          rows={4}
          className="resize-none text-sm"
          maxLength={MAX_CHARS + 50}
          autoFocus
        />
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
      </div>

      {(extracting || visible.length > 0) && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            {extracting ? 'Analysing…' : 'Detected claims'}
          </p>
          <div className="space-y-1.5">
            {visible.map((c, i) => {
              const missing = !c.asset || !c.percentage || !c.until;
              const key = claimKey({
                asset: c.asset,
                direction: c.direction,
                percentage: c.percentage,
                until: c.until,
              });
              const dismiss = () => setIgnored((s) => new Set(s).add(key));
              return (
                <div key={i} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <ClaimRow
                      assetSymbol={c.asset}
                      direction={c.direction as 'Bullish' | 'Bearish' | 'bullish' | 'bearish'}
                      percentage={c.percentage ?? ''}
                      until={c.until ?? ''}
                    />
                  </div>
                  <div className="flex items-center">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      disabled={missing}
                      onClick={() => {
                        const asset = assets.find((a) => a.symbol === c.asset);
                        if (!asset) return;
                        onAddExtracted({
                          asset_id: asset.id.toString(),
                          assetSymbol: asset.symbol,
                          direction: c.direction === 'bullish' ? 'Bullish' : 'Bearish',
                          percentage: c.percentage ?? '',
                          until: c.until ?? '',
                          stakeRep: '10',
                        });
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
                        dismiss();
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      onClick={dismiss}
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
    </div>
  );
}

export { MAX_CHARS };
