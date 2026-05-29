import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { HardClaimCard } from '@/components/HardClaimCard';
import { clearAuth, loginPathWithReturn, useAuthState } from '@/lib/auth';
import { clearPrivateKey, loadEncryptedKey, decryptPrivateKey } from '@/lib/crypto';
import { getHardClaimsByAddress, getAssets, getProfileStats } from '@/lib/api';
import type { HardClaimItem, AssetItem, ProfileStats } from '@/lib/types';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';

const REVEAL_TTL = 60;

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

export default function ProfilePage() {
  const navigate = useNavigate();
  const auth = useAuthState();
  const address = auth.address ?? '';
  const hasEncryptedKey = loadEncryptedKey() !== null;

  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [stats, setStats] = useState<ProfileStats | null>(null);

  useEffect(() => {
    if (!address) return;
    getHardClaimsByAddress(address).then(setHardClaims).catch(console.error);
    getAssets().then(setAssets).catch(console.error);
    getProfileStats(address).then(setStats).catch(console.error);
  }, [address]);

  const [showReveal, setShowReveal] = useState(false);
  const [revealPassword, setRevealPassword] = useState('');
  const [decrypting, setDecrypting] = useState(false);
  const [revealError, setRevealError] = useState('');
  const [privateKeyHex, setPrivateKeyHex] = useState('');
  const [countdown, setCountdown] = useState(REVEAL_TTL);

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
    <div className="space-y-4">
      {!auth.authenticated && (
        <Alert>
          <AlertDescription>
            Login is required to manage your profile and private key.
            <Button variant="link" className="px-2" onClick={() => navigate(loginPathWithReturn('/app/profile'))}>
              Go to login
            </Button>
          </AlertDescription>
        </Alert>
      )}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </Button>
        <h1 className="text-xl font-semibold">Profile</h1>
      </div>

      {/* Profile Info */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Your Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Address</Label>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded break-all">
                {address || '—'}
              </code>
              {address && <CopyButton text={address} />}
            </div>
            {stats && stats.profitability && (
              <div className="pt-2">
                <ProfitabilityBadge data={stats.profitability} className="text-sm px-3 py-1" />
              </div>
            )}
          </div>
          
          {stats && (
            <div className="flex gap-6 text-sm pt-2 flex-wrap">
              <div className="flex flex-col">
                <span className="font-semibold text-lg">{stats.followers_count}</span>
                <span className="text-muted-foreground text-xs uppercase tracking-wider">Followers</span>
              </div>
              <div className="flex flex-col">
                <span className="font-semibold text-lg">{stats.following_count}</span>
                <span className="text-muted-foreground text-xs uppercase tracking-wider">Following</span>
              </div>
              {stats.rep != null && (
                <div className="flex flex-col">
                  <span className="font-semibold text-lg font-mono">{stats.rep.toFixed(0)}</span>
                  <span className="text-muted-foreground text-xs uppercase tracking-wider">Rep</span>
                </div>
              )}
              {stats.energy != null && (
                <div className="flex flex-col">
                  <span className="font-semibold text-lg font-mono">
                    {Math.floor(stats.energy)}
                    {stats.energy_cap != null ? `/${stats.energy_cap}` : ''}
                  </span>
                  <span className="text-muted-foreground text-xs uppercase tracking-wider">Energy</span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Private Key */}
      {hasEncryptedKey && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Private Key</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!privateKeyHex && !showReveal && (
              <>
                <p className="text-sm text-muted-foreground">
                  Encrypted with your password. Stored locally only.
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
                    {`${privateKeyHex.slice(0, 8)}…${privateKeyHex.slice(-8)}`}
                  </code>
                  <CopyButton text={privateKeyHex} />
                </div>
                <Button variant="outline" className="w-full" onClick={hidePrivateKey}>
                  Hide
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Hard Claims */}
      <div className="space-y-2 max-w-md mx-auto w-full">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Your Claims
        </h2>
        {hardClaims.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">No claims yet.</p>
        ) : (
          hardClaims.map((claim) => (
            <HardClaimCard key={claim.id} claim={claim} assets={assets} />
          ))
        )}
      </div>

      <div className="max-w-md pt-4 mx-auto w-full">
        <Button variant="destructive" onClick={handleLogout} className="w-full">
          Log out
        </Button>
      </div>
    </div>
  );
}
