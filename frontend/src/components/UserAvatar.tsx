import { cn } from '@/lib/utils';
import { avatarColor, avatarLabel } from '@/lib/wallet';

type Size = 'xs' | 'sm' | 'md' | 'lg';

const sizeMap: Record<Size, string> = {
  xs: 'size-6 text-[9px]',
  sm: 'size-8 text-[10px]',
  md: 'size-9 text-xs',
  lg: 'size-12 text-sm',
};

interface UserAvatarProps {
  address: string;
  size?: Size;
  ring?: boolean;
  className?: string;
}

export function UserAvatar({ address, size = 'md', ring = false, className }: UserAvatarProps) {
  return (
    <div
      aria-hidden
      className={cn(
        'rounded-full flex items-center justify-center text-white font-bold shrink-0 select-none',
        sizeMap[size],
        ring && 'ring-2 ring-background',
        className,
      )}
      style={{ background: avatarColor(address) }}
    >
      {avatarLabel(address)}
    </div>
  );
}
