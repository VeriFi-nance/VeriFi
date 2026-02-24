import React, { useState } from "react";
import HeaderNav, { ScreenKey } from "./components/HeaderNav";
import { initialHardClaims } from "./data/hardClaims";
import type { HardClaim } from "./types";
import FeedScreen from "./components/FeedScreen";
import ProfileScreen from "./components/ProfileScreen";
import ResolutionsScreen from "./components/ResolutionsScreen";
import ProofsScreen from "./components/ProofsScreen";

const App: React.FC = () => {
  const [screen, setScreen] = useState<ScreenKey>("feed");
  const [claims, setClaims] = useState<HardClaim[]>(initialHardClaims);

  const handleAddClaim = (claim: HardClaim) => {
    setClaims((prev) => [...prev, claim]);
  };

  const handleUpdateClaims = (updated: HardClaim[]) => {
    setClaims(updated);
  };

  let content: React.ReactNode = null;
  if (screen === "feed") {
    content = <FeedScreen claims={claims} onAddClaim={handleAddClaim} />;
  } else if (screen === "profile") {
    content = <ProfileScreen claims={claims} />;
  } else if (screen === "resolutions") {
    content = <ResolutionsScreen claims={claims} onUpdateClaims={handleUpdateClaims} />;
  } else if (screen === "proofs") {
    content = <ProofsScreen claim={claims[0] ?? null} />;
  }

  return (
    <div className="layout-twitter">
      <aside className="left-sidebar">
        <HeaderNav current={screen} onChange={setScreen} />
      </aside>
      
      <main className="main-feed">
        {content}
      </main>
      
      <aside className="right-sidebar">
        <div className="side-widget">
          <div className="side-widget-title"><span className="icon">🏆</span> Leaderboard</div>
          <div className="leaderboard-row">
            <div className="lb-rank">1</div>
            <div className="lb-name">@yatbaba</div>
            <div className="lb-score">450</div>
          </div>
          <div className="leaderboard-row">
            <div className="lb-rank">2</div>
            <div className="lb-name">@crypto_king</div>
            <div className="lb-score">320</div>
          </div>
          <div className="leaderboard-row">
            <div className="lb-rank">3</div>
            <div className="lb-name">@oracle_node</div>
            <div className="lb-score">215</div>
          </div>
        </div>
        
        <div className="side-widget">
          <div className="side-widget-title"><span className="icon">📈</span> Trending Assets</div>
          <div className="leaderboard-row">
            <div className="lb-name">1. $BTC</div>
            <div className="lb-score trending-stat">52.4K posts</div>
          </div>
          <div className="leaderboard-row">
            <div className="lb-name">2. $NVDA</div>
            <div className="lb-score trending-stat">18.1K posts</div>
          </div>
          <div className="leaderboard-row">
            <div className="lb-name">3. $SOL</div>
            <div className="lb-score trending-stat">14.2K posts</div>
          </div>
        </div>
      </aside>
    </div>
  );
};

export default App;

