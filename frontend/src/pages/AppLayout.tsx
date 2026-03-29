import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Home, User, LogOut } from 'lucide-react';
import { clearAuth } from '@/lib/auth';
import { clearPrivateKey } from '@/lib/crypto';

function NavLink({
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
      variant={active ? 'navActive' : 'ghost'}
      size="lg"
      asChild
      className="gap-2 font-semibold"
    >
      <Link to={to}>
        {icon}
        {label}
      </Link>
    </Button>
  );
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const isFeed = location.pathname === '/app' || location.pathname === '/app/';

  function handleDisconnect() {
    clearAuth();
    clearPrivateKey();
    navigate('/login');
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* ── Navbar ──────────────────────────────────────────────────────── */}
      <header className="border-b sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">

          {/* Brand */}
          <Button variant="ghost" size="lg" asChild className="gap-3 px-2 hover:bg-transparent shrink-0">
            <Link to="/app">
              <img src="/logo.png" alt="VeriFi" className="h-10 w-auto" />
            </Link>
          </Button>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Nav links + Disconnect — grouped on the right */}
          <nav className="flex items-center gap-1">
            <NavLink
              to="/app"
              icon={<Home className="size-5" />}
              label="Feed"
              active={isFeed}
            />
            <NavLink
              to="/app/profile"
              icon={<User className="size-5" />}
              label="Profile"
              active={location.pathname === '/app/profile'}
            />
          </nav>

          {/* Disconnect */}
          <Button
            variant="outline"
            size="lg"
            className="gap-2 shrink-0"
            onClick={handleDisconnect}
          >
            <LogOut className="size-5" />
            Disconnect
          </Button>
        </div>
      </header>

      {/* ── Page content ────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
