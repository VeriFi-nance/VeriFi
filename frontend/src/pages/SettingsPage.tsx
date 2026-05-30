import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Copy, Check, Sun, Moon, LogOut, KeyRound } from 'lucide-react';
import { clearAuth, loadAddress } from '@/lib/auth';
import { clearPrivateKey } from '@/lib/crypto';
import { loadTheme, toggleTheme, type Theme } from '@/lib/theme';
import { useWalletReveal } from '@/lib/useWalletReveal';

function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <Button variant="outline" size="sm" onClick={copy} className="shrink-0 gap-1.5">
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? 'Copied' : label}
    </Button>
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const address = loadAddress() ?? '';
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const reveal = useWalletReveal();
  const [showReveal, setShowReveal] = useState(false);
  const [password, setPassword] = useState('');

  function handleThemeToggle() {
    const next = toggleTheme();
    setTheme(next);
  }

  function handleLogout() {
    clearAuth();
    clearPrivateKey();
    navigate('/login');
  }

  async function handleDecrypt() {
    await reveal.reveal(password);
    setPassword('');
  }

  function cancelReveal() {
    setShowReveal(false);
    setPassword('');
    reveal.hide();
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      {/* Wallet address */}
      <Card className="p-5 space-y-4">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold">Wallet address</h2>
          <p className="text-xs text-muted-foreground">
            Your secp256k1 Ethereum-compatible address.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded break-all">
            {address || '—'}
          </code>
          {address && <CopyButton text={address} />}
        </div>
      </Card>

      {/* Private key reveal */}
      {reveal.hasEncryptedKey && (
        <Card className="p-5 space-y-4">
          <div className="space-y-1">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <KeyRound className="size-4" />
              Private key
            </h2>
            <p className="text-xs text-muted-foreground">
              Encrypted with your password, stored locally. Reveal expires after
              60 seconds.
            </p>
          </div>

          {!reveal.privateKeyHex && !showReveal && (
            <Button variant="outline" onClick={() => setShowReveal(true)}>
              Reveal private key
            </Button>
          )}

          {showReveal && !reveal.privateKeyHex && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="reveal-pw">Password</Label>
                <Input
                  id="reveal-pw"
                  type="password"
                  placeholder="Encryption password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleDecrypt()}
                  autoFocus
                />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={cancelReveal}>
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  disabled={reveal.decrypting || password.length === 0}
                  onClick={handleDecrypt}
                >
                  {reveal.decrypting ? 'Decrypting…' : 'Decrypt'}
                </Button>
              </div>
              {reveal.error && (
                <Alert variant="destructive">
                  <AlertDescription>{reveal.error}</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {reveal.privateKeyHex && (
            <div className="space-y-3">
              <Alert>
                <AlertDescription className="text-danger font-medium num">
                  Keep this secret. Auto-hides in {reveal.secondsLeft}s.
                </AlertDescription>
              </Alert>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded break-all">
                  {`${reveal.privateKeyHex.slice(0, 8)}…${reveal.privateKeyHex.slice(-8)}`}
                </code>
                <CopyButton text={reveal.privateKeyHex} />
              </div>
              <Button variant="outline" className="w-full" onClick={cancelReveal}>
                Hide
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Appearance */}
      <Card className="p-5 flex items-center justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <h2 className="text-sm font-semibold">Appearance</h2>
          <p className="text-xs text-muted-foreground">
            Switch between light and dark theme.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleThemeToggle} className="gap-2 shrink-0">
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          {theme === 'dark' ? 'Light' : 'Dark'}
        </Button>
      </Card>

      {/* Session */}
      <Card className="p-5 flex items-center justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <h2 className="text-sm font-semibold">Disconnect</h2>
          <p className="text-xs text-muted-foreground">
            Sign out and clear local wallet from this device.
          </p>
        </div>
        <Button variant="destructive" size="sm" onClick={handleLogout} className="gap-2 shrink-0">
          <LogOut className="size-4" />
          Disconnect
        </Button>
      </Card>
    </div>
  );
}
