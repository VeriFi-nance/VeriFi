import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

const sizeStyles = {
  sm: {
    text: 'text-2xl',
  },
  lg: {
    text: 'text-[3rem]',
  },
} as const;

interface BrandLogoProps {
  to?: string;
  link?: boolean;
  size?: keyof typeof sizeStyles;
  showText?: boolean;
  /** Show "V" when narrow, full wordmark at lg+ (sidebar). */
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
  const showWordmark = showText ?? true;

  const fullWordmark = (
    <span className={cn('font-serif-logo leading-none tracking-normal', styles.text)}>
      <span className="font-bold text-muted-foreground">Veri</span>
      <span className="font-bold text-foreground">Fi</span>
    </span>
  );

  const compactMark = (
    <span
      className={cn(
        'font-serif-logo font-bold leading-none text-foreground tracking-normal',
        styles.text,
      )}
      aria-hidden
    >
      V
    </span>
  );

  const content = !showWordmark ? null : responsiveText ? (
    <>
      <span className="lg:hidden">{compactMark}</span>
      <span className="hidden lg:inline">{fullWordmark}</span>
    </>
  ) : (
    fullWordmark
  );

  const classes = cn('inline-flex items-center', className);

  if (link) {
    return (
      <Link to={to} className={classes} aria-label="VeriFi home">
        {content}
      </Link>
    );
  }

  return <div className={classes}>{content}</div>;
}
