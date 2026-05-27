import { useEffect, useState } from 'react';
import { Coins, Flame, TrendingDown, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { buyShares, getMarket, previewBuy } from '@/lib/api';
import type { BuyPreviewResult, ClaimMarketItem } from '@/lib/types';

interface Props {
  claimId: number;
  onChange?: () => void;
}

export function MarketPanel({ claimId, onChange }: Props) {
  const [market, setMarket] = useState<ClaimMarketItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewYes, setPreviewYes] = useState<BuyPreviewResult | null>(null);
  const [previewNo, setPreviewNo] = useState<BuyPreviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = async () => {
    try {
      setLoading(true);
      const m = await getMarket(claimId);
      setMarket(m);
      setError(null);
      if (!m.resolved) {
        const [py, pn] = await Promise.all([
          previewBuy(claimId, 'YES'),
          previewBuy(claimId, 'NO'),
        ]);
        setPreviewYes(py);
        setPreviewNo(pn);
      }
    } catch (e: any) {
      setError(e.message || 'No market');
      setMarket(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claimId]);

  const handleBuy = async (side: 'YES' | 'NO') => {
    setBusy(true);
    setActionError(null);
    try {
      await buyShares(claimId, side);
      await reload();
      onChange?.();
    } catch (e: any) {
      setActionError(e.message || 'Buy failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="text-xs text-muted-foreground">Loading market…</div>;
  if (error || !market) {
    return (
      <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        No reputation market on this claim.
      </div>
    );
  }

  const yesPct = market.yes_price * 100;
  const noPct = 100 - yesPct;
  const hasStake = !!market.your_stake;

  return (
    <div className="rounded-lg border bg-card p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold flex items-center gap-1.5">
          <Coins className="size-3.5" /> Reputation Market
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span>{market.stake_count} stakers</span>
          <span>·</span>
          <span className="flex items-center gap-1">
            <Flame className="size-3" /> {market.total_burned.toFixed(2)} burned
          </span>
        </div>
      </div>

      {/* Live YES/NO price */}
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="flex items-center gap-1 font-medium text-emerald-600">
            <TrendingUp className="size-3" /> YES {yesPct.toFixed(1)}%
          </span>
          <span className="flex items-center gap-1 font-medium text-red-600">
            <TrendingDown className="size-3" /> NO {noPct.toFixed(1)}%
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-red-500/20 overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: `${yesPct}%` }}
          />
        </div>
      </div>

      {market.resolved ? (
        <div className="text-xs">
          {market.refunded_trivial ? (
            <Badge variant="secondary">Refunded — trivial claim</Badge>
          ) : (
            <Badge variant="outline">Resolved · paid out</Badge>
          )}
        </div>
      ) : (
        <>
          {hasStake ? (
            <div className="rounded-md bg-muted/50 px-2.5 py-2 text-xs space-y-0.5">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Your stake</span>
                <Badge
                  variant={market.your_stake!.side === 'YES' ? 'success' : 'destructive'}
                  className="text-[10px] px-1.5 py-0"
                >
                  {market.your_stake!.side}
                  {market.your_stake!.is_creator && ' · creator'}
                </Badge>
              </div>
              <div className="flex items-center justify-between font-mono">
                <span>Locked payout if correct:</span>
                <span className="font-semibold">
                  {market.your_stake!.locked_payout_if_win.toFixed(2)} rep
                </span>
              </div>
              <div className="text-[10px] text-muted-foreground">
                Paid {market.your_stake!.rep_paid_gross.toFixed(0)} rep · entry{' '}
                {(market.your_stake!.entry_price * 100).toFixed(1)}%
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <BuyButton
                side="YES"
                preview={previewYes}
                rep={market.trader_stake}
                disabled={busy}
                onClick={() => handleBuy('YES')}
              />
              <BuyButton
                side="NO"
                preview={previewNo}
                rep={market.trader_stake}
                disabled={busy}
                onClick={() => handleBuy('NO')}
              />
            </div>
          )}
          {actionError && (
            <div className="text-[11px] text-red-600">{actionError}</div>
          )}
          <div className="text-[10px] text-muted-foreground">
            5% trade burn · refund if losers &lt; {market.min_loser_voters} or total &lt;{' '}
            {market.min_total_voters}.
          </div>
        </>
      )}
    </div>
  );
}

function BuyButton({
  side,
  preview,
  rep,
  disabled,
  onClick,
}: {
  side: 'YES' | 'NO';
  preview: BuyPreviewResult | null;
  rep: number;
  disabled: boolean;
  onClick: () => void;
}) {
  const isYes = side === 'YES';
  return (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'flex-col items-start h-auto py-2 px-3 gap-0.5',
        isYes
          ? 'border-emerald-500/40 hover:bg-emerald-500/10 text-emerald-700'
          : 'border-red-500/40 hover:bg-red-500/10 text-red-700'
      )}
    >
      <span className="text-xs font-semibold">
        Buy {side} ({rep} rep)
      </span>
      {preview && (
        <span className="text-[10px] font-mono opacity-80">
          locked: {preview.locked_payout_if_win.toFixed(2)} rep
        </span>
      )}
    </Button>
  );
}
