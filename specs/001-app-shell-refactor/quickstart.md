# Quickstart / Validation Guide

This guide outlines how to validate the App Shell Refactor once implemented.

## Prerequisites

Ensure the frontend dependencies are installed and the development server is running:

```bash
cd frontend
pnpm install
pnpm dev
```

## Validation Scenarios

### Scenario 1: Desktop Layout Verification (≥768px)
1. Open the application in a desktop browser at `http://localhost:5173/feed`.
2. **Verify Sidebar**: 
   - Ensure the Sidebar is visible on the left side (width should be 240px).
   - Ensure the VeriFi logo is visible at the top.
   - Check that the active navigation item ("Feed") has a gold left-bar accent and a gold-tinted background.
   - Verify the Markets section renders ticker rows (or skeletons).
   - Confirm the user identity row is at the bottom, showing your avatar, truncated address, and Truth Score %.
3. **Verify TopNav**: 
   - Ensure the TopNav is sticky at the top of the main content area.
   - Check the title on the left reads "Feed".
   - Verify the Energy Points pill and Truth Score pill are displayed on the right.
4. **Verify MainContent**:
   - Confirm the grid background (`main-grid-bg`) and radial fade (`content-grid-fade`) are visible behind the feed posts.

### Scenario 2: Mobile Layout Verification (<768px)
1. Resize your browser window to less than 768px wide (or use Chrome DevTools device toolbar).
2. **Verify Sidebar**: 
   - Ensure the Sidebar is completely hidden.
3. **Verify TopNav**:
   - On very small screens (<640px), ensure the user address/username text is hidden in the TopNav, but the avatar remains tappable.
4. **Verify BottomTabBar**:
   - Ensure the mobile `BottomTabBar` takes over the bottom of the screen.
   - Ensure the `MainContent` adds enough bottom padding so content isn't obscured by the bottom bar.

### Scenario 3: Theme Switching
1. Click the theme toggle icon (Sun/Moon) in the TopNav.
2. Verify that the Sidebar, TopNav, and MainContent switch simultaneously between light and dark modes without flashing or inconsistent colors.

### Scenario 4: Auth State
1. If authenticated, click the "Disconnect" button in the Sidebar (or Mobile Menu).
2. Verify that the user row in the Sidebar is replaced with a "Connect Wallet" / Login button.
3. Verify that the EP and Truth Score pills in the TopNav disappear and a "Connect" button takes their place.
