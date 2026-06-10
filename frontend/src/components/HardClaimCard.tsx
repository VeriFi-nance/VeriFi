import { useState } from 'react';
import { ArrowDown, ArrowUp, Download, FileCheck2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AttachmentRow } from '@/components/AttachmentRow';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { getClaimProof, getMarket, buyShares } from '@/lib/api';
import { getClaimWindowProgress, getFeedClaimTagLabel, getHardClaimDisplay, getHardClaimType, isClaimPastDue } from '@/lib/claims';
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
  const progress = getClaimWindowProgress(claim.created_at, claim.until);

  const timelinePct = Math.min(100, Math.max(0, isConfirmed || isRejected ? 100 : progress));
  const timelineLabel = `${Math.round(timelinePct)}%`;
  const timelineBarClass = isConfirmed
    ? 'bg-emerald-500'
    : isRejected
      ? 'bg-red-500'
      : pastDue
        ? 'bg-amber-500'
        : 'bg-blue-400';
  const marketClosed = claim.status !== 'undetermined';

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
      const market = await getMarket(claim.id);
      if (market.resolved || market.claim_status !== 'undetermined') {
        toast.error('This market is already resolved.');
        return;
      }

      const label = side === 'YES' ? 'Agree' : 'Disagree';
      const ok = await confirm({
        title: `${label} with ${market.trader_stake} rep?`,
        description: `You will buy ${label} shares on this claim's reputation market. Your stake is locked until the claim resolves.`,
        confirmText: `Buy ${label}`,
      });
      if (!ok) return;

      await buyShares(claim.id, side);
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
      badge={tag.label}
      badgeVariant={tag.variant}
      summary={<span className="truncate">{display.summary}</span>}
      progress={{
        value: timelinePct,
        label: timelineLabel,
        className: timelineBarClass,
      }}
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
            disabled={busySide !== null || marketClosed}
            title="Buy Agree shares"
            aria-label="Buy Agree shares"
            onClick={(e) => handleBuy(e, 'YES')}
            className="size-8 rounded-md text-success hover:bg-success/10 hover:text-success disabled:opacity-35"
          >
            {busySide === 'YES' ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            disabled={busySide !== null || marketClosed}
            title="Buy Disagree shares"
            aria-label="Buy Disagree shares"
            onClick={(e) => handleBuy(e, 'NO')}
            className="size-8 rounded-md text-destructive hover:bg-destructive/10 hover:text-destructive disabled:opacity-35"
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
        isConfirmed && 'border-emerald-500/60 shadow-sm',
        isRejected && 'border-red-500/60 opacity-80',
        !isConfirmed && !isRejected && pastDue && 'border-amber-500/50',
        !isConfirmed && !isRejected && !pastDue && 'border-border hover:shadow-sm',
      )}
    />
  );
}
