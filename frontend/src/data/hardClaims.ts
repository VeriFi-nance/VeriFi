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
  },
  {
    id: 4,
    text: "Solana is heavily undervalued. Predicting a 200% surge before Q3 2026.",
    asset: "SOL",
    direction: "Rise",
    target: "+200%",
    timeframe: "2026-09-30",
    status: "pending",
    oraclePrice: null,
    reputationImpact: 0,
    createdAt: "2026-02-18T11:45:00Z"
  },
  {
    id: 5,
    text: "AAPL will slightly drop after their next earnings report due to weak hardware sales.",
    asset: "AAPL",
    direction: "Drop",
    target: "-5%",
    timeframe: "2026-05-10",
    status: "pending",
    oraclePrice: null,
    reputationImpact: 0,
    createdAt: "2026-02-20T08:15:00Z"
  },
  {
    id: 6,
    text: "TSLA will drop below $150 by end of the month.",
    asset: "TSLA",
    direction: "Drop",
    target: "< $150",
    timeframe: "2026-02-28",
    status: "resolved_failure",
    oraclePrice: 165.20,
    reputationImpact: -8,
    createdAt: "2026-01-25T16:00:00Z"
  },
  {
    id: 7,
    text: "DOGE to $1. The memes are back in full force.",
    asset: "DOGE",
    direction: "Rise",
    target: "$1.00",
    timeframe: "2026-12-31",
    status: "pending",
    oraclePrice: null,
    reputationImpact: 0,
    createdAt: "2026-02-22T21:30:00Z"
  },
  {
    id: 8,
    text: "S&P 500 will hit 6000 points this year.",
    asset: "SPY",
    direction: "Rise",
    target: "6000",
    timeframe: "2026-12-31",
    status: "pending",
    oraclePrice: null,
    reputationImpact: 0,
    createdAt: "2026-02-23T09:00:00Z"
  }
];

