import React from "react";
import type { HardClaim } from "../types";

interface ClaimFeedListProps {
  claims: HardClaim[];
}

function statusLabel(status: HardClaim["status"]): string {
  if (status === "pending") return "Pending";
  if (status === "resolved_success") return "Resolved (Success)";
  return "Resolved (Failure)";
}

const ClaimFeedList: React.FC<ClaimFeedListProps> = ({ claims }) => {
  if (claims.length === 0) {
    return (
      <div className="box">
        <h2>Feed</h2>
        <p>No hard claims yet. Post a prediction to see how it affects your reputation.</p>
      </div>
    );
  }

  const sorted = [...claims].sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));

  return (
    <div className="box">
      <h2>Recent Hard Claims</h2>
      {sorted.map((claim) => (
        <div key={claim.id} className="post-card">
          <div className="post-card-header">
            <div className="post-avatar">YB</div>
            <div className="post-user-info">
              <div className="post-username">@yatbaba</div>
              <div className="post-time">{new Date(claim.createdAt).toLocaleString()}</div>
            </div>
            {claim.status === "pending" ? (
              <span className="badge badge-pending">Pending</span>
            ) : claim.status === "resolved_success" ? (
              <span className="badge badge-success">+{claim.reputationImpact}</span>
            ) : (
              <span className="badge badge-failure">{claim.reputationImpact}</span>
            )}
          </div>

          <div className="post-body">{claim.text}</div>

          <div className="post-claim-preview">
            <div className="claim-meta">
              <span className="badge badge-accent">{claim.asset}</span>
              <span className={claim.direction.toLowerCase() === "rise" ? "td-direction up" : "td-direction down"}>
                {claim.direction}
              </span>
              <span className="td-target">{claim.target}</span>
              <span className="badge badge-soft">By {claim.timeframe || "N/A"}</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--txt-muted)", textAlign: "right" }}>
              {statusLabel(claim.status)}
            </div>
          </div>

          <div className="post-actions">
            <button className="post-action-btn" type="button">
              <span>Bookmark</span>
            </button>
            <button className="post-action-btn" type="button">
              <span>View impact</span>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ClaimFeedList;

