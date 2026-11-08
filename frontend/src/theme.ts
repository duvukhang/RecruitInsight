import { useSyncExternalStore } from 'react';

export type Theme = 'light' | 'dark';
const key = 'recruitinsight-theme';
const event = 'app-theme-changed';

function savedTheme(): Theme {
  try { return localStorage.getItem(key) === 'light' ? 'light' : 'dark'; }
  catch { return 'dark'; }
}
function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}
apply(savedTheme());

export function setTheme(theme: Theme) {
  apply(theme);
  try { localStorage.setItem(key, theme); } catch { /* The switch still works when storage is unavailable. */ }
  window.dispatchEvent(new Event(event));
}
function subscribe(listener: () => void) {
  const storageChanged = (change: StorageEvent) => {
    if (change.key === key || change.key === null) { apply(savedTheme()); listener(); }
  };
  window.addEventListener(event, listener);
  window.addEventListener('storage', storageChanged);
  return () => { window.removeEventListener(event, listener); window.removeEventListener('storage', storageChanged); };
}
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, () => document.documentElement.dataset.theme === 'light' ? 'light' : 'dark', () => 'dark');
}
