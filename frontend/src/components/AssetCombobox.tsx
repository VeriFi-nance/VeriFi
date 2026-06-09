import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown, Loader2, Search } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { searchAssets, resolveAsset } from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import type { AssetItem, AssetSearchResult } from '@/lib/types';

/** Merge a resolved asset into the shared ['assets'] cache so feed cards and
 * other id→symbol lookups can render it immediately (no 10-min refetch wait). */
function cacheAsset(asset: AssetItem) {
  queryClient.setQueryData<AssetItem[]>(['assets'], (prev) =>
    prev?.some((a) => a.id === asset.id) ? prev : [...(prev ?? []), asset],
  );
}

interface AssetComboboxProps {
  /** Label shown on the trigger for the current selection (e.g. "BTC/USD"). */
  selectedLabel?: string;
  /** Fired with the fully-resolved Asset (remote candidates are persisted first). */
  onSelect: (asset: AssetItem) => void;
  placeholder?: string;
  className?: string;
  /** Compact trigger height to match dense forms. */
  size?: 'sm' | 'default';
}

function formatPair(r: { symbol: string; quote_currency?: string }): string {
  if (r.symbol.includes('/')) return r.symbol;
  return r.quote_currency ? `${r.symbol}/${r.quote_currency}` : r.symbol;
}

function resultKey(r: AssetSearchResult): string {
  return `${r.id ?? 'remote'}:${r.symbol}:${r.market_type ?? ''}`;
}

export function AssetCombobox({
  selectedLabel,
  onSelect,
  placeholder = 'Search assets…',
  className,
  size = 'default',
}: AssetComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [resolvingKey, setResolvingKey] = useState<string | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce keystrokes before hitting the backend.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  // Focus the search box when the popover opens.
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
    setError('');
  }, [open]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['asset-search', debounced],
    queryFn: () => searchAssets(debounced, 20),
    enabled: open,
    staleTime: 60_000,
  });

  async function pick(item: AssetSearchResult) {
    setError('');
    if (item.id != null) {
      cacheAsset(item as AssetItem);
      onSelect(item as AssetItem);
      setOpen(false);
      return;
    }
    // Remote candidate — materialize it into a real Asset row first.
    setResolvingKey(resultKey(item));
    try {
      const asset = await resolveAsset(item);
      cacheAsset(asset);
      onSelect(asset);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not add that asset.');
    } finally {
      setResolvingKey(null);
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'w-full justify-between font-normal',
            size === 'sm' && 'h-8 text-sm',
            !selectedLabel && 'text-muted-foreground',
            className,
          )}
        >
          <span className="truncate">{selectedLabel || placeholder}</span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[--radix-popover-trigger-width] p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="size-4 shrink-0 opacity-50" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search NASDAQ, BIST, crypto…"
            className="flex h-10 w-full bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          {isFetching && <Loader2 className="size-4 shrink-0 animate-spin opacity-50" />}
        </div>

        <div className="max-h-64 overflow-y-auto p-1">
          {error && (
            <p className="px-3 py-2 text-xs text-destructive">{error}</p>
          )}
          {!error && results.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">
              {debounced.length < 2
                ? 'Type to search assets.'
                : isFetching
                  ? 'Searching…'
                  : 'No assets found.'}
            </p>
          )}
          {results.map((r) => {
            const key = resultKey(r);
            const busy = resolvingKey === key;
            return (
              <button
                key={key}
                type="button"
                disabled={resolvingKey !== null}
                onClick={() => pick(r)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm',
                  'hover:bg-accent hover:text-accent-foreground disabled:opacity-60',
                )}
              >
                <span className="font-mono font-semibold">{formatPair(r)}</span>
                <span className="truncate text-muted-foreground">{r.name}</span>
                {busy && <Loader2 className="ml-auto size-4 shrink-0 animate-spin" />}
                {!busy && selectedLabel === formatPair(r) && (
                  <Check className="ml-auto size-4 shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
