import React from "react";
import type { HardClaim } from "../types";
import PostComposer from "./PostComposer";
import ClaimFeedList from "./ClaimFeedList";

interface FeedScreenProps {
  claims: HardClaim[];
  onAddClaim: (claim: HardClaim) => void;
}

const FeedScreen: React.FC<FeedScreenProps> = ({ claims, onAddClaim }) => {
  const nextId = claims.length === 0 ? 1 : Math.max(...claims.map((c) => c.id)) + 1;

  return (
    <>
      <div className="box">
        <h1>Feed</h1>
        <p>Post verifiable hard claims and see how they affect your reputation.</p>
      </div>

      <PostComposer
        nextId={nextId}
        onCreateClaim={(partial) => {
          const now = new Date().toISOString();
          const claim: HardClaim = {
            id: nextId,
            text: partial.text,
            asset: partial.asset,
            direction: partial.direction,
            target: partial.target,
            timeframe: partial.timeframe,
            status: "pending",
            oraclePrice: null,
            reputationImpact: 0,
            createdAt: now
          };
          onAddClaim(claim);
        }}
      />

      <ClaimFeedList claims={claims} />
    </>
  );
};

export default FeedScreen;

