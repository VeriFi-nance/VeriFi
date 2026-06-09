import { useState } from 'react';
import { BrandLogo } from '@/components/BrandLogo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  generateMnemonic,
  deriveKeyPair,
  privateKeyToKeyPair,
  signMessage,
} from '@/lib/crypto';
import { encryptPrivateKey, saveEncryptedKey } from '@/lib/keystore';
import { register, getChallenge, login } from '@/lib/api';
import { getFieldError, getMessage } from '@/lib/errors';
import { FieldError } from '@/components/ui/field-error';
import { saveAuthSession, setAuthMethod } from '@/lib/auth';
import { connectAndAuthenticateMetaMask } from '@/lib/walletAuth';
import { isPrivyConfigured } from '@/lib/privyAuth';
import { GoogleLoginButton } from '@/components/GoogleLoginButton';
import { GoogleIcon, MetaMaskIcon } from '@/components/BrandIcons';

type Tab = 'create' | 'signin';

interface LoginFormProps {
  onSuccess: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [tab, setTab] = useState<Tab>('create');
  const [mnemonic, setMnemonic] = useState('');
  const [createStep, setCreateStep] = useState(0); // 0 passphrase, 1 password, 2 username
  const [saved, setSaved] = useState(false);
  const [createPassword, setCreatePassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [createUsername, setCreateUsername] = useState('');
  const [usernameError, setUsernameError] = useState('');
  const [creating, setCreating] = useState(false);
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
    setUsernameError('');
    setMnemonic('');
    setCreateStep(0);
    setSaved(false);
    setCreateUsername('');
    setCreatePassword('');
    setConfirmPassword('');
    setRestoreMethod('mnemonic');
    setInputMnemonic('');
    setInputPrivateKey('');
    setSigninPassword('');
    setSigninPwError('');
  }

  function handleGenerate() {
    setMnemonic(generateMnemonic());
    setCreateStep(0);
    setSaved(false);
    setCreateUsername('');
    setCreatePassword('');
    setConfirmPassword('');
    setError('');
    setUsernameError('');
  }

  const passwordMismatch =
    confirmPassword.length > 0 && createPassword !== confirmPassword;
  const passwordReady =
    createPassword.length >= 8 && createPassword === confirmPassword;
  const usernameReady = createUsername.trim().length >= 3;
  const createReady = mnemonic && saved && usernameReady && passwordReady;

  async function handleCreate() {
    setError('');
    setUsernameError('');
    setCreating(true);
    try {
      const { privateKey, address } = deriveKeyPair(mnemonic);
      const encrypted = await encryptPrivateKey(privateKey, createPassword);
      const { access, username, avatar_url } = await register(address, createUsername.trim());
      saveEncryptedKey(encrypted);
      saveAuthSession(address, username, access, avatar_url);
      setAuthMethod('native');
      onSuccess();
    } catch (e) {
      // Field-level errors (e.g. username taken) pin under the input; the rest
      // fall back to the generic form alert.
      const fieldErr = getFieldError(e, 'username');
      if (fieldErr) setUsernameError(fieldErr);
      else setError(getMessage(e));
    } finally {
      setCreating(false);
    }
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

  const words = mnemonic ? mnemonic.split(' ') : [];

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
          <div className="space-y-4">
            {!mnemonic ? (
              <Button className="w-full" onClick={handleGenerate}>
                Generate Passphrase
              </Button>
            ) : (
              <>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground text-center">
                  {createStep === 0
                    ? 'Step 1 of 3 · Passphrase'
                    : createStep === 1
                      ? 'Step 2 of 3 · Password'
                      : 'Step 3 of 3 · Username'}
                </p>

                {/* ── Step 1: passphrase ─────────────────────── */}
                {createStep === 0 && (
                  <>
                    <Alert>
                      <AlertDescription className="text-amber-600 font-medium">
                        Write down these 12 words and store them safely. You cannot recover your account
                        without them.
                      </AlertDescription>
                    </Alert>

                    <div className="grid grid-cols-3 gap-2">
                      {words.map((word, i) => (
                        <div key={i} className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground w-4">{i + 1}.</span>
                          <Badge variant="secondary" className="font-mono text-xs">
                            {word}
                          </Badge>
                        </div>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="saved"
                        checked={saved}
                        onCheckedChange={(v) => setSaved(!!v)}
                      />
                      <Label htmlFor="saved" className="cursor-pointer">
                        I have saved my 12-word passphrase
                      </Label>
                    </div>

                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={handleGenerate}>
                        Regenerate
                      </Button>
                      <Button
                        className="flex-1"
                        disabled={!saved}
                        onClick={() => setCreateStep(1)}
                      >
                        Next
                      </Button>
                    </div>
                  </>
                )}

                {/* ── Step 2: password ───────────────────────── */}
                {createStep === 1 && (
                  <>
                    <p className="text-sm text-muted-foreground">
                      Set a password to encrypt your private key locally on this device.
                    </p>
                    <div className="space-y-1">
                      <Label htmlFor="create-pw">Password</Label>
                      <Input
                        id="create-pw"
                        type="password"
                        placeholder="At least 8 characters"
                        value={createPassword}
                        onChange={(e) => setCreatePassword(e.target.value)}
                        autoFocus
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="confirm-pw">Confirm password</Label>
                      <Input
                        id="confirm-pw"
                        type="password"
                        placeholder="Repeat password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        aria-invalid={passwordMismatch}
                      />
                      <FieldError>{passwordMismatch ? 'Passwords do not match' : ''}</FieldError>
                    </div>

                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => setCreateStep(0)}>
                        Back
                      </Button>
                      <Button
                        className="flex-1"
                        disabled={!passwordReady}
                        onClick={() => setCreateStep(2)}
                      >
                        Next
                      </Button>
                    </div>
                  </>
                )}

                {/* ── Step 3: username ───────────────────────── */}
                {createStep === 2 && (
                  <>
                    <p className="text-sm text-muted-foreground">
                      Pick a unique username. This is how others will see you.
                    </p>
                    <div className="space-y-1">
                      <Label htmlFor="create-username">Username</Label>
                      <Input
                        id="create-username"
                        type="text"
                        placeholder="e.g. Satoshi"
                        value={createUsername}
                        onChange={(e) => {
                          setCreateUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, ''));
                          if (usernameError) setUsernameError('');
                        }}
                        aria-invalid={!!usernameError}
                        autoFocus
                      />
                      <FieldError>{usernameError}</FieldError>
                    </div>

                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => setCreateStep(1)}>
                        Back
                      </Button>
                      <Button
                        className="flex-1"
                        disabled={!createReady || creating}
                        onClick={handleCreate}
                      >
                        {creating ? 'Creating…' : 'Create Account'}
                      </Button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
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
