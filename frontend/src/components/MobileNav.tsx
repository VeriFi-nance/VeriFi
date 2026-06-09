import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Dialog as DialogPrimitive } from 'radix-ui';
import { Bell, Home, Tv, Settings, Menu, LogOut, Sun, Moon, User, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { BrandLogo } from '@/components/BrandLogo';
import type { Theme } from '@/lib/theme';

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
      to: '/channels',
      icon: <Tv className="size-5" />,
      label: 'Channels',
      matches: (p) => p.startsWith('/channels') || p.startsWith('/c'),
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

export interface MobileNavProps {
  authenticated: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  onDisconnect: () => void;
  onLogin: () => void;
  unreadNotifications?: number;
}

export function MobileMenuButton({
  authenticated,
  theme,
  onToggleTheme,
  onDisconnect,
  onLogin,
  unreadNotifications = 0,
}: MobileNavProps) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const items = buildNavItems();

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden size-9"
          aria-label="Open menu"
        >
          <Menu className="size-5" />
        </Button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-background/10 backdrop-blur-md supports-[backdrop-filter]:bg-background/5 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          className={cn(
            'fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-background border-r border-border outline-none',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left',
            'flex flex-col',
          )}
        >
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Primary navigation menu
          </DialogPrimitive.Description>
          <div className="px-5 pt-5 pb-3 flex items-center gap-3">
            <BrandLogo showText link={false} />
          </div>
          <div className="mx-4 h-px bg-border mb-3" />
          <nav className="flex-1 px-3 space-y-1">
            {items.map((item) => {
              const active = item.matches(location.pathname);
              return (
                <DialogPrimitive.Close asChild key={item.to}>
                  <Link
                    to={item.to}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                      active
                        ? 'bg-foreground/5 text-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent',
                    )}
                  >
                    <span className="relative">
                      {item.icon}
                      {item.to === '/notifications' && unreadNotifications > 0 && (
                        <span className="absolute -right-1.5 -top-1.5 flex min-w-4 justify-center rounded-full bg-primary px-1 text-[9px] font-semibold leading-4 text-primary-foreground">
                          {unreadNotifications > 9 ? '9+' : unreadNotifications}
                        </span>
                      )}
                    </span>
                    {item.label}
                  </Link>
                </DialogPrimitive.Close>
              );
            })}
          </nav>
          <div className="px-3 pb-5 pt-3 border-t border-border space-y-1">
            <button
              onClick={onToggleTheme}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              {theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />}
              {theme === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>
            {authenticated ? (
              <button
                onClick={onDisconnect}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
              >
                <LogOut className="size-5" />
                Disconnect
              </button>
            ) : (
              <button
                onClick={onLogin}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                <User className="size-5" />
                Login
              </button>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function BottomTabBar({ unreadNotifications = 0 }: { unreadNotifications?: number }) {
  const location = useLocation();
  const items = buildNavItems();
  return (
    <nav
      aria-label="Primary"
      className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-5">
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
