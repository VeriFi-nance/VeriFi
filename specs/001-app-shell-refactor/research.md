# Research

## UI Shell Extraction

**Decision**: Extract the `Sidebar`, `TopNav`, and `MainContent` directly from the `AppLayout.tsx` and place them in `src/components/layout/`.
**Rationale**: Adhering to the Feature-Sliced Design (FSD) architecture defined in the constitution. This will prevent `AppLayout.tsx` from growing infinitely and separate layout concerns.
**Alternatives considered**: Extracting components into `src/pages/layout/`, which was rejected as it violates the newly enforced FSD paths (`pages/` is only for routing wrappers).

## CSS Tokens and Global Styles

**Decision**: Continue using `frontend/src/index.css` as the single source of truth for all design tokens (colors, border radius, animations). If we find that any specific token from `mockup.html` (e.g., gold primary variants) is missing in `index.css`, we will update `index.css` instead of hardcoding the value in React files. 
**Rationale**: This fulfills the User's request and Constitution Principle III to have a centralized file to change the color palette or roundness for the whole app. The `index.css` currently defines variables under `:root` and `.dark` block.
**Alternatives considered**: Creating a separate `global.css` or importing a separate theme file, but since `index.css` already exists and acts as the Tailwind entry point, expanding it is the cleanest approach.

## Responsive Design

**Decision**: Handle responsive design purely through Tailwind utility classes (e.g., `hidden md:flex`) in the layout components, mirroring the behavior in `mockup.html`.
**Rationale**: This keeps the implementation purely CSS-driven without relying on JavaScript window resizing listeners, which can be computationally expensive and cause hydration mismatches or flickers.
