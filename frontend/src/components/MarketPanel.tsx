import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { buyShares, getMarket, previewBuy } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import type { BuyPreviewResult, ClaimMarketItem } from '@/lib/types';

interface Props {
  claimId: number;
  onChange?: () => void;
}

export function MarketPanel({ claimId, onChange }: Props) {
  const openLogin = useOpenLogin();
  const auth = useAuthState();
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'No market');
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
    if (!auth.authenticated) {
      openLogin();
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await buyShares(claimId, side);
      await reload();
      onChange?.();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Buy failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading reputation market…</p>;
  }

  if (error || !market) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        No reputation market on this claim yet.
      </div>
    );
  }

  const agreePct = market.yes_price * 100;
  const disagreePct = 100 - agreePct;
  const hasStake = !!market.your_stake;

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
      <h3 className="text-sm font-semibold">Reputation market</h3>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-success">
            Agree {agreePct.toFixed(0)}%
          </span>
          <span className="font-medium text-destructive">
            Disagree {disagreePct.toFixed(0)}%
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-destructive/20 overflow-hidden">
          <div
            className="h-full bg-success transition-all"
            style={{ width: `${agreePct}%` }}
          />
        </div>
        <p className="text-[11px] text-muted-foreground">
          {market.stake_count} {market.stake_count === 1 ? 'person' : 'people'} staked
        </p>
      </div>

      {market.resolved ? (
        <div className="text-sm">
          {market.refunded_trivial ? (
            <Badge variant="secondary">Refunded — not enough voters</Badge>
          ) : (
            <Badge variant="outline">Market settled</Badge>
          )}
        </div>
      ) : hasStake ? (
        <YourStakeCard stake={market.your_stake!} />
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <BuyButton
            side="YES"
            label="Agree"
            preview={previewYes}
            rep={market.trader_stake}
            disabled={busy}
            onClick={() => handleBuy('YES')}
          />
          <BuyButton
            side="NO"
            label="Disagree"
            preview={previewNo}
            rep={market.trader_stake}
            disabled={busy}
            onClick={() => handleBuy('NO')}
          />
        </div>
      )}

      {actionError && (
        <p className="text-xs text-destructive">{actionError}</p>
      )}
    </div>
  );
}

function YourStakeCard({ stake }: { stake: NonNullable<ClaimMarketItem['your_stake']> }) {
  const isAgree = stake.side === 'YES';
  return (
    <div className="rounded-lg border border-border bg-card p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Your position</p>
        <Badge variant={isAgree ? 'success' : 'destructive'} className="text-[10px]">
          {isAgree ? 'Agree' : 'Disagree'}
          {stake.is_creator && ' · creator'}
        </Badge>
      </div>
      <p className="text-sm">
        If you&apos;re right, you win{' '}
        <span className="font-semibold font-mono num">
          {stake.locked_payout_if_win.toFixed(1)} rep
        </span>
      </p>
      <p className="text-xs text-muted-foreground">
        You staked {stake.rep_paid_gross.toFixed(0)} rep at {(stake.entry_price * 100).toFixed(0)}%
        odds
      </p>
    </div>
  );
}

function BuyButton({
  side,
  label,
  preview,
  rep,
  disabled,
  onClick,
}: {
  side: 'YES' | 'NO';
  label: string;
  preview: BuyPreviewResult | null;
  rep: number;
  disabled: boolean;
  onClick: () => void;
}) {
  const isAgree = side === 'YES';
  return (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'flex-col items-start h-auto py-3 px-3 gap-1',
        isAgree
          ? 'border-success/40 hover:bg-success/10'
          : 'border-destructive/40 hover:bg-destructive/10',
      )}
    >
      <span className={cn('text-sm font-semibold', isAgree ? 'text-success' : 'text-destructive')}>
        {label}
      </span>
      <span className="text-xs font-medium mt-0.5">{rep} rep</span>
      {preview && (
        <span className="text-[11px] font-mono text-muted-foreground">
          +{preview.locked_payout_if_win.toFixed(1)} rep
        </span>
      )}
    </Button>
  );
}
