import React from "react";

export type ScreenKey = "feed" | "profile" | "resolutions" | "proofs";

interface HeaderNavProps {
  current: ScreenKey;
  onChange: (screen: ScreenKey) => void;
}

const HeaderNav: React.FC<HeaderNavProps> = ({ current, onChange }) => {
  return (
    <div className="nav-vertical">
      <div className="nav-header">
        <span className="app-title">
          <span className="app-title-icon">VF</span>
          Veri<strong>Fi</strong>
        </span>
      </div>

      <div className="nav-links-vertical">
        <a
          href="#feed"
          className={current === "feed" ? "active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            onChange("feed");
          }}
        >
          <span className="nav-icon">🏠</span>
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
          <span className="nav-icon">⭐️</span>
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
          <span className="nav-icon">⚖️</span>
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
          <span className="nav-icon">🛡️</span>
          <span>Proofs</span>
        </a>
      </div>

      <button className="btn btn-primary btn-post-nav">Post Claim</button>

      <div className="nav-user-profile">
        <div className="nav-avatar">YB</div>
        <div className="nav-user-info">
          <div className="nav-username">Yatbaba</div>
          <div className="nav-handle">@yatbaba</div>
        </div>
      </div>
    </div>
  );
};

export default HeaderNav;

