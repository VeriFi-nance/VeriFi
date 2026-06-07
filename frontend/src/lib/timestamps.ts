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

export function formatRelativeTimestamp(value: TimestampValue, now: Date = new Date()): string {
  const date = parseTimestamp(value);
  if (!date) return '';

  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.max(0, Math.floor(diffMs / 1000));

  if (diffSeconds < 45) return 'a few secs ago';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${Math.max(1, diffMinutes)}m`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d`;

  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  return date.toLocaleDateString();
}
