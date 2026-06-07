import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { closePosition, getPositionProof } from '@/lib/api';
import type { PositionItem, AssetItem } from '@/lib/types';
import { useAuthState } from '@/lib/auth';
import { Link } from 'react-router-dom';
import { truncateAddress } from '@/lib/wallet';
import { Download, ChevronUp, ChevronDown } from 'lucide-react';
import { PositionPriceChart } from './feed/PositionPriceChart';
import { usePositionChartData } from '@/hooks/usePositionChartData';
import { toast, getMessage } from '@/lib/errors';
import { useConfirm } from './ConfirmDialog';
import { SmartTimestamp } from '@/components/SmartTimestamp';

interface PositionCardProps {
  position: PositionItem;
  assets: AssetItem[];
  onClosed?: () => void;
}

export function PositionCard({ position, assets, onClosed }: PositionCardProps) {
  const [closing, setClosing] = useState(false);
  const [downloadingProof, setDownloadingProof] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const confirm = useConfirm();

  const { data: chartData, interval, setInterval, loading: chartLoading, refetching } = usePositionChartData(
    showChart ? position.id : undefined,
    position.created_at,
    position.lifetime,
    position.status,
  );

  const handleDownloadProof = async () => {
    try {
      setDownloadingProof(true);
      const proof = await getPositionProof(position.id);
      const blob = new Blob([JSON.stringify(proof, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `position-proof-${position.id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      toast.error(getMessage(e, 'Failed to download proof'));
    } finally {
      setDownloadingProof(false);
    }
  };

  const { address: myAddress } = useAuthState();
  const asset = assets.find(a => a.id === position.asset);
  const isAuthor = !!myAddress && myAddress.toLowerCase() === position.author_address.toLowerCase();
  const canClose = isAuthor && position.status === 'active';
  const canCancel = isAuthor && position.status === 'pending';

  const handleClose = async () => {
    const isPending = position.status === 'pending';
    const ok = await confirm({
      title: isPending ? 'Cancel pending position?' : 'Close position early?',
      description: isPending
        ? 'This pending position will be cancelled.'
        : 'This will close the position before its lifetime ends.',
      confirmText: isPending ? 'Cancel position' : 'Close position',
      variant: 'destructive',
    });
    if (!ok) return;
    setClosing(true);
    try {
      await closePosition(position.id);
      toast.success(isPending ? 'Position cancelled.' : 'Position closed.');
      onClosed?.();
    } catch (e: unknown) {
      toast.error(getMessage(e, 'Failed to close position'));
    } finally {
      setClosing(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'confirmed': return 'bg-success/10 text-success border border-success/30';
      case 'rejected': return 'bg-danger/10 text-danger border border-danger/30';
      case 'active': return 'bg-primary/10 text-primary border border-primary/30 animate-pulse';
      case 'pending': return 'bg-muted text-muted-foreground border border-border';
      default: return 'bg-muted text-muted-foreground border border-border';
    }
  };

  const isLong = position.direction.toLowerCase() === 'long';

  return (
    <Card className={`relative overflow-hidden ${position.status === 'active' ? 'border-primary/30' : ''}`}>
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-sm font-bold bg-muted/50">
              {asset?.symbol || `Asset #${position.asset}`}
            </Badge>
            <Badge variant={isLong ? 'success' : 'destructive'} className="uppercase">
              {position.direction}
            </Badge>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider ${getStatusColor(position.status)}`}>
              {position.status.replace('_', ' ')}
            </span>
          </div>

          <div className="flex flex-col items-end gap-1">
            <Link to={`/u/${position.author_username || position.author_address}`} className="text-xs font-mono hover:underline">
              {position.author_username ? `@${position.author_username}` : truncateAddress(position.author_address)}
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm bg-muted/30 rounded-lg p-3">
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Entry Price</div>
            <div className="font-mono font-medium num">${position.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Stop Loss</div>
            <div className="font-mono text-danger font-medium num">
              ${position.stop_loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
              <span className="text-[10px] ml-1 opacity-80">
                ({(isLong ? ((position.stop_loss - position.entry_price) / position.entry_price) * 100 : ((position.entry_price - position.stop_loss) / position.entry_price) * 100).toFixed(2)}%)
              </span>
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Take Profit</div>
            <div className="font-mono text-success font-medium num">
              ${position.take_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
              <span className="text-[10px] ml-1 opacity-80">
                ({(isLong ? ((position.take_profit - position.entry_price) / position.entry_price) * 100 : ((position.entry_price - position.take_profit) / position.entry_price) * 100) > 0 ? '+' : ''}{(isLong ? ((position.take_profit - position.entry_price) / position.entry_price) * 100 : ((position.entry_price - position.take_profit) / position.entry_price) * 100).toFixed(2)}%)
              </span>
            </div>
          </div>
        </div>

        {(['confirmed', 'rejected', 'closed_early', 'expired'] as const).includes(position.status as any) && position.pnl_percentage !== null && (
          <div className={`mt-3 p-3 rounded-lg border flex items-center justify-between text-sm ${position.pnl_percentage > 0 ? 'bg-emerald-500/10 border-emerald-500/30 text-foreground' : 'bg-red-500/10 border-red-500/30 text-foreground'}`}>
            <span className="font-medium">
              {position.author_username ? `@${position.author_username}` : 'User'} <span className={position.pnl_percentage > 0 ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-red-600 dark:text-red-400 font-semibold'}>{position.pnl_percentage > 0 ? 'gained' : 'lost'} {Math.abs(position.pnl_percentage).toFixed(2)}%</span> with this position.
            </span>
            {position.exit_price && (
              <span className="text-xs text-muted-foreground font-mono">
                Exit: ${position.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
              </span>
            )}
          </div>
        )}

        <Button variant="ghost" size="sm" onClick={() => setShowChart(!showChart)} className="w-full mt-2 h-8 text-xs text-muted-foreground flex items-center justify-center gap-1.5 hover:bg-muted/50 transition-colors">
          {showChart ? <><ChevronUp className="size-3.5" /> Hide Chart</> : <><ChevronDown className="size-3.5" /> Show Chart</>}
        </Button>

        {showChart && (
          <div className="mt-2 relative mb-3">
            {chartLoading && !chartData && (
              <div className="h-[320px] flex items-center justify-center text-sm text-muted-foreground rounded-lg border bg-muted/20">
                Loading chart...
              </div>
            )}
            {chartData && (
              <PositionPriceChart
                data={chartData}
                interval={interval}
                onIntervalChange={setInterval}
                refetching={refetching}
              />
            )}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <div>
            {position.status === 'pending' && (
              <span>Valid until: <SmartTimestamp value={position.entry_interval} /></span>
            )}
            {position.status === 'active' && (
              <span>Expires: <SmartTimestamp value={position.lifetime} /></span>
            )}
            {position.status === 'missed' && <span>Entry target not reached.</span>}
            {position.signature && (
              <div className="mt-2">
                <Button variant="outline" size="sm" onClick={handleDownloadProof} disabled={downloadingProof} className="h-6 text-[10px] gap-1">
                  <Download className="size-3" />
                  {downloadingProof ? 'Downloading...' : 'Download Proof'}
                </Button>
              </div>
            )}
          </div>

          {/* Author actions */}
          {(canClose || canCancel) && (
            <div className="flex flex-col items-end gap-1 shrink-0">
              <div className="flex gap-2">
                {canClose && (
                  <Button size="sm" variant="outline" onClick={handleClose} disabled={closing} className="h-7 text-xs">
                    {closing ? 'Closing…' : 'Close Early'}
                  </Button>
                )}
                {canCancel && (
                  <Button size="sm" variant="outline" onClick={handleClose} disabled={closing} className="h-7 text-xs text-destructive hover:text-destructive hover:bg-destructive/10">
                    {closing ? 'Canceling…' : 'Cancel Position'}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
