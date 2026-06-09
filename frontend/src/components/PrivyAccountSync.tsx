import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCreateWallet, usePrivy, useWallets } from '@privy-io/react-auth';
import {
  clearAuth,
  isBackendTokenUsable,
  loadAddress,
  loadAuthMethod,
  loginReturnTo,
  openLogin,
  useAuthState,
} from '@/lib/auth';
import { clearPrivateKey } from '@/lib/keystore';
import {
  findPrivyEmbeddedWallet,
  isPrivyConfigured,
  registerPrivySignerFromWallet,
  syncPrivyWalletToVerifi,
} from '@/lib/privyAuth';
import { registerPrivyLogout, clearPrivyLogout } from '@/lib/privyLogout';
import { clearPrivySigner } from '@/lib/privySigner';
import {
  clearPrivySyncState,
  setPrivySyncError,
  setPrivySyncPending,
} from '@/lib/privySyncState';

export function PrivyAccountSync() {
  const { ready, authenticated, logout } = usePrivy();
  const { wallets, ready: walletsReady } = useWallets();
  const { createWallet } = useCreateWallet();
  const navigate = useNavigate();
  const location = useLocation();
  const authState = useAuthState();
  const creatingWalletRef = useRef(false);
  const syncingRef = useRef(false);

  useEffect(() => {
    if (!isPrivyConfigured()) return;
    registerPrivyLogout(logout);
    return () => clearPrivyLogout();
  }, [logout]);

  // Complete VeriFi login once Privy OAuth + embedded wallet are ready.
  useEffect(() => {
    if (!ready || !authenticated || !walletsReady) return;

    const wallet = findPrivyEmbeddedWallet(wallets);
    if (!wallet?.address) {
      if (!creatingWalletRef.current) {
        creatingWalletRef.current = true;
        setPrivySyncPending(true);
        void createWallet()
          .catch(() => {
            // Wallet may already exist; wallets array will update on next render.
          })
          .finally(() => {
            creatingWalletRef.current = false;
            setPrivySyncPending(false);
          });
      }
      return;
    }

    const walletAddress = wallet.address.toLowerCase();
    const currentAddress = authState.address?.toLowerCase() ?? loadAddress()?.toLowerCase();
    const alreadySynced =
      authState.authenticated &&
      isBackendTokenUsable(authState.token) &&
      loadAuthMethod() === 'privy' &&
      currentAddress === walletAddress;

    if (alreadySynced) {
      void registerPrivySignerFromWallet(wallet);
      return;
    }

    if (syncingRef.current) return;
    syncingRef.current = true;
    setPrivySyncPending(true);
    setPrivySyncError(null);

    void syncPrivyWalletToVerifi(wallet)
      .then(() => {
        if (location.pathname === '/login') {
          const returnTo = loginReturnTo(new URLSearchParams(location.search));
          navigate(returnTo, { replace: true });
        }
      })
      .catch(async (err: unknown) => {
        const message =
          err instanceof Error ? err.message : 'Failed to complete Google sign-in';
        setPrivySyncError(message);
        await logout();
        clearAuth();
        clearPrivateKey();
        clearPrivySigner();
      })
      .finally(() => {
        syncingRef.current = false;
        setPrivySyncPending(false);
      });
  }, [
    ready,
    authenticated,
    walletsReady,
    wallets,
    createWallet,
    navigate,
    location.pathname,
    location.search,
    logout,
    authState.address,
    authState.authenticated,
    authState.token,
  ]);

  // Privy session ended — clear VeriFi session if it was a Privy login.
  useEffect(() => {
    if (!ready || authenticated) return;
    if (loadAuthMethod() !== 'privy') return;

    clearAuth();
    clearPrivateKey();
    clearPrivySigner();
    clearPrivySyncState();
  }, [ready, authenticated]);

  // Wallet address changed while logged in via Privy.
  useEffect(() => {
    if (!ready || !authenticated || !walletsReady) return;
    if (loadAuthMethod() !== 'privy') return;

    const wallet = findPrivyEmbeddedWallet(wallets);
    if (!wallet?.address) return;

    const current = loadAddress()?.toLowerCase();
    const next = wallet.address.toLowerCase();
    if (!current || current === next) return;

    if (syncingRef.current) return;
    syncingRef.current = true;
    setPrivySyncPending(true);

    void syncPrivyWalletToVerifi(wallet)
      .catch(() => {
        clearAuth();
        clearPrivySigner();
        openLogin(navigate, location, location.pathname);
      })
      .finally(() => {
        syncingRef.current = false;
        setPrivySyncPending(false);
      });
  }, [ready, authenticated, walletsReady, wallets, navigate, location]);

  return null;
}
