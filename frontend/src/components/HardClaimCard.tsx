import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, Download, FileCheck2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AttachmentRow } from '@/components/AttachmentRow';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { getClaimProof, getMarket, buyShares } from '@/lib/api';
import { getFeedClaimTagLabel, getHardClaimDisplay, getHardClaimType, isClaimPastDue } from '@/lib/claims';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import { useConfirm } from '@/components/ConfirmDialog';
import { toast, getMessage } from '@/lib/errors';

function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Compact expanded claim row — matches collapsed feed tag + window timeline. */
export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const auth = useAuthState();
  const openLogin = useOpenLogin();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [busySide, setBusySide] = useState<'YES' | 'NO' | null>(null);
  const [downloadingProof, setDownloadingProof] = useState(false);

  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const tag = getFeedClaimTagLabel(claim, asset);
  const display = getHardClaimDisplay(
    {
      direction: claim.direction,
      percentage: claim.percentage,
      until: claim.until,
      claim_type: getHardClaimType(claim),
      asset_obj: claim.asset_obj,
    },
    assetSymbol,
  );
  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';
  const pastDue = isClaimPastDue(claim);
  const marketClosed = claim.status !== 'undetermined';
  const marketQueryKey = ['claim-market', claim.id] as const;
  const { data: marketState } = useQuery({
    queryKey: marketQueryKey,
    queryFn: () => getMarket(claim.id),
    enabled: auth.authenticated && !marketClosed,
    staleTime: 30_000,
    retry: false,
  });
  const activeSide = marketState?.your_stake?.side ?? null;

  async function handleDownloadProof(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      setDownloadingProof(true);
      const proof = await getClaimProof(claim.id);
      downloadJson(`claim-proof-${claim.id}.json`, proof);
    } catch (err: unknown) {
      toast.error(getMessage(err, 'Failed to download proof'));
    } finally {
      setDownloadingProof(false);
    }
  }

  async function handleBuy(e: React.MouseEvent, side: 'YES' | 'NO') {
    e.preventDefault();
    e.stopPropagation();

    if (!auth.authenticated) {
      openLogin();
      return;
    }
    if (marketClosed) {
      toast.error('This claim has resolved, so reputation staking is closed.');
      return;
    }

    try {
      setBusySide(side);
      const market = marketState ?? await getMarket(claim.id);
      queryClient.setQueryData(marketQueryKey, market);
      if (market.resolved || market.claim_status !== 'undetermined') {
        toast.error('This market is already resolved.');
        return;
      }
      if (market.your_stake) {
        toast.error(`You already bought ${market.your_stake.side === 'YES' ? 'Agree' : 'Disagree'} shares.`);
        return;
      }

      const label = side === 'YES' ? 'Agree' : 'Disagree';
      const ok = await confirm({
        title: `${label} with ${market.trader_stake} rep?`,
        description: `You will buy ${label} shares on this claim's reputation market. Your stake is locked until the claim resolves.`,
        confirmText: `Buy ${label}`,
      });
      if (!ok) return;

      const result = await buyShares(claim.id, side);
      queryClient.setQueryData(marketQueryKey, result.market);
      toast.success(`${label} shares bought.`);
    } catch (err: unknown) {
      toast.error(getMessage(err, 'Could not buy market shares'));
    } finally {
      setBusySide(null);
    }
  }

  return (
    <AttachmentRow
      icon={<FileCheck2 className="size-4" />}
      title={assetSymbol}
      titleTone={display.isBullish ? 'text-emerald-400' : 'text-rose-400'}
      meta={<span className={cn(display.isBullish ? 'text-emerald-400' : 'text-rose-400')}>{tag.label}</span>}
      badge="Claim"
      badgeVariant="outline"
      summary={<span className="truncate">{display.summary}</span>}
      right={
        <span
          className={cn(
            'text-[10px] font-semibold uppercase tracking-wide',
            isConfirmed ? 'text-success' : isRejected ? 'text-destructive' : pastDue ? 'text-amber-500' : 'text-muted-foreground',
          )}
        >
          {isConfirmed ? 'Confirmed' : isRejected ? 'Rejected' : pastDue ? 'Past due' : 'Open'}
        </span>
      }
      actions={
        <>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            disabled={busySide !== null || marketClosed || activeSide !== null}
            aria-pressed={activeSide === 'YES'}
            title="Buy Agree shares"
            aria-label="Buy Agree shares"
            onClick={(e) => handleBuy(e, 'YES')}
            className={cn(
              'size-8 rounded-md text-success hover:bg-success/10 hover:text-success',
              activeSide === 'YES'
                ? 'bg-success/15 ring-1 ring-success/40 disabled:opacity-100'
                : 'disabled:opacity-35',
            )}
          >
            {busySide === 'YES' ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            disabled={busySide !== null || marketClosed || activeSide !== null}
            aria-pressed={activeSide === 'NO'}
            title="Buy Disagree shares"
            aria-label="Buy Disagree shares"
            onClick={(e) => handleBuy(e, 'NO')}
            className={cn(
              'size-8 rounded-md text-destructive hover:bg-destructive/10 hover:text-destructive',
              activeSide === 'NO'
                ? 'bg-destructive/15 ring-1 ring-destructive/40 disabled:opacity-100'
                : 'disabled:opacity-35',
            )}
          >
            {busySide === 'NO' ? <Loader2 className="size-4 animate-spin" /> : <ArrowDown className="size-4" />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            disabled={downloadingProof || !claim.signature}
            title={claim.signature ? 'Download proof' : 'No proof available'}
            aria-label="Download claim proof"
            onClick={handleDownloadProof}
            className="size-8 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-35"
          >
            {downloadingProof ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
          </Button>
        </>
      }
      className={cn(
        isConfirmed && 'border-emerald-500/35',
        isRejected && 'border-red-500/35 opacity-80',
        !isConfirmed && !isRejected && pastDue && 'border-amber-500/35',
      )}
    />
  );
}
