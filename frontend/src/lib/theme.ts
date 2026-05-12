const THEME_KEY = 'verifi-theme';

export type Theme = 'light' | 'dark';

/** Get the current theme from localStorage, defaulting to 'light'. */
export function loadTheme(): Theme {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return 'light';
}

/** Save the theme to localStorage and apply it to the document root. */
export function saveTheme(theme: Theme): void {
  localStorage.setItem(THEME_KEY, theme);
  applyTheme(theme);
}

/** Apply the theme by toggling the 'dark' class on document.documentElement. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

/** Initialize the theme on app startup. */
export function initTheme(): void {
  const theme = loadTheme();
  applyTheme(theme);
}

/** Toggle between light and dark themes. */
export function toggleTheme(): Theme {
  const current = loadTheme();
  const next: Theme = current === 'dark' ? 'light' : 'dark';
  saveTheme(next);
  return next;
}
