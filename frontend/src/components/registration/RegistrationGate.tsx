import { useState, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { RegistrationWizard } from './RegistrationWizard';
import {
  getPendingRegistration, subscribePendingRegistration,
  resolvePendingRegistration, rejectPendingRegistration,
} from '@/lib/pendingRegistration';
import { loadRegDraft, clearRegDraft } from '@/lib/regWizard';
import type { AuthMethod } from '@/lib/auth';

/**
 * Renders the social (MetaMask / Privy) registration wizard whenever wallet auth
 * discovers a brand-new address. Mounted once at the app root.
 *
 * Two ways it opens:
 *  - Live: `requestRegistration()` fired from walletAuth/PrivyAccountSync.
 *  - Resume after reload: a persisted `social` draft (register needs no signer,
 *    so we can finish from the draft alone).
 */
export function RegistrationGate() {
  const navigate = useNavigate();
  const pending = useSyncExternalStore(subscribePendingRegistration, getPendingRegistration);

  // Resume a social draft left over from a reload (computed once).
  const [resumed] = useState(() => {
    const d = loadRegDraft();
    return d && d.flow === 'social' ? { address: d.address ?? '', authMethod: d.authMethod } : null;
  });

  const active = pending ?? resumed;
  if (!active) return null;

  const authMethod: AuthMethod = active.authMethod;

  function handleComplete() {
    if (pending) {
      resolvePendingRegistration();
    } else {
      // Resumed-after-reload: no awaiting caller, navigate ourselves.
      navigate('/feed', { replace: true });
    }
  }

  function handleCancel() {
    clearRegDraft();
    if (pending) rejectPendingRegistration();
    // Resumed case: dropping `active` requires the draft gone; reload-safe enough.
    navigate('/feed', { replace: true });
  }

  return (
    <RD.Root open onOpenChange={(o) => { if (!o) handleCancel(); }}>
      <RD.Content className="sm:max-w-md">
        <RD.Header>
          <RD.Title>Finish creating your account</RD.Title>
          <RD.Description>Choose a username and verify your phone to continue.</RD.Description>
        </RD.Header>
        <div className="pt-2">
          <RegistrationWizard
            flow="social"
            authMethod={authMethod}
            address={active.address}
            onComplete={handleComplete}
            onCancel={handleCancel}
          />
        </div>
      </RD.Content>
    </RD.Root>
  );
}
