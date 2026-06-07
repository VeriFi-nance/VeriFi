import { lazy, Suspense, useEffect } from 'react';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';
import AppLayout from './pages/AppLayout';
import FeedPage from './pages/FeedPage';
import PostDetailPage from './pages/PostDetailPage';
import UserPage from './pages/UserPage';
import SettingsPage from './pages/SettingsPage';
import ClaimDetailPage from './pages/ClaimDetailPage';
import NotificationsPage from './pages/NotificationsPage';
import { clearAuth, loadAddress, loadAuthMethod, openLogin, useAuthState, setAuthMethod } from './lib/auth';
import { clearPrivateKey } from './lib/keystore';
import { authenticateMetaMaskAddress } from './lib/walletAuth';
import { PrivyAccountSync } from './components/PrivyAccountSync';
import { isPrivyConfigured } from './lib/privyAuth';
import { ConfirmProvider } from './components/ConfirmDialog';
import { PasswordPromptProvider } from './components/PasswordPromptProvider';
import { Toaster } from './components/ui/sonner';

// Lazy so the BIP39/BIP32/secp256k1 bundle (only reachable through LoginForm)
// is fetched on demand when the login modal opens, not in the initial chunk.
const LoginModal = lazy(() =>
  import('./components/LoginModal').then((m) => ({ default: m.LoginModal }))
);

const VerifyPage = lazy(() =>
  import('./pages/VerifyPage').then((m) => ({ default: m.VerifyPage }))
);

function WalletAccountSync() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const authMethod = loadAuthMethod();
    if (authMethod && authMethod !== 'metamask') return;
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
        setAuthMethod('metamask');
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

function SettingsGate() {
  const auth = useAuthState();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (auth.authenticated) return;
    if (location.pathname === '/login') return;
    openLogin(navigate, location, '/settings', {
      ...location,
      pathname: '/feed',
      search: '',
      hash: '',
    });
  }, [auth.authenticated, navigate, location]);

  if (!auth.authenticated) return null;
  return <SettingsPage />;
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
        ? { pathname: '/feed', search: '', hash: '', key: 'login-default' }
        : null;

  return (
    <>
      <Routes location={backgroundLocation ?? location}>
        <Route element={<AppLayout />}>
          <Route path="/feed" element={<FeedPage />} />
          <Route path="/post/:id" element={<PostDetailPage />} />
          <Route path="/claim/:id" element={<ClaimDetailPage />} />
          <Route path="/u/:address" element={<UserPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/settings" element={<SettingsGate />} />
          <Route path="/verify" element={<Suspense fallback={null}><VerifyPage /></Suspense>} />
          <Route path="/verify/claim/:id" element={<Suspense fallback={null}><VerifyPage type="claim" /></Suspense>} />
          <Route path="/verify/position/:id" element={<Suspense fallback={null}><VerifyPage type="position" /></Suspense>} />
          <Route path="/login" element={null} />
        </Route>

        <Route path="/" element={<Navigate to="/feed" replace />} />

        {/* Legacy redirects */}
        <Route path="/app" element={<Navigate to="/feed" replace />} />
        <Route path="/app/profile" element={<UserLegacyRedirect />} />
        <Route path="/app/communities" element={<Navigate to="/feed" replace />} />
        <Route path="/app/communities/:id" element={<Navigate to="/feed" replace />} />
        <Route path="/app/post/:id" element={<PostLegacyRedirect />} />
        <Route path="/app/user/:address" element={<UserLegacyRedirect />} />
        <Route path="/c" element={<Navigate to="/feed" replace />} />
        <Route path="/c/:id" element={<Navigate to="/feed" replace />} />

        <Route path="*" element={<Navigate to="/feed" replace />} />
      </Routes>

      {loginOpen && (
        <Suspense fallback={null}>
          <LoginModal />
        </Suspense>
      )}
    </>
  );
}

function UserLegacyRedirect() {
  const { address } = useParams();
  const fallback = loadAddress() ?? '';
  const target = address ?? fallback;
  return <Navigate to={target ? `/u/${target}` : '/feed'} replace />;
}



function PostLegacyRedirect() {
  const { id } = useParams();
  return <Navigate to={id ? `/post/${id}` : '/feed'} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <ConfirmProvider>
        <PasswordPromptProvider>
          <WalletAccountSync />
          {isPrivyConfigured() && <PrivyAccountSync />}
          <AppRoutes />
          <Toaster />
        </PasswordPromptProvider>
      </ConfirmProvider>
    </BrowserRouter>
  );
}
