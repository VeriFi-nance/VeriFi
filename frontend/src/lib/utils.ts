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
