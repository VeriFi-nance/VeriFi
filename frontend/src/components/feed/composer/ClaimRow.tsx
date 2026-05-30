import { Badge } from '@/components/ui/badge';
import { CalendarDays } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ClaimRowProps {
  assetSymbol: string;
  direction: 'Bullish' | 'Bearish' | 'bullish' | 'bearish';
  percentage: string;
  until: string;
}

/** Compact preview row for a single claim. */
export function ClaimRow({ assetSymbol, direction, percentage, until }: ClaimRowProps) {
  const isBullish = direction === 'Bullish' || direction === 'bullish';
  return (
    <div className="flex items-center gap-2 rounded-md border border-border px-3 py-2 bg-muted/40">
      <span
        className={cn(
          'size-2 rounded-full shrink-0',
          isBullish ? 'bg-success' : 'bg-danger',
        )}
      />
      <span className="font-mono font-semibold text-xs">
        {assetSymbol || 'Unknown'}
      </span>
      <Badge
        variant={isBullish ? 'success' : 'destructive'}
        className="text-[10px] px-1.5 py-0 num"
      >
        {isBullish ? '▲' : '▼'} {percentage ? `${parseFloat(percentage).toFixed(1)}%` : '? %'}
      </Badge>
      <span className="flex items-center gap-1 text-xs text-muted-foreground flex-1 num">
        <CalendarDays className="size-3" />
        {until
          ? new Date(until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
          : 'No date'}
      </span>
    </div>
  );
}
