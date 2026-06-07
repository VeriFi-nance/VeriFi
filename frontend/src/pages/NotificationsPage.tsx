import { useEffect, useMemo, useState } from 'react';
import { Bell, CheckCheck, Loader2 } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';
import { PageContent } from '@/components/PageContent';
import { UserAvatar } from '@/components/UserAvatar';
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
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

export default function NotificationsPage() {
  const auth = useAuthState();
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const unreadCount = useMemo(() => items.filter((item) => item.unread).length, [items]);

  async function handleMarkRead(item: NotificationItem) {
    if (item.unread) {
      try {
        const updated = await markNotificationRead(item.id);
        setItems((prev) => prev.map((n) => (n.id === item.id ? updated : n)));
        window.dispatchEvent(new Event('notifications-updated'));
      } catch {
        /* Navigation should still work if marking read fails. */
      }
    }
    if (item.target_url) navigate(item.target_url);
  }

  async function handleMarkAllRead() {
    setBusy(true);
    try {
      await markAllNotificationsRead();
      const now = new Date().toISOString();
      setItems((prev) => prev.map((item) => ({ ...item, unread: false, read_at: item.read_at ?? now })));
      window.dispatchEvent(new Event('notifications-updated'));
    } finally {
      setBusy(false);
    }
  }

  if (!auth.authenticated) return null;

  return (
    <PageContent className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-normal">Notifications</h1>
          <p className="text-sm text-muted-foreground">
            {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={handleMarkAllRead}
          disabled={busy || unreadCount === 0}
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <CheckCheck className="size-4" />}
          Mark all read
        </Button>
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
            <button
              key={item.id}
              type="button"
              onClick={() => handleMarkRead(item)}
              className={cn(
                'w-full flex items-start gap-3 px-4 py-3 text-left border-b border-border last:border-b-0 transition-colors',
                item.unread ? 'bg-foreground/[0.03]' : 'hover:bg-accent/60',
              )}
            >
              <UserAvatar
                address={item.actor_address || 'system'}
                src={item.actor_avatar_url}
                size="sm"
                ring={item.unread}
              />
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
          ))}
        </div>
      )}
    </PageContent>
  );
}
