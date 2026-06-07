/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { ResponsiveDialog as RD } from './ResponsiveDialog';
import { Button } from './ui/button';

export interface ConfirmOptions {
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  /** `destructive` styles the confirm button red — use for irreversible actions. */
  variant?: 'default' | 'destructive';
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

/**
 * Replaces native `window.confirm`. Usage:
 *   const confirm = useConfirm();
 *   if (await confirm({ title: 'Close position?', variant: 'destructive' })) { ... }
 */
export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within <ConfirmProvider>');
  return ctx;
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((options) => {
    setOpts(options);
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const settle = useCallback((value: boolean) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setOpen(false);
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <RD.Root open={open} onOpenChange={(o) => { if (!o) settle(false); }}>
        <RD.Content className="md:max-w-sm" showCloseButton={false}>
          <RD.Header>
            <RD.Title>{opts?.title}</RD.Title>
            {opts?.description && <RD.Description>{opts.description}</RD.Description>}
          </RD.Header>
          <RD.Footer>
            <Button variant="outline" onClick={() => settle(false)}>
              {opts?.cancelText ?? 'Cancel'}
            </Button>
            <Button
              variant={opts?.variant === 'destructive' ? 'destructive' : 'default'}
              onClick={() => settle(true)}
            >
              {opts?.confirmText ?? 'Confirm'}
            </Button>
          </RD.Footer>
        </RD.Content>
      </RD.Root>
    </ConfirmContext.Provider>
  );
}
