import { Link, useLocation } from 'react-router-dom';
import { Bell, Home, Settings, User, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { UserAvatar } from '@/components/UserAvatar';
import { useAuthState } from '@/lib/auth';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  matches: (pathname: string) => boolean;
}

function buildNavItems(): NavItem[] {
  return [
    {
      to: '/feed',
      icon: <Home className="size-5" />,
      label: 'Feed',
      matches: (p) => p === '/feed' || p === '/' || p.startsWith('/post/') || p.startsWith('/claim/'),
    },
    {
      to: '/verify',
      icon: <ShieldCheck className="size-5" />,
      label: 'Verify Proof',
      matches: (p) => p.startsWith('/verify'),
    },
    {
      to: '/notifications',
      icon: <Bell className="size-5" />,
      label: 'Notifications',
      matches: (p) => p.startsWith('/notifications'),
    },
    {
      to: '/settings',
      icon: <Settings className="size-5" />,
      label: 'Settings',
      matches: (p) => p.startsWith('/settings'),
    },
  ];
}

export function BottomTabBar({ unreadNotifications = 0 }: { unreadNotifications?: number }) {
  const location = useLocation();
  const auth = useAuthState();
  const address = auth.address ?? '';
  const profilePath = address ? `/u/${auth.username || address}` : '/login?returnTo=%2Ffeed';
  const items = buildNavItems().map((item) =>
    item.to === '/settings'
      ? {
          to: profilePath,
          icon: address ? (
            <UserAvatar address={address} src={auth.avatar} size="xs" />
          ) : (
            <User className="size-5" />
          ),
          label: address ? 'Profile' : 'Login',
          matches: (p: string) => (address ? p.startsWith('/u/') : p === '/login'),
        }
      : item,
  );
  return (
    <nav
      aria-label="Primary"
      className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-4">
        {items.map((item) => {
          const active = item.matches(location.pathname);
          return (
            <li key={item.label}>
              <Link
                to={item.to}
                className={cn(
                  'flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors',
                  active ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
                )}
                aria-current={active ? 'page' : undefined}
              >
                <span className="relative">
                  {item.icon}
                  {item.to === '/notifications' && unreadNotifications > 0 && (
                    <span className="absolute -right-1.5 -top-1.5 flex min-w-4 justify-center rounded-full bg-primary px-1 text-[9px] font-semibold leading-4 text-primary-foreground">
                      {unreadNotifications > 9 ? '9+' : unreadNotifications}
                    </span>
                  )}
                </span>
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
