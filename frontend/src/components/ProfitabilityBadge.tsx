import { useState } from "react";

interface ProfitabilityData {
  pnl_7d: number;
  pnl_30d: number;
  pnl_all: number;
  updated_at: string | null;
}

interface Props {
  data?: ProfitabilityData | null;
  className?: string;
}

type Timeframe = "7D" | "30D" | "ALL";

export default function ProfitabilityBadge({ data, className = "" }: Props) {
  const [timeframe, setTimeframe] = useState<Timeframe>("30D");

  if (!data || data.updated_at === null) {
    return (
      <span className={`inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800 ${className}`}>
        No PnL Data
      </span>
    );
  }

  let pnl = 0;
  if (timeframe === "7D") pnl = data.pnl_7d;
  else if (timeframe === "30D") pnl = data.pnl_30d;
  else pnl = data.pnl_all;

  const cycleTimeframe = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (timeframe === "7D") setTimeframe("30D");
    else if (timeframe === "30D") setTimeframe("ALL");
    else setTimeframe("7D");
  };

  const isPositive = pnl > 0;
  const isNegative = pnl < 0;
  const sign = isPositive ? "+" : "";
  const colorClass = isPositive
    ? "bg-green-100 text-green-800"
    : isNegative
    ? "bg-red-100 text-red-800"
    : "bg-gray-100 text-gray-800";

  return (
    <button
      onClick={cycleTimeframe}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors hover:opacity-80 focus:outline-none ${colorClass} ${className}`}
      title={`Profitability over ${timeframe === "ALL" ? "All Time" : timeframe}. Click to toggle.`}
    >
      <span className="mr-1 font-bold">{timeframe}</span>
      {sign}{pnl.toFixed(2)}%
    </button>
  );
}
