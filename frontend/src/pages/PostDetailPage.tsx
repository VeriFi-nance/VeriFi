import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronLeft, Heart, MessageCircle, ImagePlus, X } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import { SmartTimestamp } from '@/components/SmartTimestamp';
import { CLAIM_DETAIL_DIALOG_CLASS, ClaimDetailView } from '@/components/feed/ClaimDetailView';
import { PostActions } from '@/components/feed/PostActions';
import { SkeletonPostCard } from '@/components/Skeleton';
import { PageContent } from '@/components/PageContent';
import { HardClaimCard } from '@/components/HardClaimCard';
import { PositionAttachmentCard } from '@/components/PositionAttachmentCard';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { createPostComment, getPost, getPostComments, likePostComment, unlikePostComment } from '@/lib/api';
import { fetchAssets } from '@/hooks/useAssets';
import { updatePostAcrossCachedFeeds } from '@/hooks/useFeed';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { safeImageSrc, imageFileFromClipboard } from '@/lib/utils';
import { truncateAddress } from '@/lib/wallet';
import type { PostItem, PostCommentItem, AssetItem, HardClaimItem } from '@/lib/types';

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
  const [replyImage, setReplyImage] = useState<File | null>(null);
  const [replyImagePreview, setReplyImagePreview] = useState<string | null>(null);
  const replyFileRef = useRef<HTMLInputElement>(null);
  const [pendingLike, setPendingLike] = useState(false);
  const [submittingReply, setSubmittingReply] = useState(false);
  const [error, setError] = useState('');

  const pickReplyImage = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) { setError('Please choose an image file.'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('Image must be 10 MB or smaller.'); return; }
    setError('');
    setReplyImage(file);
    setReplyImagePreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(file); });
  };

  const clearReplyImage = () => {
    setReplyImage(null);
    setReplyImagePreview((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    if (replyFileRef.current) replyFileRef.current.value = '';
  };

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
    if (!content && !replyImage) {
      setError('Reply cannot be empty.');
      return;
    }

    setSubmittingReply(true);
    setError('');
    try {
      const reply = await createPostComment(postId, content, comment.id, replyImage);
      onReplyCreated(comment.id, reply);
      setReplyContent('');
      clearReplyImage();
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
        <Link
          to={`/u/${comment.author_username || comment.author_address}`}
          className="h-fit rounded-full transition-opacity hover:opacity-80"
          aria-label={`View profile for ${comment.author_username ? `@${comment.author_username}` : truncateAddress(comment.author_address)}`}
        >
          <UserAvatar address={comment.author_address} src={comment.author_avatar_url} size="sm" />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              to={`/u/${comment.author_username || comment.author_address}`}
              className="text-xs font-mono font-medium hover:underline truncate"
            >
              {comment.author_username ? `@${comment.author_username}` : truncateAddress(comment.author_address)}
            </Link>
            <SmartTimestamp value={comment.created_at} className="text-xs text-muted-foreground" />
          </div>
          {comment.content && (
            <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{comment.content}</p>
          )}
          {comment.image_url && (
            <img
              src={safeImageSrc(comment.image_url)}
              alt=""
              loading="lazy"
              className="mt-2 max-h-80 rounded-lg border border-border object-cover"
            />
          )}
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
                onPaste={(e) => {
                  const file = imageFileFromClipboard(e.clipboardData);
                  if (file) { e.preventDefault(); pickReplyImage(file); }
                }}
                maxLength={500}
                placeholder="Write a reply"
                className="min-h-16 resize-none text-sm"
              />
              <input
                ref={replyFileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pickReplyImage(e.target.files?.[0] ?? null)}
              />
              {replyImagePreview && (
                <div className="relative w-fit">
                  <img src={replyImagePreview} alt="" className="max-h-40 rounded-lg border border-border object-cover" />
                  <button
                    type="button"
                    onClick={clearReplyImage}
                    aria-label="Remove image"
                    className="absolute top-1 right-1 size-6 flex items-center justify-center rounded-full bg-background/80 hover:bg-background"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              )}
              <div className="flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="mr-auto text-primary hover:bg-primary/10 hover:text-primary"
                  aria-label="Add image"
                  onClick={() => replyFileRef.current?.click()}
                >
                  <ImagePlus className="size-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setReplyOpen(false)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={submittingReply || (replyContent.trim().length === 0 && !replyImage)}
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
  const queryClient = useQueryClient();
  const auth = useAuthState();
  const openLogin = useOpenLogin();
  const [post, setPost] = useState<PostItem | null>(null);
  const [comments, setComments] = useState<PostCommentItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentContent, setCommentContent] = useState('');
  const [commentImage, setCommentImage] = useState<File | null>(null);
  const [commentImagePreview, setCommentImagePreview] = useState<string | null>(null);
  const commentFileRef = useRef<HTMLInputElement>(null);
  const [submittingComment, setSubmittingComment] = useState(false);
  const [error, setError] = useState('');
  const [commentsError, setCommentsError] = useState('');
  const [claimModal, setClaimModal] = useState<HardClaimItem | null>(null);

  const updateCurrentPost = (updater: (post: PostItem) => PostItem) => {
    setPost((prev) => {
      if (!prev) return prev;
      const next = updater(prev);
      updatePostAcrossCachedFeeds(queryClient, next, auth.address);
      return next;
    });
  };

  const handlePostChange = (updatedPost: PostItem) => {
    setPost(updatedPost);
    updatePostAcrossCachedFeeds(queryClient, updatedPost, auth.address);
  };

  const pickCommentImage = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) { setCommentsError('Please choose an image file.'); return; }
    if (file.size > 10 * 1024 * 1024) { setCommentsError('Image must be 10 MB or smaller.'); return; }
    setCommentsError('');
    setCommentImage(file);
    setCommentImagePreview((prev) => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(file); });
  };

  const clearCommentImage = () => {
    setCommentImage(null);
    setCommentImagePreview((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    if (commentFileRef.current) commentFileRef.current.value = '';
  };

  useEffect(() => {
    if (!id) return;
    const postId = Number(id);
    Promise.all([getPost(postId), fetchAssets(), getPostComments(postId)])
      .then(([found, a, loadedComments]) => {
        setPost(found);
        updatePostAcrossCachedFeeds(queryClient, found, auth.address);
        setAssets(a);
        setComments(loadedComments);
        setCommentsError('');
      })
      .catch((e) => setError(e.message))
      .finally(() => {
        setLoading(false);
        setCommentsLoading(false);
      });
  }, [auth.address, id, queryClient]);

  const handleSubmitComment = async () => {
    if (!post) return;
    if (!auth.authenticated) {
      openLogin(`/post/${post.id}`);
      return;
    }

    const content = commentContent.trim();
    if (!content && !commentImage) {
      setCommentsError('Comment cannot be empty.');
      return;
    }

    setSubmittingComment(true);
    setCommentsError('');
    try {
      const comment = await createPostComment(post.id, content, undefined, commentImage);
      setComments((prev) => [...prev, comment]);
      setCommentContent('');
      clearCommentImage();
      updateCurrentPost((currentPost) => ({
        ...currentPost,
        comment_count: currentPost.comment_count + 1,
      }));
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
    updateCurrentPost((currentPost) => ({
      ...currentPost,
      comment_count: currentPost.comment_count + 1,
    }));
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
            <Link
              to={`/u/${post.author_username || post.author_address}`}
              className="rounded-full transition-opacity hover:opacity-80"
              aria-label={`View profile for ${post.author_username ? `@${post.author_username}` : truncateAddress(post.author_address)}`}
            >
              <UserAvatar address={post.author_address} src={post.author_avatar_url} size="md" />
            </Link>
            <Link
              to={`/u/${post.author_username || post.author_address}`}
              className="text-sm font-mono font-medium hover:underline truncate"
            >
              {post.author_username ? `@${post.author_username}` : truncateAddress(post.author_address)}
            </Link>
            <SmartTimestamp value={post.created_at} mode="full" className="ml-auto text-xs text-muted-foreground" />
          </div>

          <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>

          {post.image_url && (
            <img
              src={safeImageSrc(post.image_url)}
              alt=""
              className="w-full max-h-[32rem] rounded-lg border border-border object-cover"
            />
          )}

          {post.hard_claims.length > 0 && (
            <div className="space-y-3 pt-2">
              <h2 className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Claims
              </h2>
              {post.hard_claims.map((hc) => (
                <div
                  key={hc.id}
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setClaimModal(hc);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setClaimModal(hc);
                    }
                  }}
                  className="cursor-pointer [&_a]:pointer-events-none"
                >
                  <HardClaimCard claim={hc} assets={assets} />
                </div>
              ))}
            </div>
          )}

          {post.positions && post.positions.length > 0 && (
            <div className="space-y-3 pt-2">
              <h2 className="text-[10px] font-semibold uppercase tracking-widest text-position-badge">
                Positions
              </h2>
              {post.positions.map((pos) => (
                <PositionAttachmentCard key={pos.id} position={pos} assets={assets} />
              ))}
            </div>
          )}

          <PostActions post={post} onPostChange={handlePostChange} className="border-t border-border pt-4" />
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
                onPaste={(e) => {
                  const file = imageFileFromClipboard(e.clipboardData);
                  if (file) { e.preventDefault(); pickCommentImage(file); }
                }}
                maxLength={500}
                placeholder="Add a comment"
                className="min-h-20 resize-none"
              />
              <input
                ref={commentFileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pickCommentImage(e.target.files?.[0] ?? null)}
              />
              {commentImagePreview && (
                <div className="relative w-fit">
                  <img src={commentImagePreview} alt="" className="max-h-48 rounded-lg border border-border object-cover" />
                  <button
                    type="button"
                    onClick={clearCommentImage}
                    aria-label="Remove image"
                    className="absolute top-1 right-1 size-6 flex items-center justify-center rounded-full bg-background/80 hover:bg-background"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="text-primary hover:bg-primary/10 hover:text-primary"
                    aria-label="Add image"
                    onClick={() => commentFileRef.current?.click()}
                  >
                    <ImagePlus className="size-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground num">{commentContent.length}/500</span>
                </div>
                <Button
                  size="sm"
                  disabled={submittingComment || (commentContent.trim().length === 0 && !commentImage)}
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



      {/* Claim detail modal */}
      <RD.Root open={!!claimModal} onOpenChange={(v) => !v && setClaimModal(null)}>
        <RD.Content className={CLAIM_DETAIL_DIALOG_CLASS}>
          <RD.Header>
            <RD.Title>Claim Details</RD.Title>
          </RD.Header>
          {claimModal && (
            <div className="overflow-y-auto max-h-[70vh] pr-1">
              <ClaimDetailView claim={claimModal} assets={assets} />
            </div>
          )}
        </RD.Content>
      </RD.Root>
    </PageContent>
  );
}
