type TimestampValue = string | number | Date | null | undefined;

export function parseTimestamp(value: TimestampValue): Date | null {
  if (value == null || value === '') return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatFullTimestamp(value: TimestampValue): string {
  const date = parseTimestamp(value);
  if (!date) return '';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatDateTimestamp(value: TimestampValue, options?: Intl.DateTimeFormatOptions): string {
  const date = parseTimestamp(value);
  if (!date) return '';
  return date.toLocaleDateString(undefined, options);
}

export function formatRelativeTimestamp(value: TimestampValue, now: Date = new Date()): string {
  const date = parseTimestamp(value);
  if (!date) return '';

  const diffMs = now.getTime() - date.getTime();
  const isFuture = diffMs < 0;
  const diffSeconds = Math.floor(Math.abs(diffMs) / 1000);
  const prefix = isFuture ? 'in ' : '';

  if (diffSeconds < 45) return isFuture ? 'in a few secs' : 'a few secs ago';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${prefix}${Math.max(1, diffMinutes)}m`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${prefix}${diffHours}h`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${prefix}${diffDays}d`;

  if (date.getFullYear() === now.getFullYear()) {
    return formatDateTimestamp(date, { month: 'short', day: 'numeric' });
  }

  return formatDateTimestamp(date);
}
