import { Link } from 'react-router-dom';
import { EnergyMeter } from '@/components/EnergyMeter';
import { UserAvatar } from '@/components/UserAvatar';
import { truncateAddress } from '@/lib/wallet';
import { MobileMenuButton } from '@/components/MobileNav';
import type { Theme } from '@/lib/theme';

export interface TopNavProps {
  title: string;
  authenticated: boolean;
  address?: string;
  username?: string | null;
  theme: Theme;
  onToggleTheme: () => void;
  onDisconnect: () => void;
  onLogin: () => void;
}

export function TopNav({
  title,
  authenticated,
  address,
  username,
  theme,
  onToggleTheme,
  onDisconnect,
  onLogin,
}: TopNavProps) {
  return (
    <header className="sticky top-0 z-20 h-16 flex items-center justify-between px-6 bg-surface/95 backdrop-blur-[16px] border-b border-border shrink-0">
      <div className="flex items-center gap-3">
        <MobileMenuButton
          authenticated={authenticated}
          theme={theme}
          onToggleTheme={onToggleTheme}
          onDisconnect={onDisconnect}
          onLogin={onLogin}
        />
        <h1 className="text-[18px] font-semibold tracking-[-0.01em]">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-2.5">
        <div className="hidden sm:block">
          <EnergyMeter />
        </div>

        {/* Truth Score Pill Placeholder */}
        <div 
          className="hidden sm:flex items-center gap-1.5 px-3 py-[5px] bg-primary/10 border border-primary/25 rounded-full cursor-pointer hover:shadow-[0_0_18px_rgba(245,158,11,0.18)] transition-all duration-150"
          title="Your Truth Score"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <polyline points="9 12 11 14 15 10"/>
          </svg>
          <span className="font-mono text-[12px] font-semibold text-primary">87.4%</span>
        </div>

        {address && (
          <>
            <div className="hidden sm:block w-[1px] h-6 bg-border mx-1" />
            <Link
              to={`/u/${username || address}`}
              className="flex items-center gap-2 py-1 pr-2 pl-1 rounded-full hover:bg-elevated transition-colors duration-150"
              aria-label="Your profile"
            >
              <UserAvatar address={address} size="sm" />
              <span className="hidden sm:inline text-[13px] font-medium">
                {username ? `@${username}` : truncateAddress(address)}
              </span>
            </Link>
          </>
        )}
      </div>
    </header>
  );
}
