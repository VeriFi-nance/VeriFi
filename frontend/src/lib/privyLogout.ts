type PrivyLogoutFn = () => Promise<void>;

let logoutFn: PrivyLogoutFn | null = null;

export function registerPrivyLogout(fn: PrivyLogoutFn): void {
  logoutFn = fn;
}

export function clearPrivyLogout(): void {
  logoutFn = null;
}

export async function triggerPrivyLogout(): Promise<void> {
  if (logoutFn) {
    await logoutFn();
  }
}
