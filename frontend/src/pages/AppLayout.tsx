import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { clearAuth, useAuthState, useOpenLogin } from '@/lib/auth';
import { clearPrivateKey } from '@/lib/keystore';
import { loadTheme, toggleTheme, type Theme } from '@/lib/theme';
import { BottomTabBar } from '@/components/MobileNav';
import { pageTitle } from '@/lib/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopNav } from '@/components/layout/TopNav';
import { MainContent } from '@/components/layout/MainContent';

const SITE_TITLE = 'VeriFi — Verifiable finance predictions';

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

  const title = pageTitle(location.pathname);

  useEffect(() => {
    document.title = title === 'VeriFi' ? SITE_TITLE : `${title} · VeriFi`;
  }, [title]);

  function handleThemeToggle() {
    setTheme(toggleTheme());
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
        <Sidebar
          theme={theme}
          onToggleTheme={handleThemeToggle}
          authenticated={auth.authenticated}
          address={address}
          username={username}
          onDisconnect={handleDisconnect}
          onLogin={goLogin}
        />

        <div className="flex flex-col flex-1 min-w-0">
          <TopNav
            title={title}
            authenticated={auth.authenticated}
            address={address}
            username={username}
            theme={theme}
            onToggleTheme={handleThemeToggle}
            onDisconnect={handleDisconnect}
            onLogin={goLogin}
          />
          <MainContent>
            <Outlet />
          </MainContent>
        </div>
      </div>
      <BottomTabBar />
    </div>
  );
}
