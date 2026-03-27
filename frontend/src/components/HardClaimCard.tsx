import { useNavigate } from 'react-router-dom';
import type { HardClaimItem, AssetItem } from '@/lib/types';

export function truncateAddress(addr: string | null) {
  if (!addr) return 'Unknown';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const navigate = useNavigate();
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';

  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';

  const cardClass = isConfirmed
    ? 'border-green-500 hover:bg-muted/30'
    : isRejected
    ? 'border-red-500 hover:bg-muted/30 opacity-60'
    : 'border-border hover:bg-muted/30';

  const directionClass = isBullish ? 'text-green-500' : 'text-red-500';

  const statusClass = isConfirmed
    ? 'text-green-500 font-semibold'
    : isRejected
    ? 'text-red-500 font-semibold'
    : 'text-muted-foreground font-semibold';

  return (
    <div className={`flex items-center gap-4 rounded-lg border-2 px-4 py-3 transition-colors ${cardClass}`}>
      <div className={`flex flex-col items-center justify-center min-w-[52px] gap-0.5 ${directionClass}`}>
        <span className="text-xl leading-none">{isBullish ? '▲' : '▼'}</span>
        <span className="text-sm font-bold leading-none">{assetSymbol}</span>
        <span className="text-xs font-semibold leading-none">{claim.percentage}%</span>
      </div>

      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium leading-snug line-clamp-2 ${isRejected ? 'text-muted-foreground' : ''}`}>
          {claim.text}
        </p>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
          {claim.author_address ? (
            <button
              onClick={() => navigate(`/app/user/${claim.author_address}`)}
              className="font-mono hover:underline"
            >
              {truncateAddress(claim.author_address)}
            </button>
          ) : (
            <span className="font-mono">Anonymous</span>
          )}
          <span>·</span>
          <span>{new Date(claim.created_at).toLocaleDateString()}</span>
          <span>·</span>
          <span>until {new Date(claim.until).toLocaleDateString()}</span>
        </div>
      </div>

      <span className={`text-xs capitalize shrink-0 ${statusClass}`}>
        {claim.status}
      </span>
    </div>
  );
}
