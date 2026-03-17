import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { clearAuth, loadAddress } from '@/lib/auth';
import { clearPrivateKey, loadEncryptedKey, decryptPrivateKey } from '@/lib/crypto';

const REVEAL_TTL = 60; // seconds before private key auto-hides

function truncate(hex: string) {
  return `${hex.slice(0, 8)}…${hex.slice(-8)}`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <Button variant="outline" size="sm" onClick={copy} className="shrink-0">
      {copied ? 'Copied!' : 'Copy'}
    </Button>
  );
}

export default function AppPage() {
  const navigate = useNavigate();
  const address = loadAddress() ?? '';
  const hasEncryptedKey = loadEncryptedKey() !== null;

  // ── Private key reveal state ─────────────────────────────────────────────
  const [showReveal, setShowReveal] = useState(false);
  const [revealPassword, setRevealPassword] = useState('');
  const [decrypting, setDecrypting] = useState(false);
  const [revealError, setRevealError] = useState('');
  const [privateKeyHex, setPrivateKeyHex] = useState('');
  const [countdown, setCountdown] = useState(REVEAL_TTL);

  // Auto-clear private key after TTL
  useEffect(() => {
    if (!privateKeyHex) return;
    setCountdown(REVEAL_TTL);
    const interval = setInterval(
      () => setCountdown((c) => (c > 1 ? c - 1 : 0)),
      1000
    );
    const timer = setTimeout(() => {
      setPrivateKeyHex('');
      setShowReveal(false);
    }, REVEAL_TTL * 1000);
    return () => {
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, [privateKeyHex]);

  async function handleDecrypt() {
    setRevealError('');
    const encrypted = loadEncryptedKey();
    if (!encrypted) {
      setRevealError('No encrypted key found in storage.');
      return;
    }
    setDecrypting(true);
    try {
      const key = await decryptPrivateKey(encrypted, revealPassword);
      const hex = Array.from(key)
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
      setPrivateKeyHex(hex);
      setRevealPassword('');
    } catch (e) {
      setRevealError(e instanceof Error ? e.message : 'Decryption failed');
    } finally {
      setDecrypting(false);
    }
  }

  function hidePrivateKey() {
    setPrivateKeyHex('');
    setShowReveal(false);
    setRevealPassword('');
    setRevealError('');
  }

  function handleLogout() {
    clearAuth();
    clearPrivateKey();
    navigate('/login');
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 bg-background p-4">
      <h1 className="text-3xl font-bold">Welcome to VeriFi</h1>

      {/* ── Public key card ───────────────────────────────────────────────── */}
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle className="text-base">Your Address</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded break-all">
              {address || '—'}
            </code>
            {address && <CopyButton text={address} />}
          </div>
          <p className="text-xs text-muted-foreground">
            Your Ethereum-compatible address (secp256k1, keccak256).
          </p>
        </CardContent>
      </Card>

      {/* ── Private key card (hidden for MetaMask users) ─────────────────── */}
      {hasEncryptedKey && <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle className="text-base">Private Key</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!privateKeyHex && !showReveal && (
            <>
              <p className="text-sm text-muted-foreground">
                Your private key is encrypted with your password and stored
                locally. Enter your password to reveal it.
              </p>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setShowReveal(true)}
              >
                Reveal Private Key
              </Button>
            </>
          )}

          {showReveal && !privateKeyHex && (
            <div className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="reveal-pw">Password</Label>
                <Input
                  id="reveal-pw"
                  type="password"
                  placeholder="Enter your encryption password"
                  value={revealPassword}
                  onChange={(e) => setRevealPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleDecrypt()}
                  autoFocus
                />
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => {
                    setShowReveal(false);
                    setRevealPassword('');
                    setRevealError('');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  disabled={decrypting || revealPassword.length === 0}
                  onClick={handleDecrypt}
                >
                  {decrypting ? 'Decrypting…' : 'Decrypt'}
                </Button>
              </div>
              {revealError && (
                <Alert variant="destructive">
                  <AlertDescription>{revealError}</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {privateKeyHex && (
            <div className="space-y-3">
              <Alert>
                <AlertDescription className="text-amber-600 font-medium">
                  Keep this secret. Auto-hides in {countdown}s.
                </AlertDescription>
              </Alert>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded break-all">
                  {truncate(privateKeyHex)}
                </code>
                <CopyButton text={privateKeyHex} />
              </div>
              <Button
                variant="outline"
                className="w-full"
                onClick={hidePrivateKey}
              >
                Hide
              </Button>
            </div>
          )}
        </CardContent>
      </Card>}

      <Button variant="ghost" onClick={handleLogout}>
        Log out
      </Button>
    </div>
  );
}
