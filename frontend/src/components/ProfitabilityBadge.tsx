import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { ProfitabilityData } from '@/lib/types';

interface Props {
  data?: ProfitabilityData | null;
  className?: string;
}

type Timeframe = '7D' | '30D' | 'ALL';

export default function ProfitabilityBadge({ data, className }: Props) {
  const [timeframe, setTimeframe] = useState<Timeframe>('30D');

  if (!data || data.updated_at == null) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground',
          className,
        )}
      >
        No PnL
      </span>
    );
  }

  const pnl =
    timeframe === '7D'
      ? data.pnl_7d
      : timeframe === '30D'
      ? data.pnl_30d
      : data.pnl_all;

  const cycle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setTimeframe((t) => (t === '7D' ? '30D' : t === '30D' ? 'ALL' : '7D'));
  };

  const tone =
    pnl > 0
      ? 'bg-success/10 text-success border-success/30'
      : pnl < 0
      ? 'bg-danger/10 text-danger border-danger/30'
      : 'bg-muted text-muted-foreground border-border';

  return (
    <button
      onClick={cycle}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors hover:opacity-80 focus:outline-none num',
        tone,
        className,
      )}
      title={`PnL over ${timeframe === 'ALL' ? 'all time' : timeframe}. Click to toggle.`}
    >
      <span className="font-bold opacity-70">{timeframe}</span>
      {pnl > 0 ? '+' : ''}
      {pnl.toFixed(2)}%
    </button>
  );
}
