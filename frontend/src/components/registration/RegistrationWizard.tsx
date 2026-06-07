import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { FieldError } from '@/components/ui/field-error';
import { generateMnemonic, deriveKeyPair } from '@/lib/crypto';
import { encryptPrivateKey, saveEncryptedKey, type EncryptedKey } from '@/lib/keystore';
import { register, otpStart, otpCheck } from '@/lib/api';
import { saveAuthSession, setAuthMethod, type AuthMethod } from '@/lib/auth';
import { getMessage, getFieldError } from '@/lib/errors';
import {
  loadRegDraft, saveRegDraft, clearRegDraft, type RegFlow, type RegWizardDraft,
} from '@/lib/regWizard';

// Step names per flow. Native derives a key locally first; social already has an
// address (from MetaMask / Privy) so it only needs username + phone.
const STEPS: Record<RegFlow, string[]> = {
  native: ['mnemonic', 'password', 'username', 'phone'],
  social: ['username', 'phone'],
};

interface Props {
  flow: RegFlow;
  authMethod: AuthMethod;
  /** Social flow: the already-known wallet address. */
  address?: string;
  onComplete: () => void;
  onCancel: () => void;
}

export function RegistrationWizard({ flow, authMethod, address: initialAddress, onComplete, onCancel }: Props) {
  const steps = STEPS[flow];

  // Hydrate once from any persisted draft for the same flow. Secrets (mnemonic,
  // password) are never persisted, so a native draft is only resumable once it
  // reached the username step (encryptedKeyDraft + address present).
  const hydrated = useMemo(() => {
    const d = loadRegDraft();
    if (!d || d.flow !== flow) return null;
    if (flow === 'native' && (!d.encryptedKeyDraft || !d.address)) return null;
    return d;
  }, [flow]);

  // Whether we discarded a native draft that hadn't reached a resumable point.
  const regenerated = flow === 'native' && loadRegDraft()?.flow === 'native' && !hydrated;

  const [step, setStep] = useState(() => hydrated?.step ?? 0);
  const [mnemonic, setMnemonic] = useState(() => (flow === 'native' && !hydrated ? generateMnemonic() : ''));
  const [savedPhrase, setSavedPhrase] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [username, setUsername] = useState(() => hydrated?.username ?? '');
  const [address, setAddress] = useState(() => hydrated?.address ?? initialAddress ?? '');
  const [encryptedKeyDraft, setEncryptedKeyDraft] = useState<EncryptedKey | undefined>(() => hydrated?.encryptedKeyDraft);
  const [phone, setPhone] = useState(() => hydrated?.phone ?? '');
  const [phoneSent, setPhoneSent] = useState(() => hydrated?.phoneSent ?? false);
  const [code, setCode] = useState('');
  const [phoneToken, setPhoneToken] = useState<string | undefined>(() => hydrated?.phoneToken);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [usernameError, setUsernameError] = useState('');
  const [phoneError, setPhoneError] = useState('');
  const [codeError, setCodeError] = useState('');

  const stepName = steps[step];

  // Persist non-secret progress whenever it changes.
  useEffect(() => {
    const draft: RegWizardDraft = {
      flow, authMethod, step, address, username, phone, phoneSent, phoneToken, encryptedKeyDraft,
    };
    saveRegDraft(draft);
  }, [flow, authMethod, step, address, username, phone, phoneSent, phoneToken, encryptedKeyDraft]);

  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  function regeneratePhrase() {
    setMnemonic(generateMnemonic());
    setSavedPhrase(false);
  }

  function handleCancel() {
    clearRegDraft();
    onCancel();
  }

  // ---- Step: password (native) — derive + encrypt the key, then advance --------
  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  async function handlePassword() {
    setError('');
    if (password.length < 8 || password !== confirmPassword) return;
    setBusy(true);
    try {
      const { privateKey, address: derived } = deriveKeyPair(mnemonic);
      const encrypted = await encryptPrivateKey(privateKey, password);
      setAddress(derived);
      setEncryptedKeyDraft(encrypted);
      setPassword('');
      setConfirmPassword('');
      next();
    } catch (e) {
      setError(getMessage(e));
    } finally {
      setBusy(false);
    }
  }

  // ---- Step: phone — send + verify, then finalize ------------------------------
  async function handleSendCode() {
    setPhoneError('');
    setBusy(true);
    try {
      await otpStart(phone.trim());
      setPhoneSent(true);
    } catch (e) {
      setPhoneError(getFieldError(e, 'phone') || getMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyAndFinish() {
    setCodeError('');
    setError('');
    setBusy(true);
    try {
      const token = phoneToken ?? (await otpCheck(phone.trim(), code.trim())).phone_token;
      setPhoneToken(token);
      await finalize(token);
    } catch (e) {
      const codeErr = getFieldError(e, 'code');
      if (codeErr) setCodeError(codeErr);
      else setError(getMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function finalize(token: string) {
    try {
      const { access, username: savedName, avatar_url } = await register(address, username.trim(), token);
      if (flow === 'native' && encryptedKeyDraft) saveEncryptedKey(encryptedKeyDraft);
      saveAuthSession(address, savedName, access, avatar_url);
      setAuthMethod(authMethod);
      clearRegDraft();
      onComplete();
    } catch (e) {
      // Username taken / invalid → bounce back to the username step.
      const userErr = getFieldError(e, 'username');
      if (userErr) {
        setUsernameError(userErr);
        setPhoneToken(token); // keep the verified token so they don't re-OTP
        setStep(steps.indexOf('username'));
        return;
      }
      throw e;
    }
  }

  const usernameReady = username.trim().length >= 3;

  return (
    <div className="flex flex-col gap-5">
      <div className="space-y-1 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          {flow === 'native' ? 'Create Account' : 'Finish signing up'} — Step {step + 1} of {steps.length}
        </p>
      </div>

      {regenerated && stepName === 'mnemonic' && (
        <Alert>
          <AlertDescription className="text-sm">
            For your security we generated a fresh passphrase — the previous one was never saved.
          </AlertDescription>
        </Alert>
      )}

      {/* ---- Mnemonic ---- */}
      {stepName === 'mnemonic' && (
        <div className="space-y-4">
          <Alert>
            <AlertDescription className="text-amber-600 font-medium">
              Write down these 12 words and store them safely. You cannot recover your account without them.
            </AlertDescription>
          </Alert>
          <div className="grid grid-cols-3 gap-2">
            {mnemonic.split(' ').map((word, i) => (
              <div key={i} className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground w-4">{i + 1}.</span>
                <Badge variant="secondary" className="font-mono text-xs">{word}</Badge>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="saved-phrase" checked={savedPhrase} onCheckedChange={(v) => setSavedPhrase(!!v)} />
            <Label htmlFor="saved-phrase" className="cursor-pointer">I have saved my 12-word passphrase</Label>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={regeneratePhrase}>Regenerate</Button>
            <Button className="flex-1" disabled={!savedPhrase} onClick={next}>Continue</Button>
          </div>
        </div>
      )}

      {/* ---- Password ---- */}
      {stepName === 'password' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">Set a password to encrypt your private key locally on this device.</p>
          <div className="space-y-1">
            <Label htmlFor="reg-pw">Password</Label>
            <Input id="reg-pw" type="password" placeholder="At least 8 characters" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="reg-pw2">Confirm password</Label>
            <Input id="reg-pw2" type="password" placeholder="Repeat password" value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)} aria-invalid={passwordMismatch} />
            <FieldError>{passwordMismatch ? 'Passwords do not match' : ''}</FieldError>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={back}>Back</Button>
            <Button className="flex-1" disabled={busy || password.length < 8 || password !== confirmPassword}
              onClick={handlePassword}>{busy ? 'Encrypting…' : 'Continue'}</Button>
          </div>
        </div>
      )}

      {/* ---- Username ---- */}
      {stepName === 'username' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">Pick a unique username. This is how others will find you.</p>
          <div className="space-y-1">
            <Label htmlFor="reg-username">Username</Label>
            <Input id="reg-username" type="text" placeholder="e.g. Satoshi" value={username}
              onChange={(e) => { setUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, '')); if (usernameError) setUsernameError(''); }}
              aria-invalid={!!usernameError} />
            <FieldError>{usernameError}</FieldError>
          </div>
          <div className="flex gap-2">
            {flow === 'native'
              ? <Button variant="outline" className="flex-1" onClick={back}>Back</Button>
              : <Button variant="outline" className="flex-1" onClick={handleCancel}>Cancel</Button>}
            <Button className="flex-1" disabled={!usernameReady} onClick={next}>Continue</Button>
          </div>
        </div>
      )}

      {/* ---- Phone OTP ---- */}
      {stepName === 'phone' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Verify your phone number. We’ll text you a one-time code.
          </p>
          <div className="space-y-1">
            <Label htmlFor="reg-phone">Phone number</Label>
            <Input id="reg-phone" type="tel" placeholder="+1 415 555 0100" value={phone}
              onChange={(e) => { setPhone(e.target.value); if (phoneError) setPhoneError(''); }}
              disabled={phoneSent} aria-invalid={!!phoneError} />
            <FieldError>{phoneError}</FieldError>
          </div>

          {!phoneSent ? (
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={back}>Back</Button>
              <Button className="flex-1" disabled={busy || phone.trim().length < 6} onClick={handleSendCode}>
                {busy ? 'Sending…' : 'Send code'}
              </Button>
            </div>
          ) : (
            <>
              <div className="space-y-1">
                <Label htmlFor="reg-code">Verification code</Label>
                <Input id="reg-code" inputMode="numeric" placeholder="123456" value={code}
                  onChange={(e) => { setCode(e.target.value.replace(/\D/g, '')); if (codeError) setCodeError(''); }}
                  aria-invalid={!!codeError} />
                <FieldError>{codeError}</FieldError>
                <button type="button" className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
                  onClick={() => { setPhoneSent(false); setCode(''); setPhoneToken(undefined); }}>
                  Use a different number
                </button>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" disabled={busy} onClick={handleSendCode}>Resend</Button>
                <Button className="flex-1" disabled={busy || code.trim().length < 4} onClick={handleVerifyAndFinish}>
                  {busy ? 'Verifying…' : 'Verify & finish'}
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    </div>
  );
}
