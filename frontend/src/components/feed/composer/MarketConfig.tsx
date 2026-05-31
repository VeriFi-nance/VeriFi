import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { ClaimDraft } from './types';

interface MarketConfigProps {
  value: Pick<ClaimDraft, 'stakeRep'>;
  onChange: (patch: Partial<ClaimDraft>) => void;
}

export function MarketConfig({ value, onChange }: MarketConfigProps) {
  return (
    <div className="rounded-md border border-border bg-background/60 p-3 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Reputation market (Model G)
      </p>
      <p className="text-[11px] text-muted-foreground">
        Creator side is auto-set to <span className="font-semibold text-success">YES</span>.
      </p>
      <div className="space-y-1">
        <Label className="text-xs">Stake (10–100 rep)</Label>
        <Input
          type="number"
          min={10}
          max={100}
          step={1}
          value={value.stakeRep}
          onChange={(e) => onChange({ stakeRep: e.target.value })}
          className="h-8 text-sm num"
        />
      </div>
      <p className="text-[10px] text-muted-foreground leading-snug">
        Plus a 2-rep listing fee (burned) and 5% trade burn. Costs 2 energy.
      </p>
    </div>
  );
}
