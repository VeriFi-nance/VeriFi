import { useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Home, User, LogOut, Sun, Moon, Users } from 'lucide-react';
import { clearAuth, loadAddress } from '@/lib/auth';
import { clearPrivateKey } from '@/lib/crypto';
import { loadTheme, toggleTheme, type Theme } from '@/lib/theme';

/** Derive a stable avatar background hue from an address. */
function avatarColor(addr: string): string {
  const hue = (parseInt(addr.slice(2, 4), 16) % 120) + 200;
  return `hsl(${hue} 70% 55%)`;
}

function truncateAddress(addr: string) {
  if (!addr || addr.length <= 12) return addr || '—';
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function SidebarNavLink({
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
    <Button
      variant="ghost"
      size="lg"
      asChild
      className={[
        'w-full justify-start gap-3 px-4 py-3 h-auto font-semibold text-base rounded-xl transition-all duration-150',
        active
          ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.15)] hover:bg-indigo-500/15 hover:text-indigo-300'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent border border-transparent',
      ].join(' ')}
    >
      <Link to={to}>
        {icon}
        {label}
      </Link>
    </Button>
  );
}

/** Simple path-based title — avoids multiple useMatch hook calls that can
 *  cause stale renders on client-side navigation. */
function pageTitle(pathname: string): string {
  if (pathname === '/app' || pathname === '/app/') return 'Feed';
  if (pathname === '/app/profile') return 'Profile';
  if (pathname.startsWith('/app/post/review')) return 'Review Claims';
  if (pathname.startsWith('/app/post/')) return 'Post';
  if (pathname.startsWith('/app/user/')) return 'User';
  if (pathname.startsWith('/app/communities')) return 'Communities';
  return 'VeriFi';
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const address = loadAddress() ?? '';
  const [theme, setTheme] = useState<Theme>(loadTheme);

  useEffect(() => {
    // Listen for storage changes (if user opens multiple tabs)
    const handler = (e: StorageEvent) => {
      if (e.key === 'verifi-theme' && (e.newValue === 'dark' || e.newValue === 'light')) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const isFeed = location.pathname === '/app' || location.pathname === '/app/';
  const isProfile = location.pathname === '/app/profile';
  const isCommunities = location.pathname.startsWith('/app/communities');
  const title = pageTitle(location.pathname);

  function handleThemeToggle() {
    const next = toggleTheme();
    setTheme(next);
  }

  function handleDisconnect() {
    clearAuth();
    clearPrivateKey();
    navigate('/login');
  }

  return (
    /* Max-width cap so the UI stays readable on ultrawide monitors */
    <div className="min-h-screen flex bg-background">
      <div className="flex w-full max-w-[1300px] mx-auto relative">

        {/* ── Left Sidebar ─────────────────────────────────────────────────── */}
        <aside className="sticky top-0 h-screen w-60 flex flex-col border-r bg-background shrink-0 self-start">

          {/* Brand */}
          <div className="px-5 pt-5 pb-4">
            <Link to="/app" className="flex items-center gap-3 group">
              <img src="/logo.png" alt="VeriFi" className="h-8 w-auto group-hover:scale-105 transition-transform shrink-0" />
            </Link>
          </div>

          {/* Divider */}
          <div className="mx-4 h-px bg-border mb-3" />

          {/* Nav links */}
          <nav className="flex-1 px-3 space-y-1">
            <SidebarNavLink
              to="/app"
              icon={<Home className="size-5 shrink-0" />}
              label="Feed"
              active={isFeed}
            />
            <SidebarNavLink
              to="/app/profile"
              icon={<User className="size-5 shrink-0" />}
              label="Profile"
              active={isProfile}
            />
            <SidebarNavLink
              to="/app/communities"
              icon={<Users className="size-5 shrink-0" />}
              label="Communities"
              active={isCommunities}
            />
          </nav>

          {/* Disconnect button at bottom */}
          <div className="px-3 pb-6 pt-3 border-t">
            <Button
              variant="ghost"
              size="lg"
              className="w-full justify-start gap-3 px-4 py-3 h-auto text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl font-semibold text-base transition-all duration-150"
              onClick={handleDisconnect}
            >
              <LogOut className="size-5 shrink-0" />
              Disconnect
            </Button>
          </div>
        </aside>

        {/* ── Right column (top bar + main content) ─────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0">

          {/* ── Slim Top Bar ─────────────────────────────────────────────────── */}
          <header className="sticky top-0 z-10 h-14 flex items-center border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 px-6">

            {/* Page title — left aligned */}
            <h1 className="text-md font-semibold tracking-tight flex-1">{title}</h1>

            {/* Right side controls */}
            <div className="flex items-center gap-3">
              {/* Theme toggle */}
              <Button
                variant="ghost"
                size="icon"
                className="size-8 rounded-full text-muted-foreground hover:text-foreground"
                onClick={handleThemeToggle}
                title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </Button>

              {/* Wallet info */}
              {address && (
              <div className="flex items-center gap-2.5">
                <div
                  className="size-8 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0 select-none ring-2 ring-background"
                  style={{ background: avatarColor(address) }}
                  aria-hidden
                >
                  {address.slice(2, 4).toUpperCase()}
                </div>
                <span className="text-sm font-mono text-muted-foreground">{truncateAddress(address)}</span>
              </div>
              )}
            </div>
          </header>

          {/* ── Page content ─────────────────────────────────────────────────── */}
          <main className="flex-1 w-full px-6 py-6">
            <Outlet />
          </main>
        </div>

      </div>
    </div>
  );
}
