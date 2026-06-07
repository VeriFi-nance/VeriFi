import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getProfileStats } from '@/lib/api';
import { useAuthState } from '@/lib/auth';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { ClaimDraft } from './types';
import { LISTING_FEE, MIN_STAKE, MAX_STAKE } from './types';
import { AlertCircle } from 'lucide-react';

interface StepStakeProps {
  value: ClaimDraft;
  onChange: (patch: Partial<ClaimDraft>) => void;
  onComplete: () => void;
  onBack: () => void;
}

export function StepStake({ value, onChange, onComplete, onBack }: StepStakeProps) {
  const { address } = useAuthState();
  const [rep, setRep] = useState<number | null>(null);
  const [energy, setEnergy] = useState<number | null>(null);

  useEffect(() => {
    if (address) {
      getProfileStats(address).then((stats) => {
        setRep(stats.rep ?? null);
        setEnergy(stats.energy ?? null);
      }).catch(console.error);
    }
  }, [address]);

  const stake = parseFloat(value.stakeRep);
  const total = stake + LISTING_FEE;
  const inRange = !isNaN(stake) && stake >= MIN_STAKE && stake <= MAX_STAKE;
  const cantAfford = inRange && rep !== null && rep < total;
  const noEnergy = energy !== null && energy < 1;
  const isValid = inRange && !cantAfford && !noEnergy;

  // Real-time warning so the user is told *before* hitting submit (not at the end).
  const warning = isNaN(stake)
    ? null
    : !inRange
      ? `Stake must be between ${MIN_STAKE} and ${MAX_STAKE} rep.`
      : cantAfford
        ? `Not enough rep: this needs ${total} rep (stake ${stake} + ${LISTING_FEE} listing fee) but you have ${rep !== null ? Math.floor(rep) : 0}.`
        : noEnergy
          ? 'Not enough energy: creating a claim costs 1 energy.'
          : null;

  return (
    <div className="space-y-5 animate-in slide-in-from-right-2 fade-in">
      <div className="space-y-1">
        <Label className="text-sm font-semibold">Reputation Stake</Label>
        <p className="text-xs text-muted-foreground">
          Stake your reputation on this claim. The more you stake, the more you stand to gain (or lose).
        </p>
      </div>

      <div className="rounded-lg border bg-card p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Your Current Rep</span>
          <span className="font-mono text-sm font-semibold">{rep !== null ? rep.toFixed(0) : '...'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Your Energy</span>
          <span className="font-mono text-sm font-semibold">{energy !== null ? energy.toFixed(0) : '...'} ⚡</span>
        </div>

        <div className="space-y-2 pt-2 border-t">
          <Label className="text-xs font-semibold">Stake Amount (10 - 100 rep)</Label>
          <Input
            type="number"
            min={10}
            max={100}
            step={1}
            value={value.stakeRep}
            onChange={(e) => onChange({ stakeRep: e.target.value })}
            className="h-10 text-base num"
          />
        </div>

        <div className="rounded-md bg-muted/50 p-3 flex gap-2 items-start text-xs text-muted-foreground">
          <AlertCircle className="size-4 shrink-0 mt-0.5" />
          <div className="leading-snug">
            Creator side is auto-set to <span className="font-semibold text-success">YES</span>.<br/>
            There is a 2-rep listing fee (burned) and a 5% trade burn. This action costs 1 energy.
          </div>
        </div>
      </div>

      {warning && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-2 pt-2">
        <Button variant="outline" className="w-1/3" onClick={onBack}>
          Back
        </Button>
        <Button 
          className="w-2/3" 
          disabled={!isValid} 
          onClick={onComplete}
        >
          Attach Claim
        </Button>
      </div>
    </div>
  );
}
