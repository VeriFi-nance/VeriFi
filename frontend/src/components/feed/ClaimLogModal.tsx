import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { CalendarDays, CheckCircle2, Clock, Info, XCircle } from 'lucide-react';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { truncateAddress } from '../HardClaimCard';

interface ClaimLogModalProps {
  isOpen: boolean;
  onClose: () => void;
  claim: HardClaimItem | null;
  assets: AssetItem[];
}

export function ClaimLogModal({ isOpen, onClose, claim, assets }: ClaimLogModalProps) {
  if (!claim) return null;

  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';

  // Sort events chronologically
  const events = [...(claim.events || [])].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <span
              className={`size-2.5 rounded-full shrink-0 ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}
            />
            {assetSymbol} {isBullish ? '▲' : '▼'} {claim.percentage.toFixed(1)}%
          </DialogTitle>
        </DialogHeader>

        <div className="mt-4 space-y-6 relative before:absolute before:inset-y-0 before:left-[15px] before:w-px before:bg-border">
          {/* Fallback creation event if not in DB */}
          {(!events.length || !events.some(e => e.event_type === 'creation')) && (
            <div className="relative pl-10">
              <div className="absolute left-0 top-1.5 flex size-8 -translate-x-1.5 items-center justify-center rounded-full bg-background border border-border shadow-sm">
                <Clock className="size-3.5 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Claim Created</p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <CalendarDays className="size-3" />
                  <time dateTime={claim.created_at}>
                    {new Date(claim.created_at).toLocaleString()}
                  </time>
                </div>
                {claim.author_address && (
                  <p className="text-xs text-muted-foreground">
                    Author: <span className="font-mono">{truncateAddress(claim.author_address)}</span>
                  </p>
                )}
                <Badge variant="outline" className="mt-1 font-mono text-[10px] uppercase">
                  Target Date: {claim.until}
                </Badge>
              </div>
            </div>
          )}

          {events.map((event, idx) => {
            const isCreation = event.event_type === 'creation';
            const isResolution = event.event_type === 'resolution';

            return (
              <div key={event.id || idx} className="relative pl-10">
                <div className="absolute left-0 top-1.5 flex size-8 -translate-x-1.5 items-center justify-center rounded-full bg-background border border-border shadow-sm">
                  {isCreation ? (
                    <Clock className="size-3.5 text-muted-foreground" />
                  ) : isResolution ? (
                    claim.status === 'confirmed' ? (
                      <CheckCircle2 className="size-4 text-emerald-500" />
                    ) : claim.status === 'rejected' ? (
                      <XCircle className="size-4 text-red-500" />
                    ) : (
                      <Info className="size-3.5 text-primary" />
                    )
                  ) : (
                    <Info className="size-3.5 text-muted-foreground" />
                  )}
                </div>

                <div className="space-y-2">
                  <div>
                    <h4 className="text-sm font-medium">
                      {isCreation && 'Claim Created'}
                      {isResolution && 'Claim Resolved'}
                      {!isCreation && !isResolution && 'Price Check'}
                    </h4>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                      <CalendarDays className="size-3" />
                      <time dateTime={event.timestamp}>
                        {new Date(event.timestamp).toLocaleString()}
                      </time>
                    </div>
                    {isCreation && claim.author_address && (
                      <p className="space-x-1 text-xs text-muted-foreground">
                        <span>Author:</span>
                        <span className="font-mono">{truncateAddress(claim.author_address)}</span>
                      </p>
                    )}
                  </div>

                  {/* Resolution Details */}
                  {isResolution && event.details && (
                    <div className="rounded-md border p-3 space-y-2 bg-muted/40 text-xs">
                      {event.details.evaluation_reason && (
                        <p className="font-medium text-foreground">{event.details.evaluation_reason}</p>
                      )}
                      
                      {event.details.prices && (
                        <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t">
                          <div>
                            <span className="text-muted-foreground">Ref Price: </span>
                            <span className="font-mono">${event.details.prices.reference}</span>
                            {event.details.prices.reference_url && (
                              <a href={event.details.prices.reference_url} target="_blank" rel="noreferrer" 
                                 className="block text-[10px] text-primary truncate max-w-[120px] hover:underline" title={event.details.prices.reference_url}>
                                source
                              </a>
                            )}
                          </div>
                          <div>
                            <span className="text-muted-foreground">Due Price: </span>
                            <span className="font-mono">${event.details.prices.due}</span>
                            {event.details.prices.due_url && (
                              <a href={event.details.prices.due_url} target="_blank" rel="noreferrer"
                                 className="block text-[10px] text-primary truncate max-w-[120px] hover:underline" title={event.details.prices.due_url}>
                                source
                              </a>
                            )}
                          </div>
                        </div>
                      )}

                      {event.details.computed_change_pct !== undefined && (
                        <div className="mt-2 pt-2 border-t flex justify-between items-center">
                          <span className="text-muted-foreground">Calculated Change:</span>
                          <Badge variant="secondary" className="font-mono">
                            {event.details.computed_change_pct > 0 ? '+' : ''}
                            {event.details.computed_change_pct}%
                          </Badge>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
