export type ClaimStatus = "pending" | "resolved_success" | "resolved_failure";

export interface HardClaim {
  id: number;
  text: string;
  asset: string;
  direction: string;
  target: string;
  timeframe: string;
  status: ClaimStatus;
  oraclePrice?: number | null;
  reputationImpact: number;
  createdAt: string;
}

