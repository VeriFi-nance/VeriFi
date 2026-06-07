import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, MessageCircle, Share2, Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { likePost, unlikePost } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { cn } from '@/lib/utils';
import type { PostItem } from '@/lib/types';

interface PostActionsProps {
  post: PostItem;
  onPostChange?: (post: PostItem) => void;
  className?: string;
}

function optimisticLike(post: PostItem, enabled: boolean): PostItem {
  const delta = enabled === post.liked_by_me ? 0 : enabled ? 1 : -1;
  return {
    ...post,
    liked_by_me: enabled,
    like_count: Math.max(0, post.like_count + delta),
  };
}

export function PostActions({ post, onPostChange, className }: PostActionsProps) {
  const auth = useAuthState();
  const openLogin = useOpenLogin();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const requireAuth = () => {
    if (auth.authenticated) return true;
    openLogin(`/post/${post.id}`);
    return false;
  };

  const toggleLike = async () => {
    if (!requireAuth() || pending) return;
    const nextLiked = !post.liked_by_me;
    const previous = post;
    setError('');
    setPending(true);
    onPostChange?.(optimisticLike(post, nextLiked));
    try {
      const updated = nextLiked ? await likePost(post.id) : await unlikePost(post.id);
      onPostChange?.(updated);
    } catch (e) {
      onPostChange?.(previous);
      setError(e instanceof Error ? e.message : 'Unable to update like.');
    } finally {
      setPending(false);
    }
  };

  const getShareTextAndUrl = () => {
    const baseUrl = window.location.origin.includes('localhost') ? 'https://develop.veri.finance' : window.location.origin;
    const url = `${baseUrl}/post/${post.id}`;
    
    let claimText = '';
    if (post.hard_claims && post.hard_claims.length > 0) {
      const claim = post.hard_claims[0];
      const asset = claim.asset_obj?.symbol || 'Asset';
      const direction = claim.direction.toLowerCase();
      const verb = direction === 'bullish' ? 'rises' : 'falls';
      const pct = claim.percentage || '';
      const until = new Date(claim.until).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
      claimText = `🎯 Claim: ${asset} ${verb} ${pct}% by ${until}\n\n`;
    } else if (post.positions && post.positions.length > 0) {
      const pos = post.positions[0];
      const asset = pos.asset_obj?.symbol || 'Asset';
      const direction = pos.direction.toUpperCase();
      claimText = `📈 Position: ${direction} on ${asset}\n\n`;
    }

    let text = claimText;
    if (post.content) {
      // Truncate post content if too long
      const truncated = post.content.length > 150 ? post.content.slice(0, 147) + '...' : post.content;
      text += `"${truncated}"\n\n`;
    }
    
    return { text, url };
  };

  const handleCopyText = () => {
    const { text, url } = getShareTextAndUrl();
    const copyText = text + `Read more on VeriFi:\n${url}`;
    
    try {
      void navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const input = document.createElement('textarea');
      input.value = copyText;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleShareTwitter = () => {
    const { text, url } = getShareTextAndUrl();
    const shareText = text + `Read more on VeriFi:`;
    
    window.open(
      `https://x.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer'
    );
  };

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center gap-1 text-muted-foreground">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn('h-8 px-2.5', post.liked_by_me && 'text-red-500 hover:text-red-500')}
          disabled={pending}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            void toggleLike();
          }}
          aria-pressed={post.liked_by_me}
          aria-label={post.liked_by_me ? 'Unlike post' : 'Like post'}
        >
          <Heart className={cn('size-4', post.liked_by_me && 'fill-current')} />
          <span className="num">{post.like_count}</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          asChild
          className="h-8 px-2.5"
          aria-label="View comments"
        >
          <Link
            to={`/post/${post.id}`}
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <MessageCircle className="size-4" />
            <span className="num">{post.comment_count}</span>
          </Link>
        </Button>

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2.5"
              onClick={(e) => {
                e.stopPropagation();
              }}
              aria-label="Share post"
            >
              <Share2 className="size-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-40 p-2 flex flex-col gap-1" align="end" onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="sm" className="justify-start px-2" onClick={(e) => { e.preventDefault(); handleCopyText(); }}>
              {copied ? <Check className="size-4 mr-2 text-success" /> : <Copy className="size-4 mr-2" />}
              {copied ? "Copied!" : "Copy Link"}
            </Button>
            <Button variant="ghost" size="sm" className="justify-start px-2" onClick={(e) => { e.preventDefault(); handleShareTwitter(); }}>
              <Share2 className="size-4 mr-2" />
              Share on X
            </Button>
          </PopoverContent>
        </Popover>

      </div>

      {error && <p className="px-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}
