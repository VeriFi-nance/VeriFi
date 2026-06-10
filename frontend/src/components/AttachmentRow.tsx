import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface AttachmentRowProps {
  icon?: ReactNode;
  title: string;
  titleTone?: string;
  meta?: ReactNode;
  badge?: string;
  badgeVariant?: React.ComponentProps<typeof Badge>['variant'];
  summary: ReactNode;
  progress?: {
    value: number;
    className: string;
    label?: string;
  };
  right?: ReactNode;
  actions?: ReactNode;
  className?: string;
  hideSummaryOnMobile?: boolean;
}

export function AttachmentRow({
  icon,
  title,
  titleTone,
  meta,
  badge,
  badgeVariant = 'outline',
  summary,
  progress,
  right,
  actions,
  className,
  hideSummaryOnMobile = false,
}: AttachmentRowProps) {
  const pct = progress ? Math.min(100, Math.max(0, progress.value)) : null;

  const progressBar =
    progress && pct !== null ? (
      <div className="flex w-20 shrink-0 items-center gap-1.5">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className={cn('h-full rounded-full transition-all', progress.className)} style={{ width: `${pct}%` }} />
        </div>
        {progress.label && (
          <span className="w-7 text-right text-[10px] tabular-nums text-muted-foreground">
            {progress.label}
          </span>
        )}
      </div>
    ) : null;

  const stackProgressWithRight = Boolean(right && progressBar);

  return (
    <div
      className={cn(
        'group/attachment flex w-full items-center gap-3 rounded-md border border-border/80 bg-background/45 px-3 py-2 text-left transition-colors hover:bg-muted/35',
        className,
      )}
    >
      {icon && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
          {icon}
        </div>
      )}

      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn('truncate font-mono text-xs font-bold leading-none text-foreground', titleTone)}>
            {title}
          </span>
          {meta && (
            <span
              className={cn(
                'inline-flex shrink-0 items-center font-semibold leading-none text-muted-foreground',
                hideSummaryOnMobile ? 'text-xs sm:text-[10px]' : 'text-[10px]',
              )}
            >
              {meta}
            </span>
          )}
          {badge && (
            <Badge variant={badgeVariant} className="px-1.5 py-0 text-[9px] uppercase tracking-wide text-muted-foreground">
              {badge}
            </Badge>
          )}
          {right && hideSummaryOnMobile && (
            <div className="ml-auto shrink-0 sm:hidden">{right}</div>
          )}
        </div>

        <div className={cn('flex min-w-0 items-center gap-2', hideSummaryOnMobile && 'hidden sm:flex')}>
          <div className="min-w-0 flex-1 text-[11px] leading-snug text-muted-foreground">
            {summary}
          </div>
          {progressBar && !stackProgressWithRight && (
            <div className="hidden w-20 shrink-0 items-center gap-1.5 sm:flex">{progressBar}</div>
          )}
        </div>
      </div>

      {right && (
        <div
          className={cn(
            'shrink-0 self-center',
            hideSummaryOnMobile && 'hidden sm:flex sm:flex-col sm:items-end sm:gap-1',
            !hideSummaryOnMobile && stackProgressWithRight && 'flex flex-col items-end gap-1',
          )}
        >
          {right}
          {stackProgressWithRight && (
            <div className={cn(!hideSummaryOnMobile && 'hidden sm:flex')}>{progressBar}</div>
          )}
        </div>
      )}

      {actions && <div className="flex shrink-0 items-center gap-1 self-center">{actions}</div>}
    </div>
  );
}
