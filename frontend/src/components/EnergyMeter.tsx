import { useEffect, useState } from 'react';
import { Zap } from 'lucide-react';
import { getProfileStats } from '@/lib/api';
import { loadAddress } from '@/lib/auth';

interface Props {
  /** Bump this counter to force a refetch after a market action. */
  refreshKey?: number;
}

export function EnergyMeter({ refreshKey }: Props) {
  const [energy, setEnergy] = useState<number | null>(null);
  const [cap, setCap] = useState<number>(4);
  const [rep, setRep] = useState<number | null>(null);
  const address = loadAddress();

  useEffect(() => {
    if (!address) return;
    let cancelled = false;
    getProfileStats(address)
      .then((p) => {
        if (cancelled) return;
        setEnergy(p.energy ?? null);
        setCap(p.energy_cap ?? 4);
        setRep(p.rep ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [address, refreshKey]);

  if (!address || energy == null) return null;

  return (
    <div className="flex items-center gap-3 text-xs">
      {rep != null && (
        <span className="font-mono">
          <span className="text-muted-foreground">rep</span> {rep.toFixed(0)}
        </span>
      )}
      <span className="flex items-center gap-1 font-mono">
        <Zap className="size-3.5 text-amber-500" />
        {Math.floor(energy)}/{cap}
      </span>
    </div>
  );
}
