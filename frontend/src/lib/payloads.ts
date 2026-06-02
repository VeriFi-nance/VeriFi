// ---------------------------------------------------------------------------
// Pure proof-payload builders. Kept free of @scure/@noble/ethers imports so the
// composer modals (mounted eagerly on the feed) can build a payload without
// pulling the heavy crypto bundle into the initial chunk. The actual signing /
// verification still lives in ./crypto and is loaded on demand.
// ---------------------------------------------------------------------------

export function buildClaimPayload(data: {
  asset_symbol: string; author_username: string; direction: string; percentage: number;
  until: string; created_at: string;
}): string {
  const sorted = Object.keys(data)
    .sort()
    .reduce((acc, key) => {
      acc[key] = data[key as keyof typeof data];
      return acc;
    }, {} as Record<string, unknown>);
  return JSON.stringify(sorted);
}

export function buildPositionPayload(data: {
  asset_symbol: string; author_username: string; direction: string; entry_price: number;
  stop_loss: number; take_profit: number; lifetime: string;
  created_at: string;
}): string {
  const sorted = Object.keys(data)
    .sort()
    .reduce((acc, key) => {
      acc[key] = data[key as keyof typeof data];
      return acc;
    }, {} as Record<string, unknown>);
  return JSON.stringify(sorted);
}
