import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import type { PositionDraft } from './PositionWizard';

interface PositionStepReviewProps {
  value: PositionDraft;
  onChange: (patch: Partial<PositionDraft>) => void;
  /** Validation error surfaced by the wizard when "Attach Position" fails. */
  error?: string;
}

export function PositionStepReview({ value, onChange, error }: PositionStepReviewProps) {
  const isLong = value.direction === 'long';

  return (
    <div className="space-y-4 animate-in slide-in-from-right-2 fade-in">
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-semibold">Review & Deadlines</Label>
          <Badge variant={isLong ? 'default' : 'destructive'} className="text-[10px]">
            {isLong ? 'LONG ↑' : 'SHORT ↓'}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Confirm your levels and set the expiration deadlines.
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="py-2">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-3 gap-2">
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground uppercase">Entry</Label>
          <Input 
            type="number" 
            step="any" 
            className="h-8 text-xs font-semibold num"
            value={value.entryPrice}
            onChange={(e) => onChange({ entryPrice: e.target.value })}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground uppercase">Take Profit</Label>
          <Input 
            type="number" 
            step="any" 
            className="h-8 text-xs font-semibold num text-green-500"
            value={value.takeProfit}
            onChange={(e) => onChange({ takeProfit: e.target.value })}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground uppercase">Stop Loss</Label>
          <Input 
            type="number" 
            step="any" 
            className="h-8 text-xs font-semibold num text-red-500"
            value={value.stopLoss}
            onChange={(e) => onChange({ stopLoss: e.target.value })}
          />
        </div>
      </div>

      <div className="space-y-3 pt-2">
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold">Entry Interval</Label>
          <p className="text-[10px] text-muted-foreground leading-tight">
            How long this position suggestion is valid for new entries.
          </p>
          <Input
            type="datetime-local"
            className="h-9 text-sm"
            value={value.entryInterval}
            onChange={(e) => onChange({ entryInterval: e.target.value })}
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs font-semibold">Absolute Lifetime</Label>
          <p className="text-[10px] text-muted-foreground leading-tight">
            If active but TP/SL not hit by this time, the position is force closed at current price.
          </p>
          <Input
            type="datetime-local"
            className="h-9 text-sm"
            value={value.lifetime}
            onChange={(e) => onChange({ lifetime: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}
