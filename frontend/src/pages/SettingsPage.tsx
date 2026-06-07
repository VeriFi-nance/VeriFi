import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Copy, Check, Sun, Moon, LogOut, KeyRound, ImagePlus } from 'lucide-react';
import { clearAuth, useAuthState, saveUsername, saveAvatar } from '@/lib/auth';
import { updateProfile, updateUsername, getProfileStats } from '@/lib/api';
import { FieldError } from '@/components/ui/field-error';
import { getFieldError, getMessage } from '@/lib/errors';
import { UserAvatar } from '@/components/UserAvatar';
import { clearPrivateKey } from '@/lib/keystore';
import { loadTheme, toggleTheme, type Theme } from '@/lib/theme';
import { useWalletReveal } from '@/lib/useWalletReveal';
import { PageContent } from '@/components/PageContent';
import { cn } from '@/lib/utils';

const sectionClass = 'p-5 flex flex-col gap-4';
const rowClass = 'p-5 flex items-center justify-between gap-4';
const titleClass = 'text-sm font-semibold leading-none';
const descriptionClass = 'text-sm text-muted-foreground leading-relaxed';

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

function SettingsSection({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={cn(sectionClass, className)}>{children}</section>;
}

function SettingsRow({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className={rowClass}>
      <h2 className={titleClass}>{title}</h2>
      {children}
    </section>
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const { address, username, avatar } = useAuthState();
  const [theme, setTheme] = useState<Theme>(loadTheme);

  const [avatarUrl, setAvatarUrl] = useState<string | null>(avatar);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState('');
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const reveal = useWalletReveal();
  const [showReveal, setShowReveal] = useState(false);
  const [password, setPassword] = useState('');

  const [editUsername, setEditUsername] = useState(username ?? '');
  const [isEditingUsername, setIsEditingUsername] = useState(false);
  const [savingUsername, setSavingUsername] = useState(false);
  const [usernameError, setUsernameError] = useState('');

  // Hydrate the current avatar from the server (covers logins on a fresh device
  // where the avatar isn't cached locally yet).
  useEffect(() => {
    if (!address) return;
    getProfileStats(address)
      .then((stats) => {
        setAvatarUrl(stats.avatar_url ?? null);
        saveAvatar(stats.avatar_url ?? null);
      })
      .catch(() => {});
  }, [address]);

  // Revoke the object URL for the local preview on change/unmount.
  useEffect(() => {
    return () => {
      if (avatarPreview) URL.revokeObjectURL(avatarPreview);
    };
  }, [avatarPreview]);

  async function handlePickAvatar(file: File | null) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setAvatarError('Please choose an image file.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setAvatarError('Image must be 10 MB or smaller.');
      return;
    }
    setAvatarError('');
    const preview = URL.createObjectURL(file);
    setAvatarPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return preview;
    });
    setSavingAvatar(true);
    try {
      const res = await updateProfile({ avatar: file });
      setAvatarUrl(res.avatar_url);
      saveAvatar(res.avatar_url);
    } catch (e) {
      setAvatarError(e instanceof Error ? e.message : 'Failed to update picture.');
    } finally {
      setSavingAvatar(false);
      setAvatarPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      if (avatarInputRef.current) avatarInputRef.current.value = '';
    }
  }

  async function handleSaveUsername() {
    setUsernameError('');
    if (!editUsername.trim() || editUsername.trim().length < 3) {
      setUsernameError('Username must be at least 3 characters.');
      return;
    }
    setSavingUsername(true);
    try {
      const res = await updateUsername(editUsername.trim());
      saveUsername(res.username);
      setIsEditingUsername(false);
    } catch (e) {
      setUsernameError(getFieldError(e, 'username') ?? getMessage(e, 'Failed to update username'));
    } finally {
      setSavingUsername(false);
    }
  }

  function handleThemeToggle() {
    const next = toggleTheme();
    setTheme(next);
  }

  function handleLogout() {
    clearAuth();
    clearPrivateKey();
    navigate('/feed');
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
    <PageContent>
      <Card className="divide-y divide-border">
        <SettingsSection>
          <div className="space-y-1.5">
            <h2 className={titleClass}>Wallet address</h2>
            <p className={descriptionClass}>
              Your secp256k1 Ethereum-compatible address.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded-md break-all">
              {address || '—'}
            </code>
            {address && <CopyButton text={address} />}
          </div>
        </SettingsSection>

        <SettingsSection>
          <div className="space-y-1.5">
            <h2 className={titleClass}>Profile picture</h2>
            <p className={descriptionClass}>
              Shown next to your posts and on your profile. Auto-resized; max 10 MB.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <UserAvatar address={address || ''} src={avatarPreview || avatarUrl} size="lg" />
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => handlePickAvatar(e.target.files?.[0] ?? null)}
            />
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={savingAvatar}
              onClick={() => avatarInputRef.current?.click()}
            >
              <ImagePlus className="size-3.5" />
              {savingAvatar ? 'Uploading…' : avatarUrl ? 'Change' : 'Upload'}
            </Button>
          </div>
          {avatarError && <p className="text-xs text-destructive">{avatarError}</p>}
        </SettingsSection>

        <SettingsSection>
          <div className="space-y-1.5">
            <h2 className={titleClass}>Username</h2>
            <p className={descriptionClass}>
              Your public display name.
            </p>
          </div>
          {isEditingUsername ? (
            <div className="space-y-3">
              <Input
                value={editUsername}
                onChange={(e) => { setEditUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, '')); if (usernameError) setUsernameError(''); }}
                placeholder="New username"
                aria-invalid={!!usernameError}
              />
              <FieldError>{usernameError}</FieldError>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => { setIsEditingUsername(false); setEditUsername(username ?? ''); }}>
                  Cancel
                </Button>
                <Button size="sm" disabled={savingUsername} onClick={handleSaveUsername}>
                  {savingUsername ? 'Saving…' : 'Save'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <code className="flex-1 text-sm font-mono bg-muted px-3 py-2 rounded-md break-all">
                @{username || '—'}
              </code>
              <Button variant="outline" size="sm" onClick={() => setIsEditingUsername(true)}>
                Edit
              </Button>
            </div>
          )}
        </SettingsSection>

        {reveal.hasEncryptedKey && (
          <SettingsSection>
            <div className="space-y-1.5">
              <h2 className={cn(titleClass, 'flex items-center gap-2')}>
                <KeyRound className="size-4" />
                Private key
              </h2>
              <p className={descriptionClass}>
                Encrypted with your password, stored locally. Reveal expires after 60 seconds.
              </p>
            </div>

            {!reveal.privateKeyHex && !showReveal && (
              <Button variant="outline" onClick={() => setShowReveal(true)}>
                Reveal private key
              </Button>
            )}

            {showReveal && !reveal.privateKeyHex && (
              <div className="space-y-4">
                <div className="space-y-2">
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
                <div className="flex gap-3">
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
              <div className="space-y-4">
                <Alert>
                  <AlertDescription className="text-danger font-medium num">
                    Keep this secret. Auto-hides in {reveal.secondsLeft}s.
                  </AlertDescription>
                </Alert>
                <div className="flex items-center gap-3">
                  <code className="flex-1 text-xs font-mono bg-muted px-3 py-2 rounded-md break-all">
                    {`${reveal.privateKeyHex.slice(0, 8)}…${reveal.privateKeyHex.slice(-8)}`}
                  </code>
                  <CopyButton text={reveal.privateKeyHex} />
                </div>
                <Button variant="outline" className="w-full" onClick={cancelReveal}>
                  Hide
                </Button>
              </div>
            )}
          </SettingsSection>
        )}

        <SettingsRow title="Appearance">
          <Button variant="outline" size="sm" onClick={handleThemeToggle} className="gap-2 shrink-0">
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {theme === 'dark' ? 'Light' : 'Dark'}
          </Button>
        </SettingsRow>

        <SettingsRow title="Disconnect">
          <Button variant="destructive" size="sm" onClick={handleLogout} className="gap-2 shrink-0">
            <LogOut className="size-4" />
            Disconnect
          </Button>
        </SettingsRow>
      </Card>
    </PageContent>
  );
}
