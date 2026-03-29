---
name: react-ui-guidelines
description: Use this whenever creating or editing React components, hooks, or frontend routing in the frontend/ directory.
---
# React UI Rules
- **Language**: Strict TypeScript. No `any`.
- **Components**: Functional components only. Keep under ~200 lines; extract sub-components/hooks if larger. No inline logic in JSX.
- **Styling & UI**: Tailwind 4 utility classes only. Use shadcn/ui primitives from `src/components/ui/`. Do NOT install new UI libraries.
- **State**: React `useState` / `useEffect`. No global state libraries unless explicitly approved.
- **Routing**: `react-router-dom` v7. Wrap authenticated routes in `ProtectedRoute`.
- **API**: Route all fetch calls through `src/lib/api.ts`.