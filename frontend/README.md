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
- **pnpm** — install it if you don't have it:

```bash
npm install -g pnpm
```

## Installation

### 1. Navigate to the Frontend Directory

```bash
cd frontend
```

### 2. Install Dependencies

```bash
pnpm install
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

