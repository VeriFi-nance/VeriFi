import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronLeft, Heart, MessageCircle } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import { ClaimDetailView } from '@/components/feed/ClaimDetailView';
import { PostActions } from '@/components/feed/PostActions';
import { SkeletonPostCard } from '@/components/Skeleton';
import { PageContent } from '@/components/PageContent';
import { createPostComment, getPost, getAssets, getPostComments, likePostComment, unlikePostComment } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { truncateAddress } from '@/lib/wallet';
import type { PostItem, PostCommentItem, AssetItem } from '@/lib/types';

function replaceComment(comments: PostCommentItem[], updated: PostCommentItem): PostCommentItem[] {
  return comments.map((comment) => {
    if (comment.id === updated.id) {
      return { ...updated, replies: updated.replies?.length ? updated.replies : comment.replies };
    }
    return { ...comment, replies: replaceComment(comment.replies, updated) };
  });
}

function appendReply(comments: PostCommentItem[], parentId: number, reply: PostCommentItem): PostCommentItem[] {
  return comments.map((comment) => {
    if (comment.id === parentId) {
      return { ...comment, replies: [...comment.replies, reply] };
    }
    return { ...comment, replies: appendReply(comment.replies, parentId, reply) };
  });
}

function CommentThreadItem({
  comment,
  postId,
  depth = 0,
  authenticated,
  openLogin,
  onCommentChange,
  onReplyCreated,
}: {
  comment: PostCommentItem;
  postId: number;
  depth?: number;
  authenticated: boolean;
  openLogin: (returnTo?: string) => void;
  onCommentChange: (comment: PostCommentItem) => void;
  onReplyCreated: (parentId: number, reply: PostCommentItem) => void;
}) {
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyContent, setReplyContent] = useState('');
  const [pendingLike, setPendingLike] = useState(false);
  const [submittingReply, setSubmittingReply] = useState(false);
  const [error, setError] = useState('');

  const toggleLike = async () => {
    if (!authenticated) {
      openLogin(`/post/${postId}`);
      return;
    }
    if (pendingLike) return;
    const nextLiked = !comment.liked_by_me;
    const optimistic = {
      ...comment,
      liked_by_me: nextLiked,
      like_count: Math.max(0, comment.like_count + (nextLiked ? 1 : -1)),
    };
    setPendingLike(true);
    setError('');
    onCommentChange(optimistic);
    try {
      const updated = nextLiked ? await likePostComment(comment.id) : await unlikePostComment(comment.id);
      onCommentChange(updated);
    } catch (e) {
      onCommentChange(comment);
      setError(e instanceof Error ? e.message : 'Unable to update comment like.');
    } finally {
      setPendingLike(false);
    }
  };

  const submitReply = async () => {
    if (!authenticated) {
      openLogin(`/post/${postId}`);
      return;
    }
    const content = replyContent.trim();
    if (!content) {
      setError('Reply cannot be empty.');
      return;
    }

    setSubmittingReply(true);
    setError('');
    try {
      const reply = await createPostComment(postId, content, comment.id);
      onReplyCreated(comment.id, reply);
      setReplyContent('');
      setReplyOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to post reply.');
    } finally {
      setSubmittingReply(false);
    }
  };

  return (
    <article className={depth > 0 ? 'border-l border-border pl-3 sm:pl-4' : ''}>
      <div className="flex gap-3">
        <UserAvatar address={comment.author_address} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              to={`/u/${comment.author_username || comment.author_address}`}
              className="text-xs font-mono font-medium hover:underline truncate"
            >
              {comment.author_username ? `@${comment.author_username}` : truncateAddress(comment.author_address)}
            </Link>
            <time dateTime={comment.created_at} className="text-xs text-muted-foreground num">
              {new Date(comment.created_at).toLocaleString()}
            </time>
          </div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{comment.content}</p>
          <div className="mt-1 flex items-center gap-1 text-muted-foreground">
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className={comment.liked_by_me ? 'text-red-500 hover:text-red-500' : ''}
              disabled={pendingLike}
              onClick={() => void toggleLike()}
              aria-pressed={comment.liked_by_me}
            >
              <Heart className={comment.liked_by_me ? 'size-3 fill-current' : 'size-3'} />
              <span className="num">{comment.like_count}</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => authenticated ? setReplyOpen((open) => !open) : openLogin(`/post/${postId}`)}
            >
              <MessageCircle className="size-3" />
              Comment
            </Button>
          </div>

          {replyOpen && (
            <div className="mt-2 space-y-2">
              <Textarea
                value={replyContent}
                onChange={(e) => setReplyContent(e.target.value)}
                maxLength={500}
                placeholder="Write a reply"
                className="min-h-16 resize-none text-sm"
              />
              <div className="flex items-center justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => setReplyOpen(false)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={submittingReply || replyContent.trim().length === 0}
                  onClick={() => void submitReply()}
                >
                  {submittingReply ? 'Posting...' : 'Reply'}
                </Button>
              </div>
            </div>
          )}

          {error && <p className="mt-1 text-xs text-destructive">{error}</p>}

          {comment.replies.length > 0 && (
            <div className="mt-3 space-y-3">
              {comment.replies.map((reply) => (
                <CommentThreadItem
                  key={reply.id}
                  comment={reply}
                  postId={postId}
                  depth={depth + 1}
                  authenticated={authenticated}
                  openLogin={openLogin}
                  onCommentChange={onCommentChange}
                  onReplyCreated={onReplyCreated}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

export default function PostDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const auth = useAuthState();
  const openLogin = useOpenLogin();
  const [post, setPost] = useState<PostItem | null>(null);
  const [comments, setComments] = useState<PostCommentItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentContent, setCommentContent] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [error, setError] = useState('');
  const [commentsError, setCommentsError] = useState('');

  useEffect(() => {
    if (!id) return;
    const postId = Number(id);
    Promise.all([getPost(postId), getAssets(), getPostComments(postId)])
      .then(([found, a, loadedComments]) => {
        setPost(found);
        setAssets(a);
        setComments(loadedComments);
        setCommentsError('');
      })
      .catch((e) => setError(e.message))
      .finally(() => {
        setLoading(false);
        setCommentsLoading(false);
      });
  }, [id]);

  const handleSubmitComment = async () => {
    if (!post) return;
    if (!auth.authenticated) {
      openLogin(`/post/${post.id}`);
      return;
    }

    const content = commentContent.trim();
    if (!content) {
      setCommentsError('Comment cannot be empty.');
      return;
    }

    setSubmittingComment(true);
    setCommentsError('');
    try {
      const comment = await createPostComment(post.id, content);
      setComments((prev) => [...prev, comment]);
      setCommentContent('');
      setPost((prev) => prev ? { ...prev, comment_count: prev.comment_count + 1 } : prev);
    } catch (e) {
      setCommentsError(e instanceof Error ? e.message : 'Failed to post comment.');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleCommentChange = (updatedComment: PostCommentItem) => {
    setComments((prev) => replaceComment(prev, updatedComment));
  };

  const handleReplyCreated = (parentId: number, reply: PostCommentItem) => {
    setComments((prev) => appendReply(prev, parentId, reply));
    setPost((prev) => prev ? { ...prev, comment_count: prev.comment_count + 1 } : prev);
  };

  if (loading) {
    return (
      <PageContent>
        <SkeletonPostCard />
      </PageContent>
    );
  }

  if (error || !post) {
    return (
      <PageContent className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Post not found'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" onClick={() => navigate('/feed')}>
          <ChevronLeft className="size-4 mr-1" />
          Back to feed
        </Button>
      </PageContent>
    );
  }



  return (
    <PageContent className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate('/feed')} className="-ml-2">
        <ChevronLeft className="size-4 mr-1" />
        Back
      </Button>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <UserAvatar address={post.author_address} size="md" />
            <Link
              to={`/u/${post.author_username || post.author_address}`}
              className="text-sm font-mono font-medium hover:underline truncate"
            >
              {post.author_username ? `@${post.author_username}` : truncateAddress(post.author_address)}
            </Link>
            <span className="ml-auto text-xs text-muted-foreground num">
              {new Date(post.created_at).toLocaleString()}
            </span>
          </div>

          <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>

          <PostActions post={post} onPostChange={setPost} className="border-t border-border pt-2" />
        </CardContent>
      </Card>

      <section className="mt-4 space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Comments</h2>
          <span className="text-xs text-muted-foreground num">{post.comment_count}</span>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          {auth.authenticated ? (
            <div className="space-y-2">
              <Textarea
                value={commentContent}
                onChange={(e) => setCommentContent(e.target.value)}
                maxLength={500}
                placeholder="Add a comment"
                className="min-h-20 resize-none"
              />
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-muted-foreground num">{commentContent.length}/500</span>
                <Button
                  size="sm"
                  disabled={submittingComment || commentContent.trim().length === 0}
                  onClick={() => void handleSubmitComment()}
                >
                  {submittingComment ? 'Posting…' : 'Comment'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">Log in to join the discussion.</p>
              <Button size="sm" variant="outline" onClick={() => openLogin(`/post/${post.id}`)}>
                Log in
              </Button>
            </div>
          )}

          {commentsError && (
            <Alert variant="destructive">
              <AlertDescription>{commentsError}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-3 border-t border-border pt-3">
            {commentsLoading ? (
              <p className="text-sm text-muted-foreground">Loading comments…</p>
            ) : comments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No comments yet.</p>
            ) : (
              comments.map((comment) => (
                <CommentThreadItem
                  key={comment.id}
                  comment={comment}
                  postId={post.id}
                  authenticated={auth.authenticated}
                  openLogin={openLogin}
                  onCommentChange={handleCommentChange}
                  onReplyCreated={handleReplyCreated}
                />
              ))
            )}
          </div>
        </div>
      </section>

      {post.hard_claims.length > 0 && (
        <section className="mt-4 space-y-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Claims
          </h2>
          {post.hard_claims.map((hc) => (
            <div key={hc.id} className="rounded-lg border border-border bg-card p-4 sm:p-5">
              <ClaimDetailView claim={hc} assets={assets} />
            </div>
          ))}
        </section>
      )}
    </PageContent>
  );
}
