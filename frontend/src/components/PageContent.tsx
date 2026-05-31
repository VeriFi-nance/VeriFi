import { cn } from '@/lib/utils';

type PageContentWidth = 'narrow' | 'wide';

const widthClass: Record<PageContentWidth, string> = {
  narrow: 'max-w-2xl',
  wide: 'max-w-5xl',
};

interface PageContentProps {
  children: React.ReactNode;
  className?: string;
  width?: PageContentWidth;
}

/** Centers page content and applies a light grid fade sized to the content column. */
export function PageContent({ children, className, width = 'narrow' }: PageContentProps) {
  return (
    <div className={cn('relative mx-auto w-full', widthClass[width], className)}>
      <div aria-hidden className="content-grid-fade pointer-events-none absolute inset-0 z-0" />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
