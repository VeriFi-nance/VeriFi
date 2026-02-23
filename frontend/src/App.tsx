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
    <div className="page">
      <HeaderNav current={screen} onChange={setScreen} />
      {content}
    </div>
  );
};

export default App;

