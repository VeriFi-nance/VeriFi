import { Link, useLocation } from 'react-router-dom';
import { User, Moon, Sun } from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';
import { UserAvatar } from '@/components/UserAvatar';
import { truncateAddress } from '@/lib/wallet';
import { cn } from '@/lib/utils';
import { buildNavItems } from '@/lib/navigation';
import type { Theme } from '@/lib/theme';

export interface SidebarProps {
  theme: Theme;
  onToggleTheme: () => void;
  authenticated: boolean;
  address?: string;
  username?: string | null;
  onDisconnect: () => void;
  onLogin: () => void;
}

export function Sidebar({
  theme,
  onToggleTheme,
  authenticated,
  address,
  username,
  onDisconnect,
  onLogin,
}: SidebarProps) {
  const location = useLocation();
  const items = buildNavItems();

  return (
    <aside className={cn(
      "hidden md:flex flex-col w-[240px] shrink-0 h-dvh relative overflow-hidden",
      "bg-sidebar border-r border-border",
      "before:content-[''] before:absolute before:top-0 before:inset-x-0 before:h-[180px]",
      "before:bg-[radial-gradient(ellipse_at_top_left,var(--color-primary)_0%,transparent_70%)] before:opacity-15 before:pointer-events-none"
    )}>
      <div className="h-16 flex items-center px-5 border-b border-border gap-2.5 z-10">
        <BrandLogo responsiveText />
      </div>

      <nav className="flex flex-col gap-0.5 p-3 z-10">
        {items.map((item) => {
          const active = item.matches(location.pathname);
          return (
            <Link
              key={item.label}
              to={item.to}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2.5 w-full text-left rounded-md text-[13.5px] font-medium transition-all duration-150 relative",
                active ? "text-primary bg-primary/15" : "text-muted-foreground hover:text-foreground hover:bg-accent"
              )}
            >
              {active && <span className="absolute left-0 top-[6px] bottom-[6px] w-[3px] bg-primary rounded-r-sm" />}
              {item.icon}
              {item.label}
            </Link>
          );
        })}
        
        <button
          onClick={onToggleTheme}
          className="mt-1 flex items-center justify-between px-3 py-2 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-all duration-150"
          title="Toggle Theme"
        >
          <div className="flex items-center gap-2.5 text-[13.5px] font-medium">
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            <span>Theme</span>
          </div>
        </button>
      </nav>

      <div className="px-6 pt-4 pb-2 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground z-10">
        Markets
      </div>
      
      <div className="flex flex-col gap-0.5 px-3 z-10">
        <MarketRow name="BTC/USD" colorClass="bg-[#F59E0B]" chg="+2.4%" positive />
        <MarketRow name="ETH/USD" colorClass="bg-[#627EEA]" chg="+1.8%" positive />
        <MarketRow name="SOL/USD" colorClass="bg-[#9945FF]" chg="-0.9%" />
        <MarketRow name="MATIC" colorClass="bg-[#2775CA]" chg="+3.2%" positive />
      </div>

      <div className="flex-1" />

      <div className="border-t border-border z-10">
        {authenticated && address ? (
          <div className="p-3 flex items-center gap-2.5 hover:bg-accent transition-colors duration-150 cursor-pointer" onClick={onDisconnect} title="Disconnect">
            <UserAvatar address={address} size="sm" />
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-foreground truncate">
                {username ? `@${username}` : truncateAddress(address)}
              </div>
              <div className="text-[11px] text-primary">87.4% Truth Score</div>
            </div>
          </div>
        ) : (
          <div className="p-3">
            <button
              onClick={onLogin}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-all duration-150"
            >
              <User className="size-5 shrink-0" />
              <span>Login</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

function MarketRow({ name, colorClass, chg, positive }: { name: string; colorClass: string; chg: string; positive?: boolean }) {
  return (
    <div className="flex items-center justify-between px-3 py-[7px] rounded-md hover:bg-accent cursor-pointer transition-colors duration-150">
      <div className="flex items-center gap-2 text-[12.5px] font-medium text-foreground">
        <div className={cn("size-2 rounded-full shrink-0", colorClass)} />
        {name}
      </div>
      <span className={cn("font-mono text-[11.5px] font-semibold", positive ? "text-bullish" : "text-bearish")}>
        {chg}
      </span>
    </div>
  );
}
