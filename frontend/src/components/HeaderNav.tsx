import React from "react";

export type ScreenKey = "feed" | "profile" | "resolutions" | "proofs";

interface HeaderNavProps {
  current: ScreenKey;
  onChange: (screen: ScreenKey) => void;
}

const HeaderNav: React.FC<HeaderNavProps> = ({ current, onChange }) => {
  return (
    <div className="nav">
      <span className="app-title">
        <span className="app-title-icon">VF</span>
        Veri<strong>Fi</strong>
      </span>
      <span className="nav-title">Hard Claims</span>
      <span className="nav-links">
        <a
          href="#feed"
          className={current === "feed" ? "active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            onChange("feed");
          }}
        >
          <span>Feed</span>
        </a>
        <a
          href="#profile"
          className={current === "profile" ? "active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            onChange("profile");
          }}
        >
          <span>Reputation</span>
        </a>
        <a
          href="#resolutions"
          className={current === "resolutions" ? "active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            onChange("resolutions");
          }}
        >
          <span>Resolutions</span>
        </a>
        <a
          href="#proofs"
          className={current === "proofs" ? "active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            onChange("proofs");
          }}
        >
          <span>Proofs</span>
        </a>
      </span>
    </div>
  );
};

export default HeaderNav;

