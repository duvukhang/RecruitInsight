import { Button } from "./components/ui/button";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Layers3,
  ShieldCheck,
  LogOut,
  LoaderCircle,
} from "lucide-react";
import { api, remember, clearSession, csrfHeaders, ApiError } from "./api";
import { NavLink, useLocation } from "react-router-dom";
import { can, routePermission } from './permissions';
import { RoleBadge } from './components/insights';
import {
  LayoutDashboard,
  ChartNoAxesCombined,
  Coins,
  BriefcaseBusiness,
  BrainCircuit,
  FolderOpen,
  Workflow,
  Settings,
  ScanLine,
  UserRound,
  ChevronDown,
} from "lucide-react";
import Workspace from "./Workspace";
import { avatarColors } from './Profile';
import ThemeToggle from './ThemeToggle';
type User = { id: string; username: string; role: string; display_name?: string; avatar_color?: string };
function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [notice] = React.useState(() => { const value = sessionStorage.getItem('auth-notice') || ''; sessionStorage.removeItem('auth-notice'); return value; });
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const fields = new FormData(e.currentTarget);
    try {
      const result = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: fields.get("username"),
          password: fields.get("password"),
        }),
      });
      remember(result);
      onLogin(result.data.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-wrap">
      <section className="login-story">
        <Brand />
        <div>
          <div className="eyebrow">RECRUITMENT DATA PLATFORM</div>
          <h1>
            Dữ liệu tuyển dụng.
            <br />
            Góc nhìn có cơ sở.
          </h1>
          <div className="story-tags">
            <span>Apache Spark</span>
            <span>MongoDB</span>
            <span>Machine Learning</span>
          </div>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-theme"><ThemeToggle /></div>
        <form onSubmit={submit}>
          <span className="small-icon">
            <ShieldCheck />
          </span>
          <h2>Chào mừng trở lại</h2>
          {notice && <div className="notice" role="status">{notice}</div>}
          <label>
            Tên đăng nhập
            <input
              name="username"
              autoComplete="username"
              required
              maxLength={128}
            />
          </label>
          <label>
            Mật khẩu
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={256}
            />
          </label>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <Button disabled={busy}>
            {busy && <LoaderCircle className="spin" size={18} />}{" "}
            {busy ? "Đang đăng nhập…" : "Đăng nhập"} <ArrowUpRight size={18} />
          </Button>
        </form>
      </section>
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <Layers3 />
      </span>
      recruit<span className="brand-light">insight</span>
    </div>
  );
}
export default function App() {
  const [user, setUser] = React.useState<User | null>(null);
  const [checking, setChecking] = React.useState(true);
  const client = useQueryClient();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = React.useState(false);
  React.useEffect(() => {
    setMenuOpen(false);
    document.scrollingElement?.scrollTo?.(0, 0);
  }, [location.pathname]);
  React.useEffect(() => {
    if (!user) return;
    let cancelled = false;
    let previousRole = user.role;
    const sync = async () => {
      try {
        const result = await api('/auth/me');
        if (!cancelled) {
          if (previousRole !== result.data.role) client.clear();
          previousRole = result.data.role;
          setUser(result.data);
        }
      } catch (error) {
        if (!cancelled && error instanceof ApiError && error.status === 401) {
          clearSession(); setUser(null); client.clear();
        }
      }
    };
    sync();
    const timer = window.setInterval(sync, 30000);
    window.addEventListener('focus', sync);
    window.addEventListener('app-user-changed', sync);
    return () => { cancelled = true; window.clearInterval(timer); window.removeEventListener('focus', sync); window.removeEventListener('app-user-changed', sync); };
  }, [user?.id, client]);
  React.useEffect(() => {
    const expired = () => {
      setUser(null);
      client.clear();
    };
    window.addEventListener("app-session-expired", expired);
    return () => window.removeEventListener("app-session-expired", expired);
  }, [client]);
  React.useEffect(() => {
    api("/auth/refresh", { method: "POST", headers: csrfHeaders() })
      .then((r) => {
        remember(r);
        setUser(r.data.user);
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  if (checking)
    return (
      <div className="empty full">
        <LoaderCircle className="spin" /> Đang mở không gian làm việc…
      </div>
    );
  if (!user) return <Login onLogin={setUser} />;
  const navigation = [
    { path: "/", label: "Dashboard", icon: LayoutDashboard },
    {
      path: "/analytics/recruitment",
      label: "Phân tích tuyển dụng",
      icon: ChartNoAxesCombined,
    },
    { path: "/analytics/salary", label: "Phân tích mức lương", icon: Coins },
    { path: "/jobs", label: "Danh sách việc làm", icon: BriefcaseBusiness },
    { path: "/predictions", label: "Dự đoán mức lương", icon: ScanLine },
    { path: "/datasets", label: "Quản lý dữ liệu", icon: FolderOpen },
    { path: "/etl", label: "Giám sát ETL", icon: Workflow },
    { path: "/models", label: "Machine Learning", icon: BrainCircuit },
    { path: "/settings", label: "Hệ thống", icon: Settings },
    { path: "/sources", label: "Nguồn dữ liệu", icon: FolderOpen },
    { path: "/quality", label: "Chất lượng dữ liệu", icon: ShieldCheck },
    { path: "/users", label: "Người dùng", icon: ShieldCheck },
    { path: "/audit", label: "Nhật ký quản trị", icon: Workflow },
    { path: '/profile', label: 'Hồ sơ cá nhân', icon: UserRound },
  ];
  return (
    <div className="shell">
      <Notices />
      <aside className={menuOpen ? 'menu-open' : ''}>
        <Brand />
        <button className="mobile-menu" aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(!menuOpen)}>Menu</button>
        <div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav id="main-navigation" aria-label="Điều hướng chính">
          {navigation
            .filter(
              (n) => can(user.role, routePermission[n.path] || 'read'),
            )
            .sort((a, b) => navGroup(a.path).order - navGroup(b.path).order)
            .map((n, index, visible) => (
              <React.Fragment key={n.path}>
                {(index === 0 || navGroup(visible[index - 1].path).name !== navGroup(n.path).name) && <div className="nav-group">{navGroup(n.path).name}</div>}
                <NavLink to={{ pathname: n.path, search: location.search }} end={n.path === "/"}><n.icon size={18} />{n.label}</NavLink>
              </React.Fragment>
            ))}
        </nav>
        <div className="sidebar-foot">
          <NavLink to="/profile" className="avatar" aria-label="Mở hồ sơ cá nhân" style={{ background: avatarColors[user.avatar_color || 'cyan'] }}>{Array.from(user.display_name || user.username)[0].toUpperCase()}</NavLink>
          <NavLink to="/profile" className="profile-summary">
            <strong title={user.display_name || user.username}>{user.display_name || user.username}</strong>
            <RoleBadge role={user.role} />
          </NavLink>
          <button
            aria-label="Đăng xuất"
            onClick={async () => {
              try {
                await api("/auth/logout", {
                  method: "POST",
                  headers: csrfHeaders(),
                });
              } catch {
                /* Local sign-out also works if the session is already unavailable. */
              } finally {
                clearSession();
                setUser(null);
                client.clear();
              }
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <div className="content">
        <header>
          <span>
            RecruitInsight <span className="slash">/</span> {navigation.find(n => n.path === location.pathname)?.label || 'Tổng quan'}
          </span>
          <div className="header-actions"><ThemeToggle /><NavLink to="/profile" className="account-chip" aria-label="Hồ sơ cá nhân"><span className="avatar" style={{ background: avatarColors[user.avatar_color || 'cyan'] }}>{Array.from(user.display_name || user.username)[0].toUpperCase()}</span><span className="account-chip-name">{user.display_name || user.username}<small>Hồ sơ của tôi</small></span><ChevronDown size={14} /></NavLink></div>
        </header>
        <main>
          <Workspace role={user.role} />
        </main>
      </div>
    </div>
  );
}

function navGroup(path: string) {
  if (path === '/profile') return { order: 5, name: 'Tài khoản' };
  if (path === '/') return { order: 0, name: 'Tổng quan' };
  if (path.startsWith('/analytics') || path === '/jobs') return { order: 1, name: 'Phân tích' };
  if (['/models', '/predictions'].includes(path)) return { order: 2, name: 'Machine Learning' };
  if (['/datasets', '/sources', '/quality', '/etl'].includes(path)) return { order: 3, name: 'Dữ liệu & ETL' };
  return { order: 4, name: 'Quản trị' };
}

function Notices() {
  const [notice, setNotice] = React.useState("");
  React.useEffect(() => {
    const handler = (event: Event) => setNotice((event as CustomEvent).detail);
    window.addEventListener("app-notice", handler);
    return () => window.removeEventListener("app-notice", handler);
  }, []);
  return notice ? (
    <div className="notice-toast" role="alert">
      {notice}
      <button onClick={() => setNotice("")}>Đóng</button>
    </div>
  ) : null;
}
