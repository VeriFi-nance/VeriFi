import { useState } from 'react';
import { BrandLogo } from '@/components/BrandLogo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  deriveKeyPair,
  privateKeyToKeyPair,
  signMessage,
} from '@/lib/crypto';
import { encryptPrivateKey, saveEncryptedKey } from '@/lib/keystore';
import { getChallenge, login } from '@/lib/api';
import { FieldError } from '@/components/ui/field-error';
import { saveAuthSession, setAuthMethod } from '@/lib/auth';
import { connectAndAuthenticateMetaMask } from '@/lib/walletAuth';
import { isPrivyConfigured } from '@/lib/privyAuth';
import { GoogleLoginButton } from '@/components/GoogleLoginButton';
import { GoogleIcon, MetaMaskIcon } from '@/components/BrandIcons';
import { RegistrationWizard } from '@/components/registration/RegistrationWizard';
import { loadRegDraft } from '@/lib/regWizard';

type Tab = 'create' | 'signin';

interface LoginFormProps {
  onSuccess: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [tab, setTab] = useState<Tab>('create');
  // Auto-resume the native wizard if a draft was left behind by a reload.
  const [createStarted, setCreateStarted] = useState(() => loadRegDraft()?.flow === 'native');
  const [restoreMethod, setRestoreMethod] = useState<'mnemonic' | 'privatekey'>('mnemonic');
  const [inputMnemonic, setInputMnemonic] = useState('');
  const [inputPrivateKey, setInputPrivateKey] = useState('');
  const [signinPassword, setSigninPassword] = useState('');
  const [signinPwError, setSigninPwError] = useState('');
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState('');
  const [metamaskLoading, setMetamaskLoading] = useState(false);
  const privyEnabled = isPrivyConfigured();

  function resetTab(t: Tab) {
    setTab(t);
    setError('');
    setRestoreMethod('mnemonic');
    setInputMnemonic('');
    setInputPrivateKey('');
    setSigninPassword('');
    setSigninPwError('');
  }

  async function handleSignIn() {
    setError('');
    setSigninPwError('');
    if (signinPassword.length < 8) {
      setSigninPwError('Password must be at least 8 characters.');
      return;
    }
    setSigningIn(true);
    try {
      const { privateKey, address } =
        restoreMethod === 'mnemonic'
          ? deriveKeyPair(inputMnemonic.trim())
          : privateKeyToKeyPair(inputPrivateKey.trim());
      const { nonce } = await getChallenge(address);
      const signature = await signMessage(privateKey, nonce);
      const { access, username, avatar_url } = await login(address, signature, nonce);
      const encrypted = await encryptPrivateKey(privateKey, signinPassword);
      saveEncryptedKey(encrypted);
      saveAuthSession(address, username, access, avatar_url);
      setAuthMethod('native');
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setSigningIn(false);
    }
  }

  async function handleMetaMask() {
    setMetamaskLoading(true);
    setError('');
    try {
      await connectAndAuthenticateMetaMask();
      setAuthMethod('metamask');
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'MetaMask connection failed');
    } finally {
      setMetamaskLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="space-y-2 text-center">
        <BrandLogo size="lg" link={false} className="mx-auto justify-center mb-2" />
        <p className="text-sm text-muted-foreground">
          Your 12-word passphrase is your key. Set a password to encrypt it locally on this device.
        </p>
      </div>

      <div className="space-y-3">
        {privyEnabled ? (
          <GoogleLoginButton disabled={metamaskLoading} onError={setError} />
        ) : (
          <Button
            variant="outline"
            className="w-full"
            disabled
            title="Set VITE_PRIVY_APP_ID to enable Google sign-in"
          >
            <GoogleIcon className="size-4" />
            Continue with Google
          </Button>
        )}

        <Button
          variant="outline"
          className="w-full"
          disabled={metamaskLoading}
          onClick={handleMetaMask}
        >
          <MetaMaskIcon className="size-4" />
          {metamaskLoading ? 'Connecting…' : 'Connect with MetaMask'}
        </Button>
      </div>

      <div className="relative flex items-center gap-2">
        <div className="flex-1 border-t" />
        <span className="text-xs text-muted-foreground px-1">or</span>
        <div className="flex-1 border-t" />
      </div>

      <div className="space-y-4">
        <div className="flex rounded-lg border overflow-hidden">
          {(['create', 'signin'] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                tab === t
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:bg-muted'
              }`}
              onClick={() => resetTab(t)}
            >
              {t === 'create' ? 'Create Account' : 'Restore Account'}
            </button>
          ))}
        </div>

        {tab === 'create' && (
          createStarted ? (
            <RegistrationWizard
              flow="native"
              authMethod="native"
              onComplete={onSuccess}
              onCancel={() => setCreateStarted(false)}
            />
          ) : (
            <Button className="w-full" onClick={() => setCreateStarted(true)}>
              Create a new account
            </Button>
          )
        )}

        {tab === 'signin' && (
          <div className="space-y-4">
            <div className="flex rounded-lg border overflow-hidden text-sm">
              {(['mnemonic', 'privatekey'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`flex-1 py-1.5 font-medium transition-colors ${
                    restoreMethod === m
                      ? 'bg-secondary text-secondary-foreground'
                      : 'bg-background text-muted-foreground hover:bg-muted'
                  }`}
                  onClick={() => {
                    setRestoreMethod(m);
                    setError('');
                  }}
                >
                  {m === 'mnemonic' ? '12-word passphrase' : 'Private key'}
                </button>
              ))}
            </div>

            {restoreMethod === 'mnemonic' ? (
              <div className="space-y-1">
                <Label htmlFor="mnemonic">Your 12-word passphrase</Label>
                <Textarea
                  id="mnemonic"
                  placeholder="word1 word2 word3 … word12"
                  rows={3}
                  value={inputMnemonic}
                  onChange={(e) => setInputMnemonic(e.target.value)}
                  className="font-mono text-sm resize-none"
                />
              </div>
            ) : (
              <div className="space-y-1">
                <Label htmlFor="privkey">Private key (hex)</Label>
                <Input
                  id="privkey"
                  placeholder="0x… or 64 hex characters"
                  value={inputPrivateKey}
                  onChange={(e) => setInputPrivateKey(e.target.value)}
                  className="font-mono text-sm"
                />
              </div>
            )}

            <div className="space-y-1">
              <Label htmlFor="signin-pw">Encryption password</Label>
              <Input
                id="signin-pw"
                type="password"
                placeholder="Used to encrypt your key on this device"
                value={signinPassword}
                onChange={(e) => { setSigninPassword(e.target.value); if (signinPwError) setSigninPwError(''); }}
                aria-invalid={!!signinPwError}
              />
              <FieldError>{signinPwError}</FieldError>
              <p className="text-xs text-muted-foreground">
                You will need this password to decrypt your private key later.
              </p>
            </div>
            <Button className="w-full" disabled={signingIn} onClick={handleSignIn}>
              {signingIn ? 'Restoring…' : 'Restore Account'}
            </Button>
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}
