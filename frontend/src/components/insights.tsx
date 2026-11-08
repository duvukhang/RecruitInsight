import { useEffect, useRef, type ReactNode, type KeyboardEvent } from 'react';
import type { LucideIcon } from 'lucide-react';

export function StatCard({ label, value, note, icon: Icon }: { label: string; value: ReactNode; note?: string; icon: LucideIcon }) {
  return <article className="stat"><Icon aria-hidden="true" /><span>{label}</span><strong>{value ?? '—'}</strong>{note && <small>{note}</small>}</article>;
}
export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">RECRUITINSIGHT / KHÔNG GIAN PHÂN TÍCH</div><h1>{title}</h1></div>{children}</div>;
}
export function InsightPanel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-title"><div><h2>{title}</h2>{subtitle && <p className="muted">{subtitle}</p>}</div></div>{children}</section>;
}
export function RoleBadge({ role }: { role: string }) { return <span className="badge role-badge">{({ ADMIN: 'Quản trị', ANALYST: 'Phân tích', VIEWER: 'Người xem' } as Record<string, string>)[role] || role}</span>; }
export function ModelBadge({ active }: { active: boolean }) { return <span className="badge">{active ? 'Mô hình đang dùng' : 'Ứng viên'}</span>; }
export function DataSourceBadge({ demo, source, permission }: { demo: boolean; source?: string; permission?: string }) {
  return <span className={`badge source-badge ${demo ? 'synthetic' : ''}`}>{demo ? 'DEMO tổng hợp' : 'Nguồn ngoài'} · {source || 'Chưa rõ nguồn'}{permission && ` · ${permission}`}</span>;
}
export function EmptyState({ children }: { children: ReactNode }) { return <div className="empty" role="status">{children}</div>; }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="error" role="alert">{message}{retry && <button onClick={retry}>Thử lại</button>}</div>; }
export function FilterToolbar({ children }: { children: ReactNode }) { return <div className="filter-bar" role="group" aria-label="Bộ lọc dữ liệu">{children}</div>; }
function trapDialogTab(event: KeyboardEvent<HTMLDialogElement>) {
  if (event.key !== 'Tab' || event.ctrlKey || event.metaKey) return;
  const dialog = event.currentTarget;
  const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')).filter(element => element.getClientRects().length > 0);
  const first = controls[0], last = controls[controls.length - 1];
  if (!first) { event.preventDefault(); dialog.focus(); }
  else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
export function ConfirmDialog({ title, children, pending, onClose, onConfirm }: {
  title: string; children: ReactNode; pending: boolean; onClose: () => void; onConfirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="confirm-dialog" aria-labelledby="confirm-title" onKeyDown={trapDialogTab} onCancel={e => { e.preventDefault(); if (!pending) onClose(); }}>
    <form onSubmit={e => { e.preventDefault(); onConfirm(); }}><h2 id="confirm-title">{title}</h2>{children}
      <div className="actions"><button type="button" disabled={pending} onClick={onClose}>Hủy</button><button type="submit" disabled={pending}>{pending ? 'Đang lưu…' : 'Xác nhận'}</button></div>
    </form></dialog>;
}
export function DetailDialog({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="confirm-dialog job-dialog" aria-label="Chi tiết tuyển dụng" onKeyDown={trapDialogTab} onCancel={event => { event.preventDefault(); onClose(); }}>{children}</dialog>;
}
