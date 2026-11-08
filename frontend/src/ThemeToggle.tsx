import { Moon, Sun } from 'lucide-react';
import { setTheme, useTheme } from './theme';

export default function ThemeToggle() {
  const theme = useTheme();
  const label = theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối';
  return <button type="button" className="theme-toggle" aria-label={label} title={label} aria-pressed={theme === 'light'} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
    {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}<span>{theme === 'dark' ? 'Sáng' : 'Tối'}</span>
  </button>;
}
