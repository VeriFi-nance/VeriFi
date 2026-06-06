import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, Heart, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { likePost, savePostProof, unlikePost, unsavePostProof } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { cn } from '@/lib/utils';
import type { PostItem } from '@/lib/types';

interface PostActionsProps {
  post: PostItem;
  onPostChange?: (post: PostItem) => void;
  className?: string;
}

function optimisticPost(post: PostItem, action: 'like' | 'save', enabled: boolean): PostItem {
  if (action === 'like') {
    const delta = enabled === post.liked_by_me ? 0 : enabled ? 1 : -1;
    return {
      ...post,
      liked_by_me: enabled,
      like_count: Math.max(0, post.like_count + delta),
    };
  }

  const delta = enabled === post.saved_proof_by_me ? 0 : enabled ? 1 : -1;
  return {
    ...post,
    saved_proof_by_me: enabled,
    saved_proof_count: Math.max(0, post.saved_proof_count + delta),
  };
}

export function PostActions({ post, onPostChange, className }: PostActionsProps) {
  const auth = useAuthState();
  const openLogin = useOpenLogin();
  const [pending, setPending] = useState<'like' | 'save' | null>(null);
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
    setPending('like');
    onPostChange?.(optimisticPost(post, 'like', nextLiked));
    try {
      const updated = nextLiked ? await likePost(post.id) : await unlikePost(post.id);
      onPostChange?.(updated);
    } catch (e) {
      onPostChange?.(previous);
      setError(e instanceof Error ? e.message : 'Unable to update like.');
    } finally {
      setPending(null);
    }
  };

  const toggleSave = async () => {
    if (!requireAuth() || pending) return;
    const nextSaved = !post.saved_proof_by_me;
    const previous = post;
    setError('');
    setPending('save');
    onPostChange?.(optimisticPost(post, 'save', nextSaved));
    try {
      const updated = nextSaved ? await savePostProof(post.id) : await unsavePostProof(post.id);
      onPostChange?.(updated);
    } catch (e) {
      onPostChange?.(previous);
      setError(e instanceof Error ? e.message : 'Unable to update saved proof.');
    } finally {
      setPending(null);
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
          disabled={pending !== null}
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

        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn('h-8 px-2.5', post.saved_proof_by_me && 'text-blue-500 hover:text-blue-500')}
          disabled={pending !== null}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            void toggleSave();
          }}
          aria-pressed={post.saved_proof_by_me}
          aria-label={post.saved_proof_by_me ? 'Unsave proof' : 'Save proof'}
        >
          <Bookmark className={cn('size-4', post.saved_proof_by_me && 'fill-current')} />
          <span className="hidden sm:inline">Proof</span>
          <span className="num">{post.saved_proof_count}</span>
        </Button>
      </div>

      {error && <p className="px-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}
