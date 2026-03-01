# Frontend - VeriFi

React + TypeScript + Vite frontend for the VeriFi application.

## Tech Stack

- **Framework**: React 19
- **Language**: TypeScript 5.9
- **Build Tool**: Vite 7
- **Styling**: TailwindCSS 4
- **UI Library**: Radix UI
- **Package Manager**: pnpm

## Prerequisites

- **Node.js** (v18 or higher)
- **pnpm** (recommended) or npm/yarn

Install pnpm if you don't have it:

```bash
npm install -g pnpm
```

## Installation

### 1. Navigate to the Frontend Directory

```bash
cd frontend
```

### 2. Install Dependencies

Using pnpm (recommended, as specified in pnpm-lock.yaml):

```bash
pnpm install
```

Or using npm:

```bash
npm install
```

## Running the Development Server

```bash
pnpm dev
```

The application will be available at `http://localhost:5173` with Hot Module Replacement (HMR) enabled.

## Building for Production

```bash
pnpm build
```

This generates an optimized build in the `dist/` directory.

## Preview Production Build

```bash
pnpm preview
```

## Linting

Run ESLint to check code quality:

```bash
pnpm lint
```

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
