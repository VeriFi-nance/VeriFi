import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

const sizeStyles = {
  sm: {
    mark: 'size-7',
    text: 'text-base',
    gap: 'gap-2',
  },
  lg: {
    mark: 'size-12',
    text: 'text-3xl',
    gap: 'gap-3',
  },
} as const;

function VeriFiMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('shrink-0', className)}
      aria-hidden
    >
      <rect width="32" height="32" rx="8" className="fill-foreground" />
      <path
        d="M8.5 11.5 15.5 24.5 22.5 11.5"
        className="stroke-background"
        strokeWidth="2.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="23.5" cy="9.5" r="2.75" className="fill-success" />
    </svg>
  );
}

interface BrandLogoProps {
  to?: string;
  link?: boolean;
  size?: keyof typeof sizeStyles;
  showText?: boolean;
  responsiveText?: boolean;
  className?: string;
}

export function BrandLogo({
  to = '/feed',
  link = true,
  size = 'sm',
  showText,
  responsiveText = false,
  className,
}: BrandLogoProps) {
  const styles = sizeStyles[size];
  const showWordmark = showText ?? size === 'lg';

  const content = (
    <>
      <VeriFiMark className={cn(styles.mark, link && 'group-hover:scale-105 transition-transform')} />
      {showWordmark && (
        <span
          className={cn(
            'font-bold tracking-tight leading-none',
            styles.text,
            responsiveText && 'hidden lg:inline',
          )}
        >
          Veri<span className="text-success">Fi</span>
        </span>
      )}
    </>
  );

  const classes = cn('inline-flex items-center', styles.gap, className);

  if (link) {
    return (
      <Link to={to} className={cn(classes, 'group')} aria-label="VeriFi home">
        {content}
      </Link>
    );
  }

  return <div className={classes}>{content}</div>;
}
