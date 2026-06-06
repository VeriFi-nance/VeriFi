import { useState } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import type { AssetItem } from '@/lib/types';

export interface FeedFilter {
  assetIds: number[];
  hasClaims: boolean;
  hasPositions: boolean;
}

const DEFAULT_FILTER: FeedFilter = {
  assetIds: [],
  hasClaims: false,
  hasPositions: false,
};

function isFilterActive(f: FeedFilter): boolean {
  return f.assetIds.length > 0 || f.hasClaims || f.hasPositions;
}

interface FeedFilterPopoverProps {
  assets: AssetItem[];
  filter: FeedFilter;
  onApply: (f: FeedFilter) => void;
}

export function FeedFilterPopover({ assets, filter, onApply }: FeedFilterPopoverProps) {
  const [open, setOpen] = useState(false);
  // Local draft — not committed until Apply
  const [draft, setDraft] = useState<FeedFilter>({ ...filter });

  const active = isFilterActive(filter);
  const activeCount =
    filter.assetIds.length + (filter.hasClaims ? 1 : 0) + (filter.hasPositions ? 1 : 0);

  function handleOpen(v: boolean) {
    if (v) setDraft({ ...filter }); // reset draft to current applied filter
    setOpen(v);
  }

  function toggleAsset(id: number) {
    setDraft((prev) => ({
      ...prev,
      assetIds: prev.assetIds.includes(id)
        ? prev.assetIds.filter((a) => a !== id)
        : [...prev.assetIds, id],
    }));
  }

  function handleApply() {
    onApply(draft);
    setOpen(false);
  }

  function handleReset() {
    const cleared = { ...DEFAULT_FILTER };
    setDraft(cleared);
    onApply(cleared);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={active ? 'default' : 'outline'}
          size="sm"
          id="feed-filter-btn"
          className={cn(
            'relative gap-2 shrink-0 transition-all',
            active && 'pr-6',
          )}
          aria-label="Filter feed"
        >
          <SlidersHorizontal className="size-3.5" />
          <span className="hidden sm:inline">Filter</span>
          {active && (
            <span className="absolute -top-1.5 -right-1.5 flex items-center justify-center size-4 rounded-full bg-primary text-[10px] font-bold text-primary-foreground leading-none">
              {activeCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        className="w-72 p-4 space-y-4"
        id="feed-filter-popover"
      >
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Filter Feed</p>
          {isFilterActive(draft) && (
            <button
              type="button"
              onClick={() => setDraft({ ...DEFAULT_FILTER })}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <X className="size-3" /> Clear all
            </button>
          )}
        </div>

        {/* ── Asset selection ────────────────────────────────── */}
        {assets.length > 0 && (
          <div className="space-y-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Asset
            </p>
            <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto">
              {assets.map((asset) => {
                const selected = draft.assetIds.includes(asset.id);
                return (
                  <button
                    key={asset.id}
                    type="button"
                    onClick={() => toggleAsset(asset.id)}
                    className={cn(
                      'text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md border transition-all',
                      selected
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-transparent text-muted-foreground border-border hover:border-primary/50 hover:text-foreground',
                    )}
                    aria-pressed={selected}
                  >
                    {asset.symbol}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Type toggles (Object selection) ────────────────── */}
        <div className="space-y-3">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Posts with
          </p>
          <div className="flex items-center justify-between">
            <Label htmlFor="filter-has-claims" className="text-sm cursor-pointer">
              Claim
            </Label>
            <Switch
              id="filter-has-claims"
              checked={draft.hasClaims}
              onCheckedChange={(v) => setDraft((prev) => ({ ...prev, hasClaims: v }))}
            />
          </div>
          <div className="flex items-center justify-between">
            <Label htmlFor="filter-has-positions" className="text-sm cursor-pointer">
              Position
            </Label>
            <Switch
              id="filter-has-positions"
              checked={draft.hasPositions}
              onCheckedChange={(v) => setDraft((prev) => ({ ...prev, hasPositions: v }))}
            />
          </div>
        </div>

        {/* ── Actions ────────────────────────────────────────── */}
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            className="flex-1"
            onClick={handleApply}
            id="feed-filter-apply"
          >
            Apply
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleReset}
            id="feed-filter-reset"
          >
            Reset
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
