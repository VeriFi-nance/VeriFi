import { useCallback, useEffect, useRef, useState } from 'react';
import { ResponsiveDialog as RD } from './ResponsiveDialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { setPasswordRequester, type PasswordRequest } from '@/lib/passwordPrompt';

/**
 * Renders the wallet-password modal and wires it into the module-level
 * `requestPassword` bridge so `lib/signing.ts` (and any other non-React caller)
 * can prompt for the password without using native `window.prompt`.
 */
export function PasswordPromptProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [req, setReq] = useState<PasswordRequest>({});
  const [value, setValue] = useState('');
  const resolverRef = useRef<{ resolve: (v: string) => void; reject: (e: Error) => void } | null>(null);

  const requester = useCallback((r: PasswordRequest) => {
    setReq(r);
    setValue('');
    setOpen(true);
    return new Promise<string>((resolve, reject) => {
      resolverRef.current = { resolve, reject };
    });
  }, []);

  useEffect(() => {
    setPasswordRequester(requester);
    return () => setPasswordRequester(null);
  }, [requester]);

  const cancel = useCallback(() => {
    resolverRef.current?.reject(new Error('Password required to sign'));
    resolverRef.current = null;
    setOpen(false);
  }, []);

  const submit = useCallback(() => {
    if (!value) return;
    resolverRef.current?.resolve(value);
    resolverRef.current = null;
    setOpen(false);
  }, [value]);

  return (
    <>
      {children}
      <RD.Root open={open} onOpenChange={(o) => { if (!o) cancel(); }}>
        <RD.Content className="md:max-w-sm" showCloseButton={false}>
          <RD.Header>
            <RD.Title>Wallet password</RD.Title>
            <RD.Description>
              {req.reason ? `${req.reason}. ` : ''}Enter your password to unlock your wallet.
            </RD.Description>
          </RD.Header>

          {req.error && (
            <Alert variant="destructive">
              <AlertDescription>{req.error}</AlertDescription>
            </Alert>
          )}

          <form
            onSubmit={(e) => { e.preventDefault(); submit(); }}
            className="space-y-3"
          >
            <div className="space-y-1.5">
              <Label htmlFor="wallet-password" className="text-xs font-semibold">Password</Label>
              <Input
                id="wallet-password"
                type="password"
                autoFocus
                autoComplete="current-password"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <RD.Footer>
              <Button type="button" variant="outline" onClick={cancel}>Cancel</Button>
              <Button type="submit" disabled={!value}>Unlock</Button>
            </RD.Footer>
          </form>
        </RD.Content>
      </RD.Root>
    </>
  );
}
