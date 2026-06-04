# Data Model

The App Shell Refactor feature operates strictly at the UI presentation layer and does not introduce new backend models or persistence mechanisms. 

However, it interacts with the following frontend view models/data structures:

## `NavItem`

Defines the structure for navigation links used in the `Sidebar` and `MobileNav`.

- **Fields**:
  - `to` (string): The route path (e.g., `/feed`).
  - `icon` (React.ReactNode): The Lucide icon component.
  - `label` (string): The display label.
  - `matches` (function `(pathname: string) => boolean`): Evaluates whether the current URL matches the nav item to render the active state.

## Theme & Auth State

- **Theme**: Read from local storage (`verifi-theme`: `"dark" | "light"`) via `loadTheme()` and `useTheme()`.
- **Auth**: Provided by `useAuthState()`, returning the user's `address` and `username`.

## Truth Score & Energy Points (Placeholders)

For Phase 1, `TopNav.tsx` will accept placeholders or mock data for the Truth Score and Energy Points until the respective data layers are fully integrated.
