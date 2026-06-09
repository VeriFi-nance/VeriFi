import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Plus, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { searchAssets, resolveAsset } from '@/lib/api';
import { useAssets } from '@/hooks/useAssets';
import { queryClient } from '@/lib/queryClient';
import type { AssetItem, AssetSearchResult } from '@/lib/types';

interface AssetMultiSelectProps {
  /** Currently selected asset ids. */
  value: number[];
  onChange: (ids: number[]) => void;
}

function cacheAsset(asset: AssetItem) {
  queryClient.setQueryData<AssetItem[]>(['assets'], (prev) =>
    prev?.some((a) => a.id === asset.id) ? prev : [...(prev ?? []), asset],
  );
}

function pairLabel(a: { symbol: string; quote_currency?: string }): string {
  if (a.symbol.includes('/')) return a.symbol;
  return a.quote_currency ? `${a.symbol}/${a.quote_currency}` : a.symbol;
}

/**
 * Search-driven multi-select for assets. Replaces the old static pill list:
 * type to search the full catalog (local DB + live provider candidates),
 * picked assets become removable chips. Remote candidates are persisted on
 * pick so the feed filter has a real asset id.
 */
export function AssetMultiSelect({ value, onChange }: AssetMultiSelectProps) {
  const cached = useAssets();
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [resolvingKey, setResolvingKey] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['asset-search', debounced],
    queryFn: () => searchAssets(debounced, 12),
    enabled: debounced.length >= 1,
    staleTime: 60_000,
  });

  function labelFor(id: number): string {
    const a = cached.find((x) => x.id === id);
    return a ? pairLabel(a) : `#${id}`;
  }

  function remove(id: number) {
    onChange(value.filter((v) => v !== id));
  }

  async function pick(item: AssetSearchResult) {
    let id = item.id;
    if (id == null) {
      setResolvingKey(`${item.symbol}:${item.market_type}`);
      try {
        const asset = await resolveAsset(item);
        cacheAsset(asset);
        id = asset.id;
      } catch {
        setResolvingKey(null);
        return;
      }
      setResolvingKey(null);
    } else {
      cacheAsset(item as AssetItem);
    }
    if (!value.includes(id)) onChange([...value, id]);
    setQuery('');
    inputRef.current?.focus();
  }

  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-md border border-primary bg-primary px-2 py-0.5 text-[11px] font-mono font-semibold text-primary-foreground"
            >
              {labelFor(id)}
              <button type="button" onClick={() => remove(id)} aria-label={`Remove ${labelFor(id)}`}>
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 rounded-md border px-2">
        <Search className="size-3.5 shrink-0 opacity-50" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search assets to filter…"
          className="h-8 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        {isFetching && <Loader2 className="size-3.5 shrink-0 animate-spin opacity-50" />}
      </div>

      {debounced.length >= 1 && (
        <div className="max-h-40 overflow-y-auto rounded-md border p-1">
          {results.length === 0 && (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              {isFetching ? 'Searching…' : 'No assets found.'}
            </p>
          )}
          {results.map((r) => {
            const key = `${r.id ?? 'remote'}:${r.symbol}:${r.market_type ?? ''}`;
            const already = r.id != null && value.includes(r.id);
            const busy = resolvingKey === `${r.symbol}:${r.market_type}`;
            return (
              <button
                key={key}
                type="button"
                disabled={already || resolvingKey !== null}
                onClick={() => pick(r)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm',
                  'hover:bg-accent hover:text-accent-foreground disabled:opacity-50',
                )}
              >
                <span className="font-mono font-semibold">{pairLabel(r)}</span>
                <span className="truncate text-xs text-muted-foreground">{r.name}</span>
                {busy && <Loader2 className="ml-auto size-3.5 shrink-0 animate-spin" />}
                {already && <Plus className="ml-auto size-3.5 shrink-0 rotate-45 opacity-50" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
