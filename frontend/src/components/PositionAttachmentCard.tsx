import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { PositionCard } from '@/components/PositionCard';
import type { PositionSummaryItem, AssetItem } from '@/lib/types';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface PositionAttachmentCardProps {
  position: PositionSummaryItem;
  assets?: AssetItem[];
}

function statusBadgeVariant(status: PositionSummaryItem['status']): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'confirmed': return 'default';
    case 'active': return 'secondary';
    case 'rejected': return 'destructive';
    default: return 'outline';
  }
}

function statusLabel(status: PositionSummaryItem['status']): string {
  const map: Record<string, string> = {
    pending: 'Pending',
    active: 'Active',
    confirmed: 'Confirmed ✓',
    rejected: 'Rejected ✗',
    missed: 'Missed',
    closed_early: 'Closed Early',
    expired: 'Expired',
  };
  return map[status] ?? status;
}

export function PositionAttachmentCard({ position, assets = [] }: PositionAttachmentCardProps) {
  const [open, setOpen] = useState(false);

  const asset = position.asset_obj ?? assets.find((a) => a.id === position.asset);
  const symbol = asset?.symbol ?? `#${position.asset}`;
  const isLong = position.direction === 'long';

  const pnl = position.pnl_percentage;
  const hasPnl = pnl !== null && pnl !== undefined;

  return (
    <>
      {/* Compact trigger row — visually distinct from claim rows via indigo accent */}
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className="group w-full flex items-center gap-2.5 px-3 py-1.5 rounded-md
          border border-indigo-500/20 bg-indigo-500/5 hover:bg-indigo-500/10
          text-left transition-colors cursor-pointer"
        aria-label={`View position: ${symbol} ${position.direction}`}
      >
        {/* Direction icon */}
        <span
          className={`flex items-center justify-center size-5 rounded-sm shrink-0 ${
            isLong
              ? 'bg-emerald-500/15 text-emerald-500'
              : 'bg-rose-500/15 text-rose-500'
          }`}
        >
          {isLong ? (
            <TrendingUp className="size-3" />
          ) : (
            <TrendingDown className="size-3" />
          )}
        </span>

        {/* Asset + direction */}
        <span className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs font-bold text-foreground">{symbol}</span>
          <span
            className={`text-[10px] font-semibold uppercase tracking-wide ${
              isLong ? 'text-emerald-500' : 'text-rose-500'
            }`}
          >
            {isLong ? 'LONG' : 'SHORT'}
          </span>
          <span className="text-[10px] text-muted-foreground hidden sm:inline num">
            EP {position.entry_price.toLocaleString()} · TP {position.take_profit.toLocaleString()} · SL {position.stop_loss.toLocaleString()}
          </span>
        </span>

        {/* Right: PnL (if resolved) or status */}
        <span className="shrink-0 flex items-center gap-1.5">
          {hasPnl ? (
            <span
              className={`text-xs font-bold num ${
                pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'
              }`}
            >
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
            </span>
          ) : null}
          <Badge
            variant={statusBadgeVariant(position.status)}
            className="text-[9px] px-1.5 py-0 num"
          >
            {statusLabel(position.status)}
          </Badge>
          {/* Position label to differentiate from claims */}
          <span className="text-[9px] font-semibold uppercase tracking-widest text-indigo-400 hidden sm:inline">
            Position
          </span>
        </span>
      </button>

      {/* Full position detail modal */}
      <RD.Root open={open} onOpenChange={setOpen}>
        <RD.Content className="max-w-2xl">
          <RD.Header>
            <RD.Title className="flex items-center gap-2">
              {isLong ? (
                <TrendingUp className="size-4 text-emerald-500" />
              ) : (
                <TrendingDown className="size-4 text-rose-500" />
              )}
              {symbol} {isLong ? 'Long' : 'Short'} Position
            </RD.Title>
          </RD.Header>
          <div className="overflow-y-auto max-h-[70vh] pr-1">
            {/* Render the full PositionCard inside the modal — cast summary to full PositionItem shape */}
            <PositionCard
              position={{
                ...position,
                channel: position.channel ?? 0,
                entry_interval: position.lifetime, // best available fallback in summary shape
                exit_price: null,
                events: [],
              }}
              assets={asset ? [asset] : assets}
            />
          </div>
        </RD.Content>
      </RD.Root>
    </>
  );
}
