import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Allow only image-safe URL schemes before binding a value to an <img src>.
 * Guards against a tainted value (e.g. from localStorage or a file input)
 * carrying a dangerous scheme like `javascript:` or `data:text/html`.
 * Returns the URL when safe, otherwise `undefined`.
 *
 * Uses `startsWith` prefix checks (a recognized sanitizing guard) so the
 * returned value is provably scheme-constrained.
 */
/**
 * Extract the first image file from a clipboard paste, if any. Lets users paste
 * an image (e.g. a screenshot) into a composer and have it treated as an upload.
 */
/**
 * Compact price for tight rows: 62217.54 → "62.2k", 1500000 → "1.5M".
 * Values under 1000 keep up to 2 decimals.
 */
export function formatCompactPrice(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${trimZeros((value / 1_000_000).toFixed(1))}M`;
  if (abs >= 1_000) return `${trimZeros((value / 1_000).toFixed(1))}k`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function trimZeros(s: string): string {
  return s.replace(/\.0$/, '');
}

export function imageFileFromClipboard(data: DataTransfer | null): File | null {
  if (!data) return null;
  for (const item of Array.from(data.items)) {
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) return file;
    }
  }
  return null;
}

export function safeImageSrc(url: string | null | undefined): string | undefined {
  if (typeof url !== 'string' || url.length === 0) return undefined;
  if (
    url.startsWith('https://') ||
    url.startsWith('http://') ||
    url.startsWith('blob:') ||
    url.startsWith('data:image/')
  ) {
    // Contextual output encoding: percent-encode HTML meta-characters
    // (e.g. < > "). Harmless for our URL shapes (Cloudinary/blob/data:image
    // contain no such characters) but neutralizes any injected markup.
    return encodeURI(url);
  }
  return undefined;
}
