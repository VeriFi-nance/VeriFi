// ---------------------------------------------------------------------------
// Registration-wizard draft persistence.
//
// Lets the multi-step registration wizard survive a page reload / accidental
// close. We persist ONLY non-secret progress: the chosen username, the phone
// number + whether a code was sent, the verified phone_token, the derived
// address, and the *encrypted* key blob (safe — it's AES-GCM ciphertext).
//
// We NEVER persist the mnemonic plaintext or the password. So if the user
// reloads during the mnemonic step (before a password exists), the wizard
// regenerates a fresh phrase — see RegistrationWizard's "smart" recovery.
// ---------------------------------------------------------------------------

import type { EncryptedKey } from './keystore';
import type { AuthMethod } from './auth';

const STORAGE_KEY = 'verifi_reg_wizard';

export type RegFlow = 'native' | 'social';

export interface RegWizardDraft {
  flow: RegFlow;
  authMethod: AuthMethod;
  step: number;
  address?: string;
  username: string;
  phone: string;
  phoneSent: boolean;
  phoneToken?: string;
  /** AES-GCM encrypted private key (native flow only, after the password step). */
  encryptedKeyDraft?: EncryptedKey;
}

export function loadRegDraft(): RegWizardDraft | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RegWizardDraft;
  } catch {
    return null;
  }
}

export function saveRegDraft(draft: RegWizardDraft): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
}

export function clearRegDraft(): void {
  localStorage.removeItem(STORAGE_KEY);
}
