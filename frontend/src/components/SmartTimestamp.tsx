import { cn } from '@/lib/utils';
import { formatFullTimestamp, formatRelativeTimestamp, parseTimestamp } from '@/lib/timestamps';

interface SmartTimestampProps {
  value: string | number | Date | null | undefined;
  className?: string;
  fallback?: string;
  mode?: 'relative' | 'full';
}

export function SmartTimestamp({ value, className, fallback = '', mode = 'relative' }: SmartTimestampProps) {
  const date = parseTimestamp(value);
  if (!date) return fallback ? <span className={className}>{fallback}</span> : null;
  const fullTimestamp = formatFullTimestamp(date);

  return (
    <time
      dateTime={date.toISOString()}
      title={fullTimestamp}
      className={cn('num', className)}
    >
      {mode === 'full' ? fullTimestamp : formatRelativeTimestamp(date)}
    </time>
  );
}
