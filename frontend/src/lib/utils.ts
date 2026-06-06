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
 */
export function safeImageSrc(url: string | null | undefined): string | undefined {
  if (typeof url !== 'string' || url.length === 0) return undefined;
  return /^(https?:\/\/|blob:|data:image\/)/i.test(url) ? url : undefined;
}
