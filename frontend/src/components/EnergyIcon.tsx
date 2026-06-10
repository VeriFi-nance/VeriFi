import { cn } from '@/lib/utils';
import energyIcon from '@/assets/icons/energy.png';

const sizeClass = {
  xs: 'size-3.5',
  sm: 'size-4',
  md: 'size-5',
  lg: 'size-6',
} as const;

interface EnergyIconProps {
  className?: string;
  size?: keyof typeof sizeClass;
}

export function EnergyIcon({ className, size = 'sm' }: EnergyIconProps) {
  return (
    <img
      src={energyIcon}
      alt=""
      aria-hidden
      className={cn('shrink-0 object-contain', sizeClass[size], className)}
    />
  );
}
