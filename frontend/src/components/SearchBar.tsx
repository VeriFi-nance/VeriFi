import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Search, Loader2, User, Hash, FileText, X, Check, LineChart, SlidersHorizontal } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { useDebounce } from '@/hooks/useDebounce';
import { cn } from '@/lib/utils';
import { searchAPI, searchAssets, resolveAsset } from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import { useAssets } from '@/hooks/useAssets';
import { UserAvatar } from '@/components/UserAvatar';
import type { AssetItem, AssetSearchResult } from '@/lib/types';

type SearchType = 'posts' | 'people' | 'channels' | 'assets';

/** Merge a resolved asset into the shared ['assets'] cache for instant lookups. */
function cacheAsset(asset: AssetItem) {
  queryClient.setQueryData<AssetItem[]>(['assets'], (prev) =>
    prev?.some((a) => a.id === asset.id) ? prev : [...(prev ?? []), asset],
  );
}

function pairLabel(a: { symbol: string; quote_currency?: string }): string {
  if (a.symbol.includes('/')) return a.symbol;
  return a.quote_currency ? `${a.symbol}/${a.quote_currency}` : a.symbol;
}

interface SearchResult {
  id?: number | string;
  address?: string;
  username?: string;
  avatar_url?: string;
  content?: string;
  name?: string;
  [key: string]: any;
}

