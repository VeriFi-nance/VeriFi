import { toast } from 'sonner';
import { ApiError } from './api';

/** Re-export so call sites import toast from one place. */
export { toast };

/** Best-effort human-readable message from any thrown value. */
export function getMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return fallback;
}

/** Per-field validation message for a form input, if the error carries one. */
export function getFieldError(err: unknown, field: string): string | undefined {
  if (err instanceof ApiError && err.fields?.[field]?.length) {
    return err.fields[field][0];
  }
  return undefined;
}

/** Show an error toast with the best message we can extract. */
export function toastError(err: unknown, fallback = 'Something went wrong'): void {
  toast.error(getMessage(err, fallback));
}
