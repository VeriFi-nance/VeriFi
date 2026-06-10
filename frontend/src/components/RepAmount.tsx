import { cn } from '@/lib/utils';
import { RepIcon } from '@/components/RepIcon';

interface RepAmountProps {
  value: number | string;
  className?: string;
  iconClassName?: string;
  iconSize?: 'xs' | 'sm' | 'md' | 'lg';
}

/** Numeric rep value paired with the rep score icon. */
export function RepAmount({
  value,
  className,
  iconClassName,
  iconSize = 'xs',
}: RepAmountProps) {
  return (
    <span className={cn('inline-flex items-center gap-0.5 align-middle font-mono num', className)}>
      {value}
      <RepIcon size={iconSize} className={iconClassName} />
    </span>
  );
}
