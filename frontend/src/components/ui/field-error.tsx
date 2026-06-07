import { cn } from '@/lib/utils';

/**
 * Inline form-field error message. Render directly under the related <Input>,
 * and set `aria-invalid={!!error}` on that input so its border turns red
 * (shadcn Input styles `aria-invalid:border-destructive`).
 *
 * Renders nothing when there's no message, so it's safe to always include.
 */
export function FieldError({ children, className }: { children?: React.ReactNode; className?: string }) {
  if (!children) return null;
  return <p className={cn('text-xs text-destructive', className)}>{children}</p>;
}
