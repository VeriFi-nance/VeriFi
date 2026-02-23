import React from "react";
import type { HardClaim } from "../types";

interface ProfileScreenProps {
  claims: HardClaim[];
}

const ProfileScreen: React.FC<ProfileScreenProps> = ({ claims }) => {
  const totalReputationImpact = claims.reduce((sum, c) => sum + c.reputationImpact, 0);
  const baseTruthScore = 60 + totalReputationImpact;
  const resolved = claims.filter((c) => c.status !== "pending");
  const successful = resolved.filter((c) => c.status === "resolved_success");
  const successRate = resolved.length === 0 ? 0 : Math.round((successful.length / resolved.length) * 100);

  const reputationBand = (() => {
    if (baseTruthScore >= 76) return { key: "rep-good", label: "Strong" };
    if (baseTruthScore >= 50) return { key: "rep-medium", label: "Balanced" };
    return { key: "rep-bad", label: "At Risk" };
  })();

  const scoreTone = baseTruthScore >= 76 ? "good" : baseTruthScore >= 50 ? "medium" : "bad";

  return (
    <>
      <div className="box">
        <h1>Investor Reputation</h1>
        <p>Live view of how oracle-resolved hard claims shape your standing on VeriFi.</p>
      </div>

      <div className="box">
        <h2>Investor Summary</h2>

        <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 16 }}>
          <div className="post-avatar" style={{ width: 64, height: 64, fontSize: 22 }}>
            YB
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0 }}>Yatırımcı Baba</h3>
            <p style={{ margin: 0, fontFamily: "'IBM Plex Mono',monospace", fontSize: 13 }}>@yatbaba • Joined Oct 2025</p>
            <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className="badge badge-accent">Top 28% Global</span>
              <span className="badge badge-success">Crypto Whale</span>
            </div>
          </div>
        </div>

        <div className="stat-row" style={{ marginTop: 0 }}>
          <div className="stat-chip">
            <div className="stat-chip-val">{claims.length}</div>
            <div className="stat-chip-label">Hard Claims</div>
          </div>
          <div className="stat-chip">
            <div className={`stat-chip-val score-dynamic ${scoreTone}`} aria-label="Truth score">
              {baseTruthScore}
            </div>
            <div className="stat-chip-label">Global Truth Score</div>
          </div>
          <div className="stat-chip">
            <div className="stat-chip-val">{successRate}%</div>
            <div className="stat-chip-label">Success Rate</div>
          </div>
          <div className="stat-chip">
            <div className="stat-chip-val">{totalReputationImpact >= 0 ? `+${totalReputationImpact}` : totalReputationImpact}</div>
            <div className="stat-chip-label">Total Reputation Impact</div>
          </div>
        </div>

        <div className={`rep-score-pill ${reputationBand.key}`}>
          <div className="rep-score-dot" />
          <div className="rep-score-meta">
            <div className="rep-score-label">Reputation Band • {reputationBand.label}</div>
            <div className="rep-score-desc">
              Every resolved hard claim nudges this band up or down. Higher bands unlock better social and on-chain privileges.
            </div>
          </div>
          <div className="rep-score-value">{baseTruthScore}</div>
        </div>
      </div>

      <div className="box">
        <h2>Past Hard Claims</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Asset</th>
              <th>Direction</th>
              <th>Target</th>
              <th>Timeframe</th>
              <th>Outcome</th>
              <th>Reputation Impact</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.id}>
                <td>{new Date(c.createdAt).toLocaleDateString()}</td>
                <td>{c.asset}</td>
                <td className={c.direction.toLowerCase() === "rise" ? "td-direction up" : "td-direction down"}>
                  {c.direction.toLowerCase() === "rise" ? "↑ Rise" : "↓ Drop"}
                </td>
                <td>{c.target}</td>
                <td>{c.timeframe}</td>
                <td>
                  {c.status === "pending" ? (
                    <span className="badge badge-pending">Pending</span>
                  ) : c.status === "resolved_success" ? (
                    <span className="badge badge-success">Success</span>
                  ) : (
                    <span className="badge badge-failure">Failed</span>
                  )}
                </td>
                <td
                  style={{
                    color: c.reputationImpact >= 0 ? "var(--green)" : "var(--red)",
                    fontFamily: "'IBM Plex Mono',monospace",
                    fontWeight: 700
                  }}
                >
                  {c.reputationImpact >= 0 ? `+${c.reputationImpact}` : c.reputationImpact}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
};

export default ProfileScreen;

