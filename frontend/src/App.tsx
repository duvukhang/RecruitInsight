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
import { api, remember, clearSession, csrfHeaders } from "./api";
import { NavLink } from "react-router-dom";
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
} from "lucide-react";
import Workspace from "./Workspace";
type User = { id: string; username: string; role: string };
function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
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
          <p>
            Phân tích dữ liệu, theo dõi chất lượng và khám phá mức lương trên
            cùng một nền tảng.
          </p>
          <div className="story-tags">
            <span>Apache Spark</span>
            <span>MongoDB</span>
            <span>Machine Learning</span>
          </div>
        </div>
        <small>Đồ án Big Data · Recruitment Analytics</small>
      </section>
      <section className="login-panel">
        <form onSubmit={submit}>
          <span className="small-icon">
            <ShieldCheck />
          </span>
          <h2>Chào mừng trở lại</h2>
          <p className="muted">Đăng nhập để truy cập không gian phân tích.</p>
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
          <p className="login-help">
            Tài khoản quản trị được cấu hình trong file .env của dự án.
          </p>
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
  ];
  return (
    <div className="shell">
      <Notices />
      <aside>
        <Brand />
        <div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav>
          {navigation
            .filter(
              (n) =>
                user.role === "ADMIN" ||
                [
                  "/",
                  "/analytics/recruitment",
                  "/analytics/salary",
                  "/jobs",
                  ...(user.role === "ANALYST"
                    ? ["/predictions", "/models"]
                    : []),
                ].includes(n.path),
            )
            .map((n) => (
              <NavLink key={n.path} to={n.path} end={n.path === "/"}>
                <n.icon size={18} />
                {n.label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-foot">
          <span className="avatar">{user.username[0].toUpperCase()}</span>
          <div>
            <strong>{user.username}</strong>
            <small>{user.role}</small>
          </div>
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
            Recruitment Analytics <span className="slash">/</span> Workspace
          </span>
          <span className="header-tag">BIG DATA PROJECT</span>
        </header>
        <main>
          <Workspace role={user.role} />
        </main>
        <footer>
          Recruitment Data Analytics & Salary Prediction{" "}
          <span>Apache Spark · MongoDB · FastAPI</span>
        </footer>
      </div>
    </div>
  );
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
