import React, { useState } from "react";
import type { HardClaim } from "../types";

interface PostComposerProps {
  onCreateClaim: (claim: Omit<HardClaim, "id" | "status" | "oraclePrice" | "reputationImpact" | "createdAt">) => void;
  nextId: number;
}

interface ExtractedClaim {
  asset: string;
  direction: string;
  target: string;
  timeframe: string;
  projectedReputation: number;
}

const initialExtracted: ExtractedClaim = {
  asset: "",
  direction: "",
  target: "",
  timeframe: "",
  projectedReputation: 0
};

function extractClaimFromText(text: string): ExtractedClaim {
  const lower = text.toLowerCase();
  let asset = "";
  if (lower.includes("bitcoin") || lower.includes("btc")) {
    asset = "BTC";
  } else if (lower.includes("nvda")) {
    asset = "NVDA";
  } else if (lower.includes("eth")) {
    asset = "ETH";
  } else {
    asset = "UNKNOWN";
  }

  let direction = "";
  if (lower.includes("drop") || lower.includes("decrease")) {
    direction = "Drop";
  } else if (lower.includes("rise") || lower.includes("increase")) {
    direction = "Rise";
  }

  let target = "";
  const targetMatch = text.match(/([+-]?\d+)%/);
  if (targetMatch) {
    target = targetMatch[1] + "%";
  }

  let timeframe = "";
  const yearMatch = text.match(/20\d{2}/);
  if (yearMatch) {
    timeframe = yearMatch[0];
  }

  const base = 10;
  const difficultyBonus = targetMatch ? Math.min(Math.abs(parseInt(targetMatch[1], 10)), 40) / 4 : 0;
  const projectedReputation = Math.round(base + difficultyBonus);

  return { asset, direction, target, timeframe, projectedReputation };
}

const PostComposer: React.FC<PostComposerProps> = ({ onCreateClaim }) => {
  const [text, setText] = useState(
    "Bitcoin fails. It will converge to 0. I forecast a drop of 50% by the end of 2026."
  );
  const [extracted, setExtracted] = useState<ExtractedClaim>(() => extractClaimFromText(text));

  const handlePost = () => {
    const next = extractClaimFromText(text);
    setExtracted(next);
    onCreateClaim({
      text,
      asset: next.asset || "UNKNOWN",
      direction: next.direction || "",
      target: next.target || "",
      timeframe: next.timeframe || ""
    });
  };

  return (
    <div className="box">
      <h2>Create Hard Claim</h2>
      <p>Write your financial prediction. VeriFi extracts a verifiable hard claim and previews its reputation impact.</p>
      <label htmlFor="postText">Post</label>
      <textarea
        id="postText"
        rows={4}
        value={text}
        onChange={(e) => {
          const value = e.target.value;
          setText(value);
          setExtracted(extractClaimFromText(value));
        }}
      />
      <button onClick={handlePost}>Post Hard Claim</button>

      <div className="box" style={{ marginTop: 12 }}>
        <h3>Extracted Hard Claim</h3>
        <p>These values are derived from your post. Edit the text above to see this update in real time.</p>
        <div className="fields-grid">
          <div>
            <label>Asset</label>
            <input type="text" readOnly value={extracted.asset} />
          </div>
          <div>
            <label>Direction</label>
            <input type="text" readOnly value={extracted.direction} />
          </div>
          <div>
            <label>Target</label>
            <input type="text" readOnly value={extracted.target} />
          </div>
          <div>
            <label>Timeframe</label>
            <input type="text" readOnly value={extracted.timeframe} />
          </div>
        </div>
        <div
          className="result"
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginTop: 12
          }}
        >
          <span
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: 0.4
            }}
          >
            Reputation score to be gained
          </span>
          <span
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 700,
              fontSize: 18
            }}
          >
            {extracted.projectedReputation}
          </span>
        </div>
      </div>
    </div>
  );
};

export default PostComposer;

