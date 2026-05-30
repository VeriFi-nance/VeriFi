import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from '@/components/ui/card';
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
  encryptPrivateKey,
  saveEncryptedKey,
} from '@/lib/crypto';
import { register, getChallenge, login } from '@/lib/api';
import { saveToken, saveAddress } from '@/lib/auth';
import { connectAndAuthenticateMetaMask } from '@/lib/walletAuth';

type Tab = 'create' | 'signin';

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('returnTo');
  const [tab, setTab] = useState<Tab>('create');

  // ── Create wallet state ──────────────────────────────────────────────────
  const [mnemonic, setMnemonic] = useState('');
  const [saved, setSaved] = useState(false);
  const [createPassword, setCreatePassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [creating, setCreating] = useState(false);

  // ── Sign-in state ────────────────────────────────────────────────────────
  const [restoreMethod, setRestoreMethod] = useState<'mnemonic' | 'privatekey'>('mnemonic');
  const [inputMnemonic, setInputMnemonic] = useState('');
  const [inputPrivateKey, setInputPrivateKey] = useState('');
  const [signinPassword, setSigninPassword] = useState('');
  const [signingIn, setSigningIn] = useState(false);

  const [error, setError] = useState('');

  // ── MetaMask state ───────────────────────────────────────────────────────
  const [metamaskLoading, setMetamaskLoading] = useState(false);

  function navigateAfterAuth() {
    navigate(returnTo || '/feed');
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function resetTab(t: Tab) {
    setTab(t);
    setError('');
    setMnemonic('');
    setSaved(false);
    setCreatePassword('');
    setConfirmPassword('');
    setRestoreMethod('mnemonic');
    setInputMnemonic('');
    setInputPrivateKey('');
    setSigninPassword('');
  }

  function handleGenerate() {
    setMnemonic(generateMnemonic());
    setSaved(false);
    setCreatePassword('');
    setConfirmPassword('');
    setError('');
  }

  // ── Create wallet ────────────────────────────────────────────────────────
  const passwordMismatch =
    confirmPassword.length > 0 && createPassword !== confirmPassword;
  const createReady =
    mnemonic &&
    saved &&
    createPassword.length >= 8 &&
    createPassword === confirmPassword;

  async function handleCreate() {
    setError('');
    setCreating(true);
    try {
      const { privateKey, address } = deriveKeyPair(mnemonic);
      const encrypted = await encryptPrivateKey(privateKey, createPassword);
      const { access } = await register(address);
      saveEncryptedKey(encrypted);
      saveAddress(address);
      saveToken(access);
      navigateAfterAuth();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setCreating(false);
    }
  }

  // ── Sign in ──────────────────────────────────────────────────────────────
  async function handleSignIn() {
    setError('');
    if (signinPassword.length < 8) {
      setError('Password must be at least 8 characters.');
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
      const { access } = await login(address, signature, nonce);
      const encrypted = await encryptPrivateKey(privateKey, signinPassword);
      saveEncryptedKey(encrypted);
      saveAddress(address);
      saveToken(access);
      navigateAfterAuth();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setSigningIn(false);
    }
  }

  // ── MetaMask ─────────────────────────────────────────────────────────────
  async function handleMetaMask() {
    setMetamaskLoading(true);
    setError('');
    try {
      await connectAndAuthenticateMetaMask();
      navigateAfterAuth();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'MetaMask connection failed');
    } finally {
      setMetamaskLoading(false);
    }
  }

  const words = mnemonic ? mnemonic.split(' ') : [];

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <BrandLogo size="lg" link={false} className="mx-auto justify-center mb-2" />
          <CardDescription>
            Your 12-word passphrase is your key. Set a password to encrypt it
            locally on this device.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Tab switcher */}
          <div className="flex rounded-lg border overflow-hidden">
            {(['create', 'signin'] as Tab[]).map((t) => (
              <button
                key={t}
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

          {/* ── Create wallet ─────────────────────────────────────────── */}
          {tab === 'create' && (
            <div className="space-y-4">
              {!mnemonic ? (
                <Button className="w-full" onClick={handleGenerate}>
                  Generate Passphrase
                </Button>
              ) : (
                <>
                  <Alert>
                    <AlertDescription className="text-amber-600 font-medium">
                      Write down these 12 words and store them safely. You
                      cannot recover your account without them.
                    </AlertDescription>
                  </Alert>

                  {/* Mnemonic grid */}
                  <div className="grid grid-cols-3 gap-2">
                    {words.map((word, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <span className="text-xs text-muted-foreground w-4">
                          {i + 1}.
                        </span>
                        <Badge
                          variant="secondary"
                          className="font-mono text-xs"
                        >
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

                  {/* Password fields — shown after checkbox */}
                  {saved && (
                    <div className="space-y-3 border rounded-lg p-3">
                      <p className="text-sm text-muted-foreground">
                        Set a password to encrypt your private key on this
                        device (min. 8 characters).
                      </p>
                      <div className="space-y-1">
                        <Label htmlFor="create-pw">Password</Label>
                        <Input
                          id="create-pw"
                          type="password"
                          placeholder="At least 8 characters"
                          value={createPassword}
                          onChange={(e) => setCreatePassword(e.target.value)}
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
                          className={
                            passwordMismatch ? 'border-destructive' : ''
                          }
                        />
                        {passwordMismatch && (
                          <p className="text-xs text-destructive">
                            Passwords do not match
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={handleGenerate}
                    >
                      Regenerate
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
            </div>
          )}

          {/* ── Sign in ───────────────────────────────────────────────── */}
          {tab === 'signin' && (
            <div className="space-y-4">
              {/* Restore method toggle */}
              <div className="flex rounded-lg border overflow-hidden text-sm">
                {(['mnemonic', 'privatekey'] as const).map((m) => (
                  <button
                    key={m}
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
                  onChange={(e) => setSigninPassword(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  You will need this password to decrypt your private key later.
                </p>
              </div>
              <Button
                className="w-full"
                disabled={signingIn}
                onClick={handleSignIn}
              >
                {signingIn ? 'Restoring…' : 'Restore Account'}
              </Button>
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* MetaMask */}
          <div className="relative flex items-center gap-2">
            <div className="flex-1 border-t" />
            <span className="text-xs text-muted-foreground px-1">or</span>
            <div className="flex-1 border-t" />
          </div>

          <Button
            variant="outline"
            className="w-full"
            disabled={metamaskLoading}
            onClick={handleMetaMask}
          >
            {metamaskLoading ? 'Connecting…' : 'Connect with MetaMask'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
