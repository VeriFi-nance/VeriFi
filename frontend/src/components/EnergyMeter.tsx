import { useEffect, useState } from 'react';
import { Zap } from 'lucide-react';
import { getProfileStats } from '@/lib/api';
import { useAuthState } from '@/lib/auth';
import { cn } from '@/lib/utils';

interface Props {
  /** Bump this counter to force a refetch after a market action. */
  refreshKey?: number;
  className?: string;
  hideRepOnMobile?: boolean;
}

export function EnergyMeter({ refreshKey, className, hideRepOnMobile = false }: Props) {
  const [energy, setEnergy] = useState<number | null>(null);
  const [rep, setRep] = useState<number | null>(null);
  const [localRefreshKey, setLocalRefreshKey] = useState(0);
  const { address } = useAuthState();

  useEffect(() => {
    const refresh = () => setLocalRefreshKey((key) => key + 1);
    window.addEventListener('energy-updated', refresh);
    return () => window.removeEventListener('energy-updated', refresh);
  }, []);

  useEffect(() => {
    if (!address) return;
    let cancelled = false;
    getProfileStats(address)
      .then((p) => {
        if (cancelled) return;
        setEnergy(p.energy ?? null);
        setRep(p.rep ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [address, refreshKey, localRefreshKey]);

  if (!address || energy == null) return null;

  return (
    <div className={cn('flex items-center gap-3 text-xs', className)}>
      {rep != null && (
        <span className={cn('font-mono', hideRepOnMobile && 'hidden sm:inline')}>
          <span className="text-muted-foreground">rep</span> {rep.toFixed(0)}
        </span>
      )}
      <span className="flex items-center gap-1 font-mono">
        <Zap className="size-3.5 text-amber-500" />
        {Math.floor(energy)}
      </span>
    </div>
  );
}
