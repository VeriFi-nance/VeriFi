import { useState } from 'react';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { PositionCard } from '@/components/PositionCard';
import { AttachmentRow } from '@/components/AttachmentRow';
import type { PositionSummaryItem, AssetItem } from '@/lib/types';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PositionAttachmentCardProps {
  position: PositionSummaryItem;
  assets?: AssetItem[];
}

function statusLabel(status: PositionSummaryItem['status']): string {
  const map: Record<string, string> = {
    pending: 'Pending',
    active: 'Active',
    confirmed: 'Confirmed',
    rejected: 'Rejected',
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
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className="w-full cursor-pointer"
        aria-label={`View position: ${symbol} ${position.direction}`}
      >
        <AttachmentRow
          icon={isLong ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
          title={symbol}
          titleTone={isLong ? 'text-emerald-400' : 'text-rose-400'}
          meta={
            <span className={cn(isLong ? 'text-emerald-400' : 'text-rose-400')}>
              {isLong ? 'Long' : 'Short'}
            </span>
          }
          badge="Position"
          summary={
            <span className="truncate">
              EP {position.entry_price.toLocaleString()} · TP {position.take_profit.toLocaleString()} · SL {position.stop_loss.toLocaleString()}
            </span>
          }
          right={
            <span className="flex items-center gap-2">
              {hasPnl && (
                <span className={cn('text-[10px] font-semibold tabular-nums', pnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                </span>
              )}
              <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {statusLabel(position.status)}
              </span>
            </span>
          }
        />
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
