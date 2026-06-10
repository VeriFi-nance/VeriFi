import { cn } from '@/lib/utils';
import repScoreIcon from '@/assets/icons/rep-score.png';

const sizeClass = {
  xs: 'size-3.5',
  sm: 'size-4',
  md: 'size-5',
  lg: 'size-6',
} as const;

interface RepIconProps {
  className?: string;
  size?: keyof typeof sizeClass;
}

export function RepIcon({ className, size = 'sm' }: RepIconProps) {
  return (
    <img
      src={repScoreIcon}
      alt=""
      aria-hidden
      className={cn('shrink-0 object-contain', sizeClass[size], className)}
    />
  );
}
