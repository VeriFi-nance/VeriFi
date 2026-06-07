import { useSyncExternalStore } from 'react';

const SYNC_EVENT = 'verifi-privy-sync-changed';

interface PrivySyncState {
  pending: boolean;
  error: string | null;
}

let state: PrivySyncState = { pending: false, error: null };

function notify(): void {
  window.dispatchEvent(new Event(SYNC_EVENT));
}

export function setPrivySyncPending(pending: boolean): void {
  state = { ...state, pending };
  notify();
}

export function setPrivySyncError(error: string | null): void {
  state = { ...state, error };
  notify();
}

export function clearPrivySyncState(): void {
  state = { pending: false, error: null };
  notify();
}

function subscribe(listener: () => void): () => void {
  window.addEventListener(SYNC_EVENT, listener);
  return () => window.removeEventListener(SYNC_EVENT, listener);
}

function getSnapshot(): PrivySyncState {
  return state;
}

export function usePrivySyncState(): PrivySyncState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
