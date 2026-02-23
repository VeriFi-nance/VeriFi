import React from "react";
import type { HardClaim } from "../types";

interface ProofsScreenProps {
  claim: HardClaim | null;
}

const ProofsScreen: React.FC<ProofsScreenProps> = ({ claim }) => {
  const [signature, setSignature] = React.useState(
    claim
      ? `SIGN(${claim.asset},${claim.direction},${claim.target},${claim.timeframe},InvestorPublicKey)`
      : ""
  );
  const [result, setResult] = React.useState("No verification attempted yet.");

  if (!claim) {
    return (
      <div className="box">
        <h1>Signed Hard Claim Proof</h1>
        <p>No claim available.</p>
      </div>
    );
  }

  const handleVerify = () => {
    const expected = `SIGN(${claim.asset},${claim.direction},${claim.target},${claim.timeframe}`;
    if (signature.startsWith(expected)) {
      setResult("Signature valid. The claim is undeniably linked to the investor.");
    } else {
      setResult("Signature invalid. Saved data does not match the current hard claim fields.");
    }
  };

  return (
    <>
      <div className="box">
        <h1>Signed Hard Claim Proof</h1>
        <p>This page shows the non-repudiation flow where a subscriber keeps a signed version of a hard claim.</p>
      </div>

      <div className="box">
        <h2>Original Hard Claim</h2>
        <p>
          <strong>Asset:</strong> {claim.asset}
        </p>
        <p>
          <strong>Direction:</strong> {claim.direction}
        </p>
        <p>
          <strong>Target:</strong> {claim.target}
        </p>
        <p>
          <strong>Timeframe:</strong> {claim.timeframe}
        </p>
      </div>

      <div className="box">
        <h2>Saved Signed Claim</h2>
        <p>This simulates the data that a subscriber saves locally.</p>
        <label htmlFor="signature">Signature</label>
        <textarea
          id="signature"
          rows={4}
          value={signature}
          onChange={(e) => setSignature(e.target.value)}
        />
        <button onClick={handleVerify}>Verify Signature</button>
        <p style={{ marginTop: 8 }}>
          <strong>{result}</strong>
        </p>
      </div>

      <div className="box">
        <h2>Reputation Effect</h2>
        <p>
          If the claim fails and the signature is valid, the investor's reputation is updated even if the social content
          is deleted.
        </p>
      </div>
    </>
  );
};

export default ProofsScreen;

