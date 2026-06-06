import { useEffect } from 'react';
import { useLoginWithOAuth, usePrivy } from '@privy-io/react-auth';
import { Button } from '@/components/ui/button';
import { GoogleIcon } from '@/components/BrandIcons';
import { useAuthState } from '@/lib/auth';
import { clearPrivySyncState, usePrivySyncState } from '@/lib/privySyncState';

interface GoogleLoginButtonProps {
  disabled?: boolean;
  onError: (message: string) => void;
}

export function GoogleLoginButton({ disabled, onError }: GoogleLoginButtonProps) {
  const { ready, authenticated: privyAuthed } = usePrivy();
  const { authenticated: verifiAuthed } = useAuthState();
  const { pending: syncPending, error: syncError } = usePrivySyncState();
  const { initOAuth, state: oauthState } = useLoginWithOAuth();

  const oauthLoading = oauthState.status === 'loading';
  const finishingLogin = privyAuthed && !verifiAuthed;
  const loading = oauthLoading || syncPending || finishingLogin;

  useEffect(() => {
    if (syncError) {
      onError(syncError);
    }
  }, [syncError, onError]);

  async function handleGoogle() {
    onError('');
    clearPrivySyncState();
    try {
      if (!ready) {
        throw new Error('Sign-in is still loading. Please try again.');
      }
      await initOAuth({ provider: 'google' });
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Google sign-in failed');
    }
  }

  return (
    <Button
      variant="outline"
      className="w-full"
      disabled={disabled || loading || !ready}
      onClick={handleGoogle}
    >
      <GoogleIcon className="size-4" />
      {loading ? 'Signing in…' : 'Continue with Google'}
    </Button>
  );
}
