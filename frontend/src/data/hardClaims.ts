import type { HardClaim } from "../types";

export const initialHardClaims: HardClaim[] = [
  {
    id: 1,
    text: "Bitcoin will drop 50% by the end of 2026.",
    asset: "BTC",
    direction: "Drop",
    target: "-50%",
    timeframe: "2026-12-31",
    status: "resolved_failure",
    oraclePrice: 0.9,
    reputationImpact: -15,
    createdAt: "2026-02-01T10:00:00Z"
  },
  {
    id: 2,
    text: "NVDA will increase 10% in 24 hours.",
    asset: "NVDA",
    direction: "Rise",
    target: "+10%",
    timeframe: "2026-03-01T18:00:00Z",
    status: "resolved_success",
    oraclePrice: 1.12,
    reputationImpact: 12,
    createdAt: "2026-02-10T09:30:00Z"
  },
  {
    id: 3,
    text: "ETH will rise 30% by mid-April 2026.",
    asset: "ETH",
    direction: "Rise",
    target: "+30%",
    timeframe: "2026-04-15",
    status: "pending",
    oraclePrice: null,
    reputationImpact: 0,
    createdAt: "2026-02-15T14:20:00Z"
  }
];

