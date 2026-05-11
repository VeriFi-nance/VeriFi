import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { closePosition } from '@/lib/api';
import type { PositionItem, AssetItem } from '@/lib/types';
import { loadAddress } from '@/lib/auth';
import ProfitabilityBadge from './ProfitabilityBadge';
import { Link } from 'react-router-dom';
import { truncateAddress } from './HardClaimCard';

interface PositionCardProps {
  position: PositionItem;
  assets: AssetItem[];
  onClosed?: () => void;
}

export function PositionCard({ position, assets, onClosed }: PositionCardProps) {
  const [closing, setClosing] = useState(false);
  const myAddress = loadAddress();
  const asset = assets.find(a => a.id === position.asset);
  
  const isAuthor = myAddress?.toLowerCase() === position.author_address.toLowerCase();
  
  const handleClose = async () => {
    if (!confirm('Are you sure you want to close this position early?')) return;
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
      case 'confirmed': return 'bg-green-100 text-green-800';
      case 'rejected': return 'bg-red-100 text-red-800';
      case 'active': return 'bg-blue-100 text-blue-800 animate-pulse';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const isLong = position.direction.toLowerCase() === 'long';

  return (
    <Card className={`relative overflow-hidden ${position.status === 'active' ? 'border-blue-200 shadow-sm shadow-blue-100' : ''}`}>
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
            <Link to={`/app/user/${position.author_address}`} className="text-xs font-mono hover:underline">
              {truncateAddress(position.author_address)}
            </Link>
            <ProfitabilityBadge data={position.profitability} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-sm bg-muted/30 rounded-lg p-3">
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Entry Price</div>
            <div className="font-mono font-medium">${position.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Stop Loss</div>
            <div className="font-mono text-destructive font-medium">${position.stop_loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs uppercase tracking-wider">Take Profit</div>
            <div className="font-mono text-success font-medium">${position.take_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <div>
            {position.status === 'pending' && (
              <span>Valid until: {new Date(position.entry_interval).toLocaleString()}</span>
            )}
            {position.status === 'active' && (
              <span>Expires: {new Date(position.lifetime).toLocaleString()}</span>
            )}
            {(position.status === 'confirmed' || position.status === 'rejected' || position.status === 'closed_early' || position.status === 'expired') && position.pnl_percentage !== null && (
              <span className={`font-bold ${position.pnl_percentage > 0 ? 'text-green-600' : 'text-red-600'}`}>
                PnL: {position.pnl_percentage > 0 ? '+' : ''}{position.pnl_percentage.toFixed(2)}%
                {position.exit_price && ` (Exit: $${position.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })})`}
              </span>
            )}
            {position.status === 'missed' && (
              <span>Entry target not reached.</span>
            )}
          </div>
          
          {isAuthor && position.status === 'active' && (
            <Button size="sm" variant="outline" onClick={handleClose} disabled={closing} className="h-7 text-xs">
              {closing ? 'Closing...' : 'Close Early'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
