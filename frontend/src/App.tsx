import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPostsPage from './pages/UserPostsPage';
import ProfilePage from './pages/ProfilePage';
import CommunitiesPage from './pages/CommunitiesPage';
import CommunityDetailPage from './pages/CommunityDetailPage';
import { LoginModal } from './components/LoginModal';
import { clearAuth, loadAddress, openLogin } from './lib/auth';
import { clearPrivateKey } from './lib/crypto';
import { authenticateMetaMaskAddress } from './lib/walletAuth';

function WalletAccountSync() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!window.ethereum?.on || !window.ethereum?.removeListener) return;
    let cancelled = false;

    const onAccountsChanged = async (accounts: string[]) => {
      if (cancelled) return;
      const next = accounts[0]?.toLowerCase();
      const current = loadAddress()?.toLowerCase();
      if (!next) {
        clearAuth();
        clearPrivateKey();
        return;
      }
      if (next === current) return;
      try {
        await authenticateMetaMaskAddress(next);
      } catch {
        clearAuth();
        clearPrivateKey();
        openLogin(navigate, location, location.pathname);
      }
    };

    window.ethereum.on('accountsChanged', onAccountsChanged);
    return () => {
      cancelled = true;
      window.ethereum?.removeListener?.('accountsChanged', onAccountsChanged);
    };
  }, [navigate, location]);

  return null;
}

function AppRoutes() {
  const location = useLocation();
  const loginOpen = location.pathname === '/login';
  const backgroundState = (location.state as { background?: ReturnType<typeof useLocation> } | null)
    ?.background;
  const backgroundLocation =
    loginOpen && backgroundState
      ? backgroundState
      : loginOpen
        ? { pathname: '/app', search: '', hash: '', key: 'login-default' }
        : null;

  return (
    <>
      <Routes location={backgroundLocation ?? location}>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<FeedPage />} />
          <Route path="post/:id" element={<PostDetailPage />} />
          <Route path="user/:address" element={<UserPostsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="communities" element={<CommunitiesPage />} />
          <Route path="communities/:id" element={<CommunityDetailPage />} />
        </Route>
      </Routes>
      {loginOpen && <LoginModal />}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <WalletAccountSync />
      <AppRoutes />
    </BrowserRouter>
  );
}
