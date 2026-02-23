import React, { useState } from "react";
import type { HardClaim } from "../types";

interface ResolutionsScreenProps {
  claims: HardClaim[];
  onUpdateClaims: (updated: HardClaim[]) => void;
}

const ResolutionsScreen: React.FC<ResolutionsScreenProps> = ({ claims, onUpdateClaims }) => {
  const [selectedId, setSelectedId] = useState<number | null>(claims[0]?.id ?? null);

  const handleResolvePending = () => {
    const updated = claims.map((c) => {
      if (c.status === "pending") {
        return {
          ...c,
          status: "resolved_failure",
          oraclePrice: c.oraclePrice ?? 0.9,
          reputationImpact: c.reputationImpact || -10
        };
      }
      return c;
    });
    onUpdateClaims(updated);
  };

  const selectedClaim = claims.find((c) => c.id === selectedId) ?? null;

  return (
    <>
      <div className="box">
        <h1>Hard Claim Resolutions</h1>
        <p>List of hard claims and their oracle-based resolution status.</p>
      </div>

      <div className="box">
        <h2>Hard Claims</h2>
        <button onClick={handleResolvePending}>Resolve pending claims</button>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Asset</th>
              <th>Direction</th>
              <th>Target</th>
              <th>Timeframe</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr
                key={c.id}
                className={c.id === selectedId ? "selected" : ""}
                onClick={() => setSelectedId(c.id)}
              >
                <td>{c.id}</td>
                <td>{c.asset}</td>
                <td>{c.direction}</td>
                <td>{c.target}</td>
                <td>{c.timeframe}</td>
                <td>
                  {c.status === "pending"
                    ? "Pending"
                    : c.status === "resolved_success"
                    ? "Resolved (Success)"
                    : "Resolved (Failure)"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="box">
        <h2>Resolution Details</h2>
        {selectedClaim ? (
          <>
            <p>
              <strong>Claim:</strong> {selectedClaim.asset} {selectedClaim.direction} {selectedClaim.target} by{" "}
              {selectedClaim.timeframe}
            </p>
            <p>
              <strong>Status:</strong>{" "}
              {selectedClaim.status === "pending"
                ? "Pending"
                : selectedClaim.status === "resolved_success"
                ? "Resolved (Success)"
                : "Resolved (Failure)"}
            </p>
            <p>
              <strong>Oracle price at resolution:</strong>{" "}
              {selectedClaim.oraclePrice != null ? selectedClaim.oraclePrice : "Not fetched yet"}
            </p>
            <p>
              <strong>Reputation impact:</strong>{" "}
              {selectedClaim.reputationImpact >= 0
                ? `+${selectedClaim.reputationImpact}`
                : selectedClaim.reputationImpact}
            </p>
            <h3>Timeline</h3>
            <ul>
              <li>Claim posted: {new Date(selectedClaim.createdAt).toLocaleString()}</li>
              <li>Resolution scheduled at: {selectedClaim.timeframe}</li>
              <li>Oracle data fetched: when claim leaves Pending state.</li>
              <li>Outcome applied to reputation: shown above as reputation impact.</li>
            </ul>
          </>
        ) : (
          <p>No claim selected.</p>
        )}
      </div>
    </>
  );
};

export default ResolutionsScreen;

