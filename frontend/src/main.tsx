import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initTheme } from './lib/theme.ts'
import { PrivyAppProvider } from './providers/PrivyAppProvider.tsx'

// Initialize theme before rendering
initTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PrivyAppProvider>
      <App />
    </PrivyAppProvider>
  </StrictMode>,
)
