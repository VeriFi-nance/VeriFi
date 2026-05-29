import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import ClaimReviewPage from './pages/ClaimReviewPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPostsPage from './pages/UserPostsPage';
import ProfilePage from './pages/ProfilePage';
import { clearAuth, loadAddress } from './lib/auth';
import { clearPrivateKey } from './lib/crypto';
import { authenticateMetaMaskAddress } from './lib/walletAuth';

import CommunitiesPage from './pages/CommunitiesPage';
import CommunityDetailPage from './pages/CommunityDetailPage';

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

export default function App() {
  return (
    <BrowserRouter>
      <WalletAccountSync />
      <Routes>
        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<FeedPage />} />
          <Route path="post/review" element={<ClaimReviewPage />} />
          <Route path="post/:id" element={<PostDetailPage />} />
          <Route path="user/:address" element={<UserPostsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="communities" element={<CommunitiesPage />} />
          <Route path="communities/:id" element={<CommunityDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
