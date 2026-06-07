// ---------------------------------------------------------------------------
// Pending-registration bridge.
//
// MetaMask / Privy auth runs deep in non-React code (walletAuth, PrivyAccountSync).
// When it discovers a brand-new address it can't just create the account anymore —
// the user must pick a username and verify a phone first. This module lets that
// code hand control to the React-rendered RegistrationWizard and await the result.
//
//   const address = ...;
//   await requestRegistration(address, 'metamask'); // resolves once the wizard
//                                                    // registers + saves the session
//
// RegistrationGate subscribes, renders the wizard, then calls
// resolvePendingRegistration() / rejectPendingRegistration() when it finishes.
// ---------------------------------------------------------------------------

import type { AuthMethod } from './auth';

export interface PendingRegistration {
  address: string;
  authMethod: AuthMethod;
}

let pending: PendingRegistration | null = null;
let resolver: (() => void) | null = null;
let rejecter: ((err: Error) => void) | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((l) => l());
}

export function requestRegistration(address: string, authMethod: AuthMethod): Promise<void> {
  // Replace any stale request.
  if (rejecter) rejecter(new Error('Registration superseded.'));
  return new Promise<void>((resolve, reject) => {
    pending = { address: address.toLowerCase(), authMethod };
    resolver = resolve;
    rejecter = reject;
    emit();
  });
}

export function resolvePendingRegistration(): void {
  const r = resolver;
  pending = null;
  resolver = null;
  rejecter = null;
  emit();
  r?.();
}

export function rejectPendingRegistration(err: Error = new Error('Registration cancelled.')): void {
  const r = rejecter;
  pending = null;
  resolver = null;
  rejecter = null;
  emit();
  r?.(err);
}

export function subscribePendingRegistration(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getPendingRegistration(): PendingRegistration | null {
  return pending;
}
