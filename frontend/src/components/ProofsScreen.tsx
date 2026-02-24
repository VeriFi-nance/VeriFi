import React, { useState } from "react";
import type { HardClaim } from "../types";

interface ProofsScreenProps {
  claim: HardClaim | null;
}

const ProofsScreen: React.FC<ProofsScreenProps> = ({ claim }) => {
  // Mock expected values for a valid proof scenario
  const MOCK_PUB_KEY = "0x8F2a...9b4C";
  const MOCK_SIGNATURE = "0x7a91fbc2...3d8e";

  const [pubKey, setPubKey] = useState(MOCK_PUB_KEY);
  const [signature, setSignature] = useState(MOCK_SIGNATURE);
  const [verificationState, setVerificationState] = useState<"idle" | "success" | "failure">("idle");
  const [showShare, setShowShare] = useState(false);

  if (!claim) {
    return (
      <div className="box">
        <h1>Cryptographic Proof Verification</h1>
        <p>No claim available to verify.</p>
      </div>
    );
  }

  const handleVerify = () => {
    // A simple simulation of verification: check if the inputs match the expected mock proof
    if (pubKey === MOCK_PUB_KEY && signature === MOCK_SIGNATURE) {
      setVerificationState("success");
    } else {
      setVerificationState("failure");
    }
  };

  return (
    <>
      <div className="box">
        <h1>Cryptographic Verification</h1>
        <p>
          Verify the authenticity of a hard claim independently. By supplying the signer's public key
          and their cryptographic signature, you can mathematically prove they authored this claim.
        </p>
      </div>

      <div className="box">
        <h2>Claim Payload</h2>
        <div style={{ background: "var(--bg-input)", padding: 14, borderRadius: 6, marginBottom: 14 }}>
          <div className="code-block" style={{ margin: 0 }}>
            {`{
  "asset": "${claim.asset}",
  "direction": "${claim.direction}",
  "target": "${claim.target}",
  "timeframe": "${claim.timeframe}",
  "timestamp": "${claim.createdAt}"
}`}
          </div>
        </div>
      </div>

      <div className="box">
        <h2>Verification Parameters</h2>
        <p>Enter the public key of the suspected author and the signature payload attached to the claim.</p>
        
        <div style={{ marginTop: 16 }}>
          <label htmlFor="pubKey">Signer Public Key (Hex)</label>
          <input
            type="text"
            id="pubKey"
            value={pubKey}
            onChange={(e) => {
              setPubKey(e.target.value);
              setVerificationState("idle");
            }}
            placeholder="0x..."
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          />

          <label htmlFor="signature">Cryptographic Signature</label>
          <textarea
            id="signature"
            rows={3}
            value={signature}
            onChange={(e) => {
              setSignature(e.target.value);
              setVerificationState("idle");
            }}
            placeholder="0x..."
            style={{ fontFamily: "'IBM Plex Mono', monospace" }}
          />
        </div>

        <button className="btn btn-primary" onClick={handleVerify} style={{ marginTop: 16 }}>
          Verify Cryptographic Proof
        </button>

        {verificationState === "success" && (
          <div className="result" style={{ borderColor: "var(--green)", backgroundColor: "var(--green-bg)", color: "var(--green)" }}>
            <strong>✅ Signature Valid</strong>
            <p style={{ color: "var(--green)", marginTop: 4 }}>
              The provided signature correctly signs the claim payload using the specified public key.
              This claim is cryptographically bound to the author.
            </p>
            
            <button 
              className="btn" 
              style={{ marginTop: 14, background: "var(--bg-surface)", color: "var(--txt-primary)", border: "1px solid var(--border)" }}
              onClick={() => setShowShare(!showShare)}
            >
              Share this Proof
            </button>
          </div>
        )}

        {showShare && verificationState === "success" && (
          <div className="box share-widget" style={{ marginTop: 16 }}>
            <h3 style={{ marginBottom: 14 }}>Share to Web3 & Socials</h3>
            <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
              <button className="btn btn-twitter" style={{ flex: 1, background: "#1DA1F2", color: "#fff", border: "none" }}>
                Twitter
              </button>
              <button className="btn btn-whatsapp" style={{ flex: 1, background: "#25D366", color: "#fff", border: "none" }}>
                WhatsApp
              </button>
              <button className="btn btn-ghost" style={{ flex: 1 }}>
                Copy Link
              </button>
            </div>

            <h4 style={{ fontSize: 13, color: "var(--txt-muted)", textTransform: "uppercase", marginBottom: 10 }}>Link Preview</h4>
            <div className="link-preview-card" style={{ border: "1px solid var(--border-lite)", borderRadius: "var(--r-md)", overflow: "hidden", display: "flex", background: "var(--bg-input)" }}>
              <div className="qr-code-container" style={{ padding: 12, borderRight: "1px solid var(--border-lite)", background: "#fff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <img src="/src/assets/qr_code_mock.png" alt="QR Code" style={{ width: 80, height: 80 }} />
              </div>
              <div className="link-preview-content" style={{ padding: "12px 14px" }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--txt-primary)", marginBottom: 4 }}>Verified Claim on VeriFi</div>
                <div style={{ fontSize: 12, color: "var(--txt-secondary)", lineHeight: 1.4 }}>
                  {claim.asset} will {claim.direction.toLowerCase()} {claim.target} by {claim.timeframe}. Cryptographically signed by 0x8F2a...
                </div>
                <div style={{ fontSize: 11, color: "var(--txt-muted)", marginTop: 6, textTransform: "uppercase" }}>verifi.network/proofs/0x7a91</div>
              </div>
            </div>
          </div>
        )}

        {verificationState === "failure" && (
          <div className="result" style={{ borderColor: "var(--red)", backgroundColor: "var(--red-bg)", color: "var(--red)" }}>
            <strong>❌ Signature Invalid</strong>
            <p style={{ color: "var(--red)", marginTop: 4 }}>
              The cryptographic signature does not match the claim payload for the provided public key.
              This claim may have been tampered with or the public key is incorrect.
            </p>
          </div>
        )}
      </div>
    </>
  );
};

export default ProofsScreen;

