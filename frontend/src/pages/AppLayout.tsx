/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Home, LogOut, Moon, Settings, Sun, User, Tv, ShieldCheck } from 'lucide-react';
import { clearAuth, useAuthState, useOpenLogin } from '@/lib/auth';
import { clearPrivateKey } from '@/lib/crypto';
import { loadTheme, toggleTheme, type Theme } from '@/lib/theme';
import { EnergyMeter } from '@/components/EnergyMeter';
import { UserAvatar } from '@/components/UserAvatar';
import { truncateAddress } from '@/lib/wallet';
import { MobileMenuButton, BottomTabBar } from '@/components/MobileNav';
import { BrandLogo } from '@/components/BrandLogo';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  matches: (pathname: string) => boolean;
}

export function buildNavItems(): NavItem[] {
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
      to: '/settings',
      icon: <Settings className="size-5" />,
      label: 'Settings',
      matches: (p) => p.startsWith('/settings'),
    },
  ];
}

const SITE_TITLE = 'VeriFi — Verifiable finance predictions';

function pageTitle(pathname: string): string {
  if (pathname === '/feed' || pathname === '/' || pathname === '') return 'Feed';
  if (pathname.startsWith('/settings')) return 'Settings';
  if (pathname.startsWith('/post/')) return 'Post';
  if (pathname.startsWith('/claim/')) return 'Claim';
  if (pathname.startsWith('/u/')) return 'Profile';
  if (pathname.startsWith('/channels/')) return 'Channel';
  if (pathname === '/channels') return 'Channels';
  if (pathname.startsWith('/c/')) return 'Channel';
  if (pathname === '/c') return 'Channels';
  return 'VeriFi';
}

function DesktopNavLink({
  to,
  icon,
  label,
  active,
}: {
  to: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      to={to}
      title={label}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
        'justify-center lg:justify-start',
        active
          ? 'bg-foreground/5 text-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent',
      )}
    >
      {icon}
      <span className="hidden lg:inline">{label}</span>
    </Link>
  );
}

export default function AppLayout() {
  const location = useLocation();
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const address = auth.address ?? '';
  const username = auth.username;
  const [theme, setTheme] = useState<Theme>(loadTheme);

  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === 'verifi-theme' && (e.newValue === 'dark' || e.newValue === 'light')) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const items = buildNavItems();
  const title = pageTitle(location.pathname);

  useEffect(() => {
    document.title = title === 'VeriFi' ? SITE_TITLE : `${title} · VeriFi`;
  }, [title]);

  function handleThemeToggle() {
    const next = toggleTheme();
    setTheme(next);
  }

  function handleDisconnect() {
    clearAuth();
    clearPrivateKey();
  }

  function goLogin() {
    openLogin(location.pathname);
  }

  return (
    <div className="min-h-dvh flex bg-background">
      <div className="flex w-full max-w-[1300px] mx-auto relative">

        <aside
          className={cn(
            'hidden md:flex sticky top-0 h-dvh flex-col border-r border-border bg-background shrink-0 self-start',
            'w-14 lg:w-56 transition-[width] duration-200',
          )}
          aria-label="Primary navigation"
        >
          <div className="px-3 lg:px-5 pt-5 pb-4 flex items-center justify-center lg:justify-start">
            <BrandLogo responsiveText />
          </div>

          <div className="mx-3 lg:mx-4 h-px bg-border mb-3" />

          <nav className="flex-1 px-2 lg:px-3 space-y-1">
            {items.map((item) => (
              <DesktopNavLink
                key={item.label}
                to={item.to}
                icon={item.icon}
                label={item.label}
                active={item.matches(location.pathname)}
              />
            ))}
          </nav>

          <div className="px-2 lg:px-3 pb-5 pt-3 border-t border-border">
            {auth.authenticated ? (
              <button
                onClick={handleDisconnect}
                title="Disconnect"
                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors justify-center lg:justify-start"
              >
                <LogOut className="size-5 shrink-0" />
                <span className="hidden lg:inline">Disconnect</span>
              </button>
            ) : (
              <button
                onClick={goLogin}
                title="Login"
                className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors justify-center lg:justify-start"
              >
                <User className="size-5 shrink-0" />
                <span className="hidden lg:inline">Login</span>
              </button>
            )}
          </div>
        </aside>

        {/* Main column */}
        <div className="flex flex-col flex-1 min-w-0">
          <header className="sticky top-0 z-20 h-14 flex items-center border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 px-4 sm:px-6 gap-3">
            <MobileMenuButton
              authenticated={auth.authenticated}
              theme={theme}
              onToggleTheme={handleThemeToggle}
              onDisconnect={handleDisconnect}
              onLogin={goLogin}
            />

            <h1 className="text-base sm:text-lg font-semibold tracking-tight flex-1 truncate">
              {title}
            </h1>

            <div className="flex items-center gap-2 sm:gap-3">
              <div className="hidden sm:block">
                <EnergyMeter />
              </div>

              <Button
                variant="ghost"
                size="icon"
                className="size-8 rounded-full text-muted-foreground hover:text-foreground"
                onClick={handleThemeToggle}
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </Button>

              {address && (
                <Link
                  to={`/u/${username || address}`}
                  className="flex items-center gap-2 hover:opacity-80 transition-opacity"
                  aria-label="Your profile"
                >
                  <UserAvatar address={address} size="sm" ring />
                  <span className="hidden sm:inline text-sm font-mono text-muted-foreground">
                    {username ? `@${username}` : truncateAddress(address)}
                  </span>
                </Link>
              )}
            </div>
          </header>

          <main className="relative flex-1 w-full px-4 sm:px-6 py-5 pb-24 md:pb-5">
            <div
              aria-hidden
              className="main-grid-bg pointer-events-none absolute inset-0 z-0"
            />
            <div className="relative z-10">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      <BottomTabBar />
    </div>
  );
}
