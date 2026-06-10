import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RepAmount } from '@/components/RepAmount';
import { RepIcon } from '@/components/RepIcon';
import { EnergyIcon } from '@/components/EnergyIcon';
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
        <Label className="inline-flex items-center gap-1 text-xs">
          Stake (10–100 <RepIcon size="xs" />)
        </Label>
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
        Plus a <RepAmount value={2} /> listing fee (burned) and 5% trade burn. Costs 1{' '}
        <EnergyIcon size="xs" className="inline-block align-middle" /> energy.
      </p>
    </div>
  );
}
