import { useState } from 'react';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { PositionCard } from '@/components/PositionCard';
import { AttachmentRow } from '@/components/AttachmentRow';
import type { PositionSummaryItem, AssetItem } from '@/lib/types';
import { TrendingUp, TrendingDown, CheckCircle2, XCircle, Clock, AlertTriangle, CircleMinus } from 'lucide-react';
import { cn, formatCompactPrice } from '@/lib/utils';

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

function StatusIcon({ status }: { status: PositionSummaryItem['status'] }) {
  switch (status) {
    case 'confirmed': return <CheckCircle2 className="size-3.5 text-emerald-500" />;
    case 'rejected': return <XCircle className="size-3.5 text-rose-500" />;
    case 'active': return <Clock className="size-3.5 text-indigo-400" />;
    case 'missed':
    case 'expired': return <AlertTriangle className="size-3.5 text-amber-500" />;
    case 'closed_early': return <CircleMinus className="size-3.5 text-muted-foreground" />;
    default: return <Clock className="size-3.5 text-muted-foreground" />;
  }
}

function statusBarClass(status: PositionSummaryItem['status']): string {
  switch (status) {
    case 'confirmed': return 'bg-emerald-500';
    case 'rejected': return 'bg-red-500';
    case 'active': return 'bg-indigo-400';
    case 'missed':
    case 'expired': return 'bg-amber-500';
    default: return 'bg-muted-foreground/40';
  }
}

/** Progress through the position lifetime window (0–100). */
function lifetimeProgress(createdAt: string, lifetime: string): number {
  const start = new Date(createdAt).getTime();
  const end = new Date(lifetime).getTime();
  const span = end - start;
  if (!Number.isFinite(span) || span <= 0) return 100;
  const now = Date.now();
  if (now <= start) return 0;
  if (now >= end) return 100;
  return ((now - start) / span) * 100;
}

export function PositionAttachmentCard({ position, assets = [] }: PositionAttachmentCardProps) {
  const [open, setOpen] = useState(false);

  const asset = position.asset_obj ?? assets.find((a) => a.id === position.asset);
  const symbol = asset?.symbol ?? `#${position.asset}`;
  const isLong = position.direction === 'long';

  const pnl = position.pnl_percentage;
  const hasPnl = pnl !== null && pnl !== undefined;
  const isResolved = !['pending', 'active'].includes(position.status);
  const timelinePct = isResolved ? 100 : lifetimeProgress(position.created_at, position.lifetime);

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
          title={symbol}
          titleTone={isLong ? 'text-emerald-400' : 'text-rose-400'}
          meta={
            <span className={cn(isLong ? 'text-emerald-400' : 'text-rose-400')}>
              {isLong ? 'Long' : 'Short'}
            </span>
          }
          summary={
            <span className="truncate">
              EP {formatCompactPrice(position.entry_price)} · TP {formatCompactPrice(position.take_profit)} · SL {formatCompactPrice(position.stop_loss)}
            </span>
          }
          right={
            <span className="flex items-center gap-2">
              {hasPnl && (
                <span className={cn('text-[10px] font-semibold tabular-nums', pnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                </span>
              )}
              <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                <StatusIcon status={position.status} />
                {statusLabel(position.status)}
              </span>
            </span>
          }
          progress={{
            value: timelinePct,
            label: `${Math.round(timelinePct)}%`,
            className: statusBarClass(position.status),
          }}
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
