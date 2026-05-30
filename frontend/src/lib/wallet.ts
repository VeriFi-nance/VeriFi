/** Stable, deterministic UI helpers for an Ethereum-style address. */

/** Two-character label drawn from the address (skips the 0x prefix). */
export function avatarLabel(addr: string): string {
  return (addr ?? '').slice(2, 4).toUpperCase();
}

/** HSL background hue derived from the first byte of the address. */
export function avatarColor(addr: string): string {
  if (!addr || addr.length < 4) return 'hsl(220 70% 55%)';
  const hue = (parseInt(addr.slice(2, 4), 16) % 120) + 200;
  return `hsl(${hue} 70% 55%)`;
}

/** Compact `0x1234…abcd` form for display. */
export function truncateAddress(addr: string | null | undefined): string {
  if (!addr) return '—';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}
