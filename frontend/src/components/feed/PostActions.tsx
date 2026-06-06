import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
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

      </div>

      {error && <p className="px-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}
