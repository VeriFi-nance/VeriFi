import { useEffect, useRef, useState } from 'react';
import { Bell, Loader2, Trash2 } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { EmptyState } from '@/components/EmptyState';
import { PageContent } from '@/components/PageContent';
import { UserAvatar } from '@/components/UserAvatar';
import {
  deleteNotification,
  getNotifications,
  markAllNotificationsRead,
} from '@/lib/api';
import { openLogin, useAuthState } from '@/lib/auth';
import type { NotificationItem } from '@/lib/types';
import { cn } from '@/lib/utils';

function formatTime(value: string): string {
  const date = new Date(value);
  const now = Date.now();
  const diff = Math.max(0, now - date.getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return date.toLocaleDateString();
}

function actorLabel(item: NotificationItem): string {
  if (item.actor_username) return `@${item.actor_username}`;
  if (item.actor_address) return `${item.actor_address.slice(0, 6)}...${item.actor_address.slice(-4)}`;
  return 'VeriFi';
}

function actorProfilePath(item: NotificationItem): string | null {
  if (!item.actor_address) return null;
  return `/u/${item.actor_username || item.actor_address}`;
}

export default function NotificationsPage() {
  const auth = useAuthState();
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const markedRef = useRef(false);

  useEffect(() => {
    if (auth.authenticated) return;
    openLogin(navigate, location, '/notifications');
  }, [auth.authenticated, navigate, location]);

  useEffect(() => {
    if (!auth.authenticated) return;
    let cancelled = false;
    setLoading(true);
    getNotifications({ page_size: 100 })
      .then((res) => {
        if (cancelled) return;
        setItems(res.results);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Could not load notifications.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.authenticated]);

  // Mark everything read once on landing, then clear the nav badge.
  useEffect(() => {
    if (!auth.authenticated || loading || error || markedRef.current) return;
    if (!items.some((item) => item.unread)) return;
    markedRef.current = true;
    markAllNotificationsRead()
      .then(() => {
        const now = new Date().toISOString();
        setItems((prev) => prev.map((item) => ({ ...item, unread: false, read_at: item.read_at ?? now })));
        window.dispatchEvent(new Event('notifications-updated'));
      })
      .catch(() => {
        markedRef.current = false;
      });
  }, [auth.authenticated, loading, error, items]);

  function handleOpen(item: NotificationItem) {
    if (item.target_url) navigate(item.target_url);
  }

  async function handleDelete(id: number) {
    const prev = items;
    setItems((curr) => curr.filter((n) => n.id !== id));
    try {
      await deleteNotification(id);
      window.dispatchEvent(new Event('notifications-updated'));
    } catch {
      setItems(prev);
    }
  }

  if (!auth.authenticated) return null;

  return (
    <PageContent className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-normal">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          {items.length > 0 ? `${items.length} notification${items.length === 1 ? '' : 's'}` : 'All caught up'}
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-12 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      ) : error ? (
        <EmptyState icon={<Bell className="size-5" />} title="Could not load notifications" description={error} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bell className="size-5" />}
          title="No notifications yet"
          description="Likes, comments, resolutions, and balance updates will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-md border border-border bg-background">
          {items.map((item) => (
            <div
              key={item.id}
              className={cn(
                'group flex items-stretch border-b border-border last:border-b-0 transition-colors',
                item.unread ? 'bg-foreground/[0.03]' : 'hover:bg-accent/60',
              )}
            >
              {actorProfilePath(item) ? (
                <Link
                  to={actorProfilePath(item)!}
                  className="ml-4 mt-3 h-fit rounded-full transition-opacity hover:opacity-80"
                  aria-label={`View profile for ${actorLabel(item)}`}
                >
                  <UserAvatar
                    address={item.actor_address || 'system'}
                    src={item.actor_avatar_url}
                    size="sm"
                    ring={item.unread}
                  />
                </Link>
              ) : (
                <div className="ml-4 mt-3 h-fit">
                  <UserAvatar
                    address="system"
                    src={item.actor_avatar_url}
                    size="sm"
                    ring={item.unread}
                  />
                </div>
              )}
              <button
                type="button"
                onClick={() => handleOpen(item)}
                className="flex min-w-0 flex-1 items-start py-3 pl-3 pr-2 text-left"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium leading-snug">
                      {item.title}
                      {item.unread && <span className="ml-2 inline-block size-2 rounded-full bg-primary align-middle" />}
                    </p>
                    <span className="shrink-0 text-xs text-muted-foreground font-mono">
                      {formatTime(item.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-snug">
                    <span className="text-foreground">{actorLabel(item)}</span>
                    {item.message ? ` · ${item.message}` : ''}
                  </p>
                  {item.target_url && <span className="inline-flex text-xs font-medium text-primary">Open</span>}
                </div>
              </button>
              <button
                type="button"
                onClick={() => handleDelete(item.id)}
                aria-label="Delete notification"
                className="flex shrink-0 items-center px-3 text-muted-foreground opacity-0 transition-colors hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </PageContent>
  );
}
