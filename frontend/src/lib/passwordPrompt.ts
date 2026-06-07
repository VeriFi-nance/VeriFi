/**
 * Module-level bridge so non-React code (e.g. `lib/signing.ts`) can open the
 * React password modal and await the entered value.
 *
 * `PasswordPromptProvider` registers its opener via `setPasswordRequester` on
 * mount; callers use `requestPassword`.
 */

export interface PasswordRequest {
  /** Short reason shown in the dialog, e.g. "Sign this action". */
  reason?: string;
  /** Optional error to surface (e.g. after a wrong-password retry). */
  error?: string;
}

type Requester = (req: PasswordRequest) => Promise<string>;

let requester: Requester | null = null;

export function setPasswordRequester(fn: Requester | null): void {
  requester = fn;
}

/**
 * Resolves with the password the user typed, or rejects if they cancel.
 * Throws if no provider is mounted.
 */
export function requestPassword(req: PasswordRequest = {}): Promise<string> {
  if (!requester) {
    return Promise.reject(new Error('Password prompt unavailable'));
  }
  return requester(req);
}
