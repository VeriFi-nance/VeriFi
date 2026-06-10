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
}: AttachmentRowProps) {
  const pct = progress ? Math.min(100, Math.max(0, progress.value)) : null;

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
          <span className={cn('truncate font-mono text-xs font-bold text-foreground', titleTone)}>
            {title}
          </span>
          {meta && <span className="shrink-0 text-[10px] font-semibold text-muted-foreground">{meta}</span>}
          {badge && (
            <Badge variant={badgeVariant} className="px-1.5 py-0 text-[9px] uppercase tracking-wide text-muted-foreground">
              {badge}
            </Badge>
          )}
          {right && <div className="ml-auto shrink-0">{right}</div>}
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <div className="min-w-0 flex-1 text-[11px] leading-snug text-muted-foreground">
            {summary}
          </div>
          {progress && pct !== null && (
            <div className="hidden w-20 shrink-0 items-center gap-1.5 sm:flex">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div className={cn('h-full rounded-full transition-all', progress.className)} style={{ width: `${pct}%` }} />
              </div>
              {progress.label && (
                <span className="w-7 text-right text-[10px] tabular-nums text-muted-foreground">
                  {progress.label}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
    </div>
  );
}
