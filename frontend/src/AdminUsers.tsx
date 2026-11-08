import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import { ConfirmDialog, EmptyState, ErrorState, InsightPanel, RoleBadge } from './components/insights';
type User = { id: string; username: string; role: string; enabled: boolean };
const roles = ['VIEWER', 'ANALYST', 'ADMIN'];
export default function AdminUsers() {
  const [q, setQ] = useState(''), [role, setRole] = useState(''), [status, setStatus] = useState(''), [page, setPage] = useState(1);
  const [action, setAction] = useState<{ kind: string; user?: User } | null>(null);
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [nextRole, setNextRole] = useState('VIEWER');
  const [error, setError] = useState('');
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['users', q, role, status, page], queryFn: () => api(`/users?page=${page}&q=${encodeURIComponent(q)}${role ? '&role=' + role : ''}${status ? '&enabled=' + status : ''}`) });
  const mutation = useMutation({ mutationFn: async () => {
    const user = action?.user;
    if (action?.kind === 'create') return api('/users', { method: 'POST', body: JSON.stringify({ username, password, role: nextRole }) });
    if (action?.kind === 'reset') return api(`/users/${user!.id}/reset-password`, { method: 'POST', body: JSON.stringify({ password }) });
    if (action?.kind === 'revoke') return api(`/users/${user!.id}/revoke-sessions`, { method: 'POST' });
    return api(`/users/${user!.id}`, { method: 'PATCH', body: JSON.stringify(action?.kind === 'role' ? { role: nextRole } : { enabled: !user!.enabled }) });
  }, onSuccess: () => {
    setAction(null); setPassword(''); client.invalidateQueries({ queryKey: ['users'] }); client.invalidateQueries({ queryKey: ['audit'] });
    window.dispatchEvent(new Event('app-user-changed'));
    window.dispatchEvent(new CustomEvent('app-notice', { detail: 'Đã lưu thay đổi tài khoản và thu hồi phiên khi cần.' }));
  }, onError: error => setError(error.message) });
  function open(kind: string, user?: User) { setPassword(''); setUsername(''); setError(''); setNextRole(user?.role || 'VIEWER'); setAction({ kind, user }); }
  return <InsightPanel title="Người dùng">
    <div className="admin-toolbar"><label>Tìm tài khoản<input value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /></label>
      <label>Vai trò<select value={role} onChange={e => { setRole(e.target.value); setPage(1); }}><option value="">Tất cả</option>{roles.map(r => <option key={r}>{r}</option>)}</select></label>
      <label>Trạng thái<select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Tất cả</option><option value="true">Hoạt động</option><option value="false">Đã khóa</option></select></label>
      <button onClick={() => open('create')}>Tạo người dùng</button></div>
    {query.isPending ? <EmptyState>Đang tải người dùng…</EmptyState> : query.error ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : <>
      <div className="table-scroll"><table><thead><tr><th>Tài khoản</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
        {query.data?.data.map((u: User) => <tr key={u.id}><td>{u.username}</td><td><RoleBadge role={u.role} /></td><td>{u.enabled ? 'Hoạt động' : 'Đã khóa'}</td><td><div className="actions">
          <button onClick={() => open('role', u)}>Đổi quyền</button><button onClick={() => open('status', u)}>{u.enabled ? 'Vô hiệu hóa' : 'Mở lại'}</button>
          <button onClick={() => open('reset', u)}>Đặt lại mật khẩu</button><button onClick={() => open('revoke', u)}>Thu hồi phiên</button>
        </div></td></tr>)}</tbody></table></div>
      {!query.data?.data.length && <EmptyState>Không có tài khoản phù hợp.</EmptyState>}
      <div className="pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Trước</button><span>Trang {page} · {query.data?.meta.total} tài khoản</span><button disabled={page * 25 >= query.data?.meta.total} onClick={() => setPage(page + 1)}>Sau</button></div>
    </>}
    {action && <ConfirmDialog title={`${({ create: 'Tạo người dùng', role: 'Đổi vai trò', status: 'Đổi trạng thái', reset: 'Đặt lại mật khẩu', revoke: 'Thu hồi mọi phiên' } as Record<string, string>)[action.kind]}${action.user ? ' · ' + action.user.username : ''}`} pending={mutation.isPending} onClose={() => { setAction(null); setPassword(''); }} onConfirm={() => mutation.mutate()}>
      {action.kind === 'create' && <label>Tên đăng nhập<input required minLength={3} maxLength={128} pattern="[A-Za-z0-9][A-Za-z0-9_.-]*" value={username} onChange={e => setUsername(e.target.value)} autoComplete="off" /></label>}
      {['create', 'role'].includes(action.kind) && <label>Vai trò mới<select value={nextRole} onChange={e => setNextRole(e.target.value)}>{roles.map(r => <option key={r}>{r}</option>)}</select></label>}
      {['create', 'reset'].includes(action.kind) && <label>Mật khẩu mới (ít nhất 12 ký tự, có hoa, thường, số, ký hiệu)<input required type="password" minLength={12} maxLength={256} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label>}
      {action.kind === 'status' && <div className="notice">{action.user?.enabled ? 'Tài khoản sẽ không thể đăng nhập; các phiên hiện có bị thu hồi.' : 'Tài khoản có thể đăng nhập lại bằng mật khẩu hiện có.'}</div>}
      {action.kind === 'revoke' && <div className="notice">Người dùng phải đăng nhập lại trên mọi thiết bị.</div>}
      {error && <ErrorState message={error} />}
    </ConfirmDialog>}
  </InsightPanel>;
}

export function AuditLogs() {
  const [page, setPage] = useState(1), [action, setAction] = useState('');
  const query = useQuery({ queryKey: ['audit', page, action], queryFn: () => api(`/audit-logs?page=${page}&action=${encodeURIComponent(action)}`) });
  return <InsightPanel title="Nhật ký quản trị"><div className="admin-toolbar"><label>Hành động<input value={action} onChange={e => { setAction(e.target.value); setPage(1); }} placeholder="USER_UPDATE" /></label><button onClick={() => query.refetch()}>Làm mới</button></div>
    {query.isPending ? <EmptyState>Đang tải nhật ký…</EmptyState> : query.error ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : <>
      <div className="table-scroll"><table><thead><tr><th>Thời gian</th><th>Hành động</th><th>Người thực hiện</th><th>Đối tượng</th></tr></thead><tbody>{query.data?.data.map((r: any) => <tr key={r.id}><td>{new Date(r.created_at).toLocaleString('vi-VN')}</td><td>{r.action}</td><td>{r.actor_id || '—'}</td><td className="mono">{r.resource_id || '—'}</td></tr>)}</tbody></table></div>
      {!query.data?.data.length && <EmptyState>Chưa có nhật ký phù hợp.</EmptyState>}<div className="pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Trước</button><span>Trang {page}</span><button disabled={page * 25 >= query.data?.meta.total} onClick={() => setPage(page + 1)}>Sau</button></div></>}
  </InsightPanel>;
}
