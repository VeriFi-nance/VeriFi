import { useEffect, useState } from 'react';
import { getProfileStats } from '@/lib/api';
import { useAuthState } from '@/lib/auth';
import { cn } from '@/lib/utils';
import { RepIcon } from '@/components/RepIcon';
import { EnergyIcon } from '@/components/EnergyIcon';

interface Props {
  /** Bump this counter to force a refetch after a market action. */
  refreshKey?: number;
  className?: string;
  hideRepOnMobile?: boolean;
  hideEnergyOnMobile?: boolean;
}

export function EnergyMeter({
  refreshKey,
  className,
  hideRepOnMobile = false,
  hideEnergyOnMobile = false,
}: Props) {
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
        <span className={cn('flex items-center gap-1 font-mono', hideRepOnMobile && 'hidden sm:inline')}>
          <RepIcon size="xs" />
          {rep.toFixed(0)}
        </span>
      )}
      <span className={cn('flex items-center gap-1 font-mono', hideEnergyOnMobile && 'hidden sm:flex')}>
        <EnergyIcon size="xs" />
        {Math.floor(energy)}
      </span>
    </div>
  );
}
