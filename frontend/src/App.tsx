import { useEffect } from 'react';
import type { ReactNode } from 'react';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPage from './pages/UserPage';
import SettingsPage from './pages/SettingsPage';
import CommunitiesPage from './pages/CommunitiesPage';
import CommunityDetailPage from './pages/CommunityDetailPage';
import { clearAuth, isAuthenticated, loadAddress } from './lib/auth';
import { clearPrivateKey } from './lib/crypto';
import { authenticateMetaMaskAddress } from './lib/walletAuth';

function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function WalletAccountSync() {
  const navigate = useNavigate();

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
        navigate('/login', { replace: true });
      }
    };

    window.ethereum.on('accountsChanged', onAccountsChanged);
    return () => {
      cancelled = true;
      window.ethereum?.removeListener?.('accountsChanged', onAccountsChanged);
    };
  }, [navigate]);

  return null;
}

function RootRedirect() {
  return <Navigate to={isAuthenticated() ? '/feed' : '/login'} replace />;
}

function UserLegacyRedirect() {
  const { address } = useParams();
  const fallback = loadAddress() ?? '';
  const target = address ?? fallback;
  return <Navigate to={target ? `/u/${target}` : '/feed'} replace />;
}

function CommunityLegacyRedirect() {
  const { id } = useParams();
  return <Navigate to={id ? `/c/${id}` : '/c'} replace />;
}

function PostLegacyRedirect() {
  const { id } = useParams();
  return <Navigate to={id ? `/post/${id}` : '/feed'} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <WalletAccountSync />
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/feed" element={<FeedPage />} />
          <Route path="/post/:id" element={<PostDetailPage />} />
          <Route path="/u/:address" element={<UserPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/c" element={<CommunitiesPage />} />
          <Route path="/c/:id" element={<CommunityDetailPage />} />
        </Route>

        {/* Legacy redirects */}
        <Route path="/app" element={<Navigate to="/feed" replace />} />
        <Route path="/app/profile" element={<UserLegacyRedirect />} />
        <Route path="/app/communities" element={<Navigate to="/c" replace />} />
        <Route path="/app/communities/:id" element={<CommunityLegacyRedirect />} />
        <Route path="/app/post/:id" element={<PostLegacyRedirect />} />
        <Route path="/app/user/:address" element={<UserLegacyRedirect />} />

        <Route path="*" element={<Navigate to="/feed" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
