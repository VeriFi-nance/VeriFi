import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { closePosition, getPositionResolveStatus, triggerPositionResolve, getPositionProof } from '@/lib/api';
import type { PositionItem, AssetItem } from '@/lib/types';
import { useAuthState } from '@/lib/auth';
import ProfitabilityBadge from './ProfitabilityBadge';
import { Link } from 'react-router-dom';
import { truncateAddress } from '@/lib/wallet';
import { RefreshCw, Download } from 'lucide-react';

interface PositionCardProps {
  position: PositionItem;
  assets: AssetItem[];
  onClosed?: () => void;
  onResolved?: (updated: PositionItem) => void;
}

export function PositionCard({ position, assets, onClosed, onResolved }: PositionCardProps) {
  const [closing, setClosing] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [resolveMsg, setResolveMsg] = useState('');
  const [countdown, setCountdown] = useState(0);
  const [downloadingProof, setDownloadingProof] = useState(false);

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
    } catch (e: any) {
      alert(e.message || 'Failed to download proof');
    } finally {
      setDownloadingProof(false);
    }
  };

  const { address: myAddress } = useAuthState();
  const asset = assets.find(a => a.id === position.asset);
  const isAuthor = !!myAddress && myAddress.toLowerCase() === position.author_address.toLowerCase();
  const canResolve = isAuthor && (position.status === 'pending' || position.status === 'active');
  const canClose = isAuthor && position.status === 'active';
  const canCancel = isAuthor && position.status === 'pending';

  // Fetch cooldown on mount (author only, resolvable positions only)
  const fetchCooldown = useCallback(async () => {
    if (!canResolve) return;
    try {
      const rs = await getPositionResolveStatus(position.id);
      setCountdown(rs.remaining_seconds);
    } catch {
      // not authed or position already resolved
    }
  }, [position.id, canResolve]);

  useEffect(() => { fetchCooldown(); }, [fetchCooldown]);

  // Live ticker
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setInterval(() => setCountdown(c => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, [countdown]);

  const fmtCountdown = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  const handleResolve = async () => {
    setResolving(true);
    setResolveMsg('');
    try {
      const res = await triggerPositionResolve(position.id);
      setCountdown(res.remaining_seconds);
      setResolveMsg('Resolution triggered.');
      onResolved?.(res.position);
    } catch (e: any) {
      setResolveMsg(e.message || 'Failed to resolve.');
    } finally {
      setResolving(false);
    }
  };

  const handleClose = async () => {
    const isPending = position.status === 'pending';
    const msg = isPending 
      ? 'Are you sure you want to cancel this pending position?' 
      : 'Are you sure you want to close this position early?';
    if (!confirm(msg)) return;
    setClosing(true);
    try {
      await closePosition(position.id);
      onClosed?.();
    } catch (e: any) {
      alert(e.message);
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
            <ProfitabilityBadge data={position.profitability} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm bg-muted/30 rounded-lg p-3">
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Entry Price</div>
            <div className="font-mono font-medium num">${position.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Stop Loss</div>
            <div className="font-mono text-danger font-medium num">${position.stop_loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Take Profit</div>
            <div className="font-mono text-success font-medium num">${position.take_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <div>
            {position.status === 'pending' && (
              <span>Valid until: {new Date(position.entry_interval).toLocaleString()}</span>
            )}
            {position.status === 'active' && (
              <span>Expires: {new Date(position.lifetime).toLocaleString()}</span>
            )}
            {(['confirmed', 'rejected', 'closed_early', 'expired'] as const).includes(position.status as any) && position.pnl_percentage !== null && (
              <span className={`font-bold num ${position.pnl_percentage > 0 ? 'text-success' : 'text-danger'}`}>
                PnL: {position.pnl_percentage > 0 ? '+' : ''}{position.pnl_percentage.toFixed(2)}%
                {position.exit_price && ` (Exit: $${position.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })})`}
              </span>
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
          {(canResolve || canClose) && (
            <div className="flex flex-col items-end gap-1 shrink-0">
              <div className="flex gap-2">
                {canResolve && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleResolve}
                    disabled={resolving || countdown > 0}
                    className="h-7 text-xs gap-1.5"
                    title={countdown > 0 ? `Next resolve in ${fmtCountdown(countdown)}` : 'Check if SL or TP has been hit'}
                  >
                    <RefreshCw className={`size-3 ${resolving ? 'animate-spin' : ''}`} />
                    {resolving ? 'Checking…' : countdown > 0 ? `Wait ${fmtCountdown(countdown)}` : 'Resolve'}
                  </Button>
                )}
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
              {resolveMsg && (
                <p className={`text-[10px] ${resolveMsg.startsWith('Failed') ? 'text-destructive' : 'text-success'}`}>
                  {resolveMsg}
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
