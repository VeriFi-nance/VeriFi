import { Home, ShieldCheck, Settings, Tv } from 'lucide-react';

export interface NavItem {
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

export function pageTitle(pathname: string): string {
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
