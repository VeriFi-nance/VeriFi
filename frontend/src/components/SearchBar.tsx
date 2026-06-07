import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Search, Loader2, User, Hash, FileText, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useDebounce } from '@/hooks/useDebounce';
import { searchAPI } from '@/lib/api';
import { UserAvatar } from '@/components/UserAvatar';

type SearchType = 'posts' | 'people' | 'channels';

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

    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      try {
        const data = await searchAPI(debouncedQuery, type);
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
    <div className="relative flex-1 max-w-lg" ref={wrapperRef}>
      <div className="relative flex items-center group">
        <Search className="absolute left-3 size-4 text-muted-foreground pointer-events-none" />
        <Input
          placeholder="Search..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen && e.target.value.trim() && type !== 'posts') setIsOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && type === 'posts' && query.trim()) {
              navigate(`/feed?q=${encodeURIComponent(query.trim())}`);
              setIsOpen(false);
            }
          }}
          className="pl-9 pr-[130px] w-full"
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
            className="absolute right-[110px] top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 transition-colors z-10"
            aria-label="Clear search"
          >
            <X className="size-4" />
          </button>
        )}

        {/* Type Selector inside the search bar */}
        <div className="absolute right-1 top-1/2 -translate-y-1/2">
          <Select value={type} onValueChange={(value) => {
            setType(value as SearchType);
            if (query.trim() && value !== 'posts') setIsOpen(true);
          }}>
            <SelectTrigger className="h-8 border-none bg-transparent hover:bg-muted focus:ring-0 focus:ring-offset-0 w-[100px] text-xs shadow-none">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="posts">Posts</SelectItem>
              <SelectItem value="people">People</SelectItem>
              <SelectItem value="channels">Channels</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isOpen && (query.trim().length > 0) && (
        <div className="absolute top-full mt-2 w-full bg-background border border-border rounded-md shadow-lg z-50 max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="p-4 flex justify-center text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : results.length > 0 ? (
            <ul className="py-2">
              {results.map((result, idx) => (
                <li
                  key={result.id || result.address || idx}
                  className="px-4 py-2 hover:bg-muted/50 cursor-pointer flex items-center gap-3 transition-colors"
                  onClick={() => handleResultClick(result)}
                >
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