export function SearchBar() {
  const cachedAssets = useAssets();
  const [query, setQuery] = useState('');
  const [type, setType] = useState<SearchType>('posts');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  
  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (type === 'posts') {
      setIsOpen(false);
      // Only auto-navigate on debounce if we are already on the feed page
      if (location.pathname === '/feed' || location.pathname === '/') {
        if (debouncedQuery.trim()) {
          navigate(`/feed?q=${encodeURIComponent(debouncedQuery.trim())}`, { replace: true });
        } else {
          const params = new URLSearchParams(window.location.search);
          if (params.has('q')) {
            params.delete('q');
            navigate(`${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`, { replace: true });
          }
        }
      }
      return;
    }

    // Assets mode fetches even with an empty query — that returns the most-used
    // assets so the common picks sit at the top before the user types.
    if (type !== 'assets' && !debouncedQuery.trim()) {
      setResults([]);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      try {
        const data =
          type === 'assets'
            ? await searchAssets(debouncedQuery, 12)
            : await searchAPI(debouncedQuery, type);
        setResults(data || []);
        setIsOpen(true);
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [debouncedQuery, type, navigate, location.pathname]);

  // Asset ids currently applied to the feed filter (from the URL), so the
  // dropdown can show which results are already active.
  function currentAssetIds(): number[] {
    const raw = new URLSearchParams(location.search).get('assets');
    if (!raw) return [];
    return raw.split(',').map(Number).filter((n) => Number.isFinite(n) && n > 0);
  }

  async function toggleAssetFilter(item: AssetSearchResult) {
    let id = item.id;
    if (id == null) {
      try {
        const asset = await resolveAsset(item);
        cacheAsset(asset);
        id = asset.id;
      } catch {
        return;
      }
    } else {
      cacheAsset(item as AssetItem);
    }
    const ids = currentAssetIds();
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
    const params = new URLSearchParams(location.search);
    if (next.length) params.set('assets', next.join(','));
    else params.delete('assets');
    navigate(`/feed${params.toString() ? `?${params.toString()}` : ''}`);
  }

  // Claim / position type toggles, also stored in the URL so the feed reads one
  // source of truth (no separate filter component).
  function toggleFeedFlag(key: 'claims' | 'positions') {
    const params = new URLSearchParams(location.search);
    if (params.get(key) === '1') params.delete(key);
    else params.set(key, '1');
    navigate(`/feed${params.toString() ? `?${params.toString()}` : ''}`);
  }

  const flagOn = (key: 'claims' | 'positions') =>
    new URLSearchParams(location.search).get(key) === '1';
  const activeFilterCount =
    currentAssetIds().length + (flagOn('claims') ? 1 : 0) + (flagOn('positions') ? 1 : 0);
  const isFeedRoute = location.pathname === '/feed' || location.pathname === '/';

  const searchTypeSelect = (
    <Select
      value={type}
      onValueChange={(value) => {
        setType(value as SearchType);
        if (value === 'assets' || (query.trim() && value !== 'posts')) setIsOpen(true);
      }}
    >
      <SelectTrigger className="w-full md:w-[7.5rem]">
        <SelectValue placeholder="Type" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="posts">Posts</SelectItem>
        <SelectItem value="people">People</SelectItem>
        <SelectItem value="channels">Channels</SelectItem>
        <SelectItem value="assets">Assets</SelectItem>
      </SelectContent>
    </Select>
  );

  function removeAssetFilter(id: number) {
    const next = currentAssetIds().filter((x) => x !== id);
    const params = new URLSearchParams(location.search);
    if (next.length) params.set('assets', next.join(','));
    else params.delete('assets');
    navigate(`/feed${params.toString() ? `?${params.toString()}` : ''}`);
  }

  function assetLabel(id: number): string {
    const a = cachedAssets.find((x) => x.id === id);
    if (!a) return `#${id}`;
    return a.symbol.includes('/') ? a.symbol : a.quote_currency ? `${a.symbol}/${a.quote_currency}` : a.symbol;
  }

  const handleResultClick = (result: SearchResult) => {
    setIsOpen(false);
    setQuery('');
    
    if (type === 'posts' && result.id) {
      navigate(`/post/${result.id}`);
    } else if (type === 'people' && result.address) {
      navigate(`/u/${result.username || result.address}`);
    } else if (type === 'channels' && result.id) {
      console.log('Channel selected:', result);
    }
  };

  return (
    <div className="relative flex-1 min-w-0 max-w-lg flex items-center gap-2" ref={wrapperRef}>
      <div className="relative flex min-w-0 items-center group flex-1">
        <Search className="absolute left-3 size-4 text-muted-foreground pointer-events-none" />
        <Input
          placeholder="Search..."
          value={query}
          onFocus={() => {
            if (type === 'assets') setIsOpen(true);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen && type !== 'posts') setIsOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && type === 'posts' && query.trim()) {
              navigate(`/feed?q=${encodeURIComponent(query.trim())}`);
              setIsOpen(false);
            }
          }}
          className="pl-9 pr-9 w-full"
        />
        
        {query && (
          <button
            onClick={() => {
              setQuery('');
              setIsOpen(false);
              if (type === 'posts') {
                const params = new URLSearchParams(window.location.search);
                if (params.has('q')) {
                  params.delete('q');
                  navigate(`${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`, { replace: true });
                }
              }
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 transition-colors z-10"
            aria-label="Clear search"
          >
            <X className="size-4" />
          </button>
        )}
      </div>

      <div className="hidden md:block shrink-0">{searchTypeSelect}</div>

      {/* Mobile: search type + optional feed filters. Desktop feed: feed filters only. */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className={cn('relative shrink-0', !isFeedRoute && 'md:hidden')}
            aria-label={isFeedRoute ? 'Filter feed' : 'Search options'}
          >
            <SlidersHorizontal className="size-4" />
            {isFeedRoute && activeFilterCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 flex items-center justify-center size-4 rounded-full bg-primary text-[10px] font-bold text-primary-foreground leading-none">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-60 space-y-3">
          <div className="space-y-2 md:hidden">
            <Label className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Search type
            </Label>
            {searchTypeSelect}
          </div>

          {isFeedRoute && currentAssetIds().length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Assets
              </p>
              <div className="flex flex-wrap gap-1.5">
                {currentAssetIds().map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 rounded-md border border-primary bg-primary px-2 py-0.5 text-[11px] font-mono font-semibold text-primary-foreground"
                  >
                    {assetLabel(id)}
                    <button
                      type="button"
                      onClick={() => removeAssetFilter(id)}
                      aria-label={`Remove ${assetLabel(id)} filter`}
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {isFeedRoute && (
            <>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Posts with
              </p>
              <div className="flex items-center justify-between">
                <Label htmlFor="sb-has-claims" className="text-sm cursor-pointer">Claim</Label>
                <Switch id="sb-has-claims" checked={flagOn('claims')} onCheckedChange={() => toggleFeedFlag('claims')} />
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="sb-has-positions" className="text-sm cursor-pointer">Position</Label>
                <Switch id="sb-has-positions" checked={flagOn('positions')} onCheckedChange={() => toggleFeedFlag('positions')} />
              </div>
            </>
          )}
        </PopoverContent>
      </Popover>

      {isOpen && (query.trim().length > 0 || type === 'assets') && (
        <div className="absolute top-full mt-2 w-full bg-background border border-border rounded-md shadow-lg z-50 max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="p-4 flex justify-center text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : results.length > 0 ? (
            <ul className="py-2">
              {results.map((result, idx) => (
                <li
                  key={result.id || result.address || result.symbol || idx}
                  className="px-4 py-2 hover:bg-muted/50 cursor-pointer flex items-center gap-3 transition-colors"
                  onClick={() =>
                    type === 'assets'
                      ? toggleAssetFilter(result as AssetSearchResult)
                      : handleResultClick(result)
                  }
                >
                  {type === 'assets' && (
                    <>
                      <LineChart className="size-4 text-muted-foreground shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-mono font-semibold truncate">
                          {pairLabel(result as AssetSearchResult)}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">{result.name}</p>
                      </div>
                      {result.id != null && currentAssetIds().includes(result.id as number) && (
                        <Check className="size-4 shrink-0 text-primary" />
                      )}
                    </>
                  )}
                  {type === 'posts' && (
                    <>
                      <FileText className="size-4 text-muted-foreground shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm truncate">
                          {result.content || "No content"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          @{result.author_username || 'unknown'}
                        </p>
                      </div>
                    </>
                  )}
                  {type === 'people' && (
                    <>
                      {result.address ? (
                        <UserAvatar address={result.address} src={result.avatar_url} size="sm" />
                      ) : (
                        <User className="size-4 text-muted-foreground shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">@{result.username}</p>
                        <p className="text-xs text-muted-foreground font-mono truncate">{result.address}</p>
                      </div>
                    </>
                  )}
                  {type === 'channels' && (
                    <>
                      <Hash className="size-4 text-muted-foreground shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{result.name}</p>
                        {result.description && (
                          <p className="text-xs text-muted-foreground truncate">{result.description}</p>
                        )}
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No results found.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
