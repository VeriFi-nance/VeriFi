import { useEffect, useState } from 'react';
import { Toaster as SonnerToaster } from 'sonner';

/**
 * App toast host. Mirrors the app's class-based dark mode (`.dark` on <html>)
 * into sonner's `theme` prop so toasts match the active palette.
 */
export function Toaster() {
  const [theme, setTheme] = useState<'light' | 'dark'>(
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light',
  );

  useEffect(() => {
    const root = document.documentElement;
    const update = () => setTheme(root.classList.contains('dark') ? 'dark' : 'light');
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return (
    <SonnerToaster
      theme={theme}
      richColors
      position="top-center"
      closeButton
      toastOptions={{ duration: 4000 }}
    />
  );
}
