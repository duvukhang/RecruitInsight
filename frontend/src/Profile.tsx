import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Check, Fingerprint, KeyRound, LogOut, Save, ShieldCheck, UserRound } from 'lucide-react';
import { api, clearSession } from './api';
import { ConfirmDialog, EmptyState, ErrorState, RoleBadge } from './components/insights';

export const avatarColors: Record<string, string> = { cyan: '#22b8cf', blue: '#5489ff', violet: '#a48aff', emerald: '#32c99a', amber: '#e3ad48' };
const colorLabels: Record<string, string> = { cyan: 'Xanh ngọc', blue: 'Xanh lam', violet: 'Tím', emerald: 'Xanh lá', amber: 'Vàng' };
type Fields = { display_name: string; email: string; organization: string; bio: string; avatar_color: string };
const blank: Fields = { display_name: '', email: '', organization: '', bio: '', avatar_color: 'cyan' };
function date(value?: string) { return value ? new Date(value).toLocaleString('vi-VN') : 'Chưa ghi nhận'; }
function browserName(value: string) {
  if (!value) return 'Phiên đăng nhập cũ';
  const name = value.includes('Edg/') ? 'Microsoft Edge' : value.includes('Firefox/') ? 'Firefox' : value.includes('Chrome/') ? 'Google Chrome' : value.includes('Safari/') ? 'Safari' : 'Ứng dụng / trình duyệt';
  return name + (value.includes('Mobile') ? ' · Di động' : ' · Máy tính');
}
export default function Profile() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['my-profile'], queryFn: () => api('/auth/profile') });
  const [sessionPage, setSessionPage] = useState(1);
  const sessions = useQuery({ queryKey: ['my-sessions', sessionPage], queryFn: () => api('/auth/sessions?page=' + sessionPage) });
  const [fields, setFields] = useState<Fields>(blank), [tab, setTab] = useState('info');
  const [notice, setNotice] = useState(''), [revokeOpen, setRevokeOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState(''), [password, setPassword] = useState(''), [confirm, setConfirm] = useState(''), [passwordError, setPasswordError] = useState('');
  const user = query.data?.data;
  useEffect(() => { if (user) setFields(Object.fromEntries(Object.keys(blank).map(key => [key, user[key] ?? blank[key as keyof Fields]])) as Fields); }, [user]);
  const save = useMutation({ mutationFn: () => api('/auth/profile', { method: 'PATCH', body: JSON.stringify(fields) }),
    onSuccess: result => { client.setQueryData(['my-profile'], result); window.dispatchEvent(new Event('app-user-changed')); setNotice('Đã lưu hồ sơ cá nhân.'); }, onError: error => setNotice(error.message) });
  function signedOut(message: string) {
    sessionStorage.setItem('auth-notice', message); clearSession(); window.dispatchEvent(new Event('app-session-expired'));
  }
  const changePassword = useMutation({ mutationFn: () => api('/auth/password', { method: 'POST', body: JSON.stringify({ current_password: currentPassword, password }) }),
    onSuccess: () => { setCurrentPassword(''); setPassword(''); setConfirm(''); signedOut('Đã đổi mật khẩu và thu hồi các phiên cũ. Vui lòng đăng nhập lại.'); }, onError: error => setPasswordError(error.message) });
  const revoke = useMutation({ mutationFn: () => api('/auth/revoke-sessions', { method: 'POST' }),
    onSuccess: () => signedOut('Đã đăng xuất mọi thiết bị. Vui lòng đăng nhập lại.'), onError: error => setNotice(error.message) });
  if (query.isPending) return <EmptyState>Đang tải hồ sơ của bạn…</EmptyState>;
  if (query.error) return <ErrorState message={query.error.message} retry={() => query.refetch()} />;
  const initial = Array.from(String(fields.display_name || user.username))[0].toUpperCase();
  return <div className="profile-layout">
    <section className="profile-identity">
      <div className="profile-cover"><span>RECRUITINSIGHT / TÀI KHOẢN</span><Fingerprint aria-hidden="true" /></div>
      <div className="profile-identity-body"><div className="profile-avatar" style={{ '--avatar-color': avatarColors[fields.avatar_color] } as React.CSSProperties}>{initial}</div>
        <h2>{user.display_name}</h2><div className="muted">@{user.username}</div><RoleBadge role={user.role} />
        <div className="profile-account-facts"><span>Tham gia<strong>{date(user.created_at)}</strong></span><span>Đăng nhập gần nhất<strong>{date(user.last_login_at)}</strong></span><span>Phiên đang hoạt động<strong>{sessions.data?.meta.total ?? '—'}</strong></span></div>
        {user.role === 'ADMIN' && <Link className="profile-admin-link" to="/users"><ShieldCheck size={16} /> Quản lý người dùng</Link>}
      </div>
    </section>
    <section className="profile-content">
      <div className="profile-tabs" role="tablist" aria-label="Cài đặt hồ sơ">{[['info', 'Thông tin cá nhân', UserRound], ['security', 'Bảo mật & phiên', ShieldCheck]].map(([key, label, Icon]: any) => <button key={key} id={'tab-' + key} role="tab" aria-selected={tab === key} aria-controls={'panel-' + key} onClick={() => { setTab(key); setNotice(''); }}><Icon size={17} />{label}</button>)}</div>
      {notice && <div className="notice" role="status">{notice}</div>}
      <div role="tabpanel" id={'panel-' + tab} aria-labelledby={'tab-' + tab}>
        {tab === 'info' ? <form className="profile-form" onSubmit={event => { event.preventDefault(); setNotice(''); save.mutate(); }}>
          <div className="profile-section-heading"><span className="section-number">01</span><div><h2>Thông tin của bạn</h2></div></div>
          <div className="profile-form-grid"><label>Tên hiển thị<input required maxLength={80} value={fields.display_name} onChange={e => setFields({ ...fields, display_name: e.target.value })} autoComplete="name" /></label><label>Tên đăng nhập<input value={user.username} readOnly /></label>
            <label>Email liên hệ<input type="email" maxLength={254} value={fields.email} onChange={e => setFields({ ...fields, email: e.target.value })} autoComplete="email" /></label><label>Tổ chức<input maxLength={120} value={fields.organization} onChange={e => setFields({ ...fields, organization: e.target.value })} autoComplete="organization" /></label>
            <label className="wide">Giới thiệu<textarea rows={4} maxLength={600} value={fields.bio} onChange={e => setFields({ ...fields, bio: e.target.value })} placeholder="Vai trò, lĩnh vực bạn quan tâm…" /><small>{fields.bio.length}/600 ký tự</small></label></div>
          <fieldset className="avatar-palette"><legend>Màu avatar</legend>{Object.entries(avatarColors).map(([key, color]) => <label key={key} title={colorLabels[key]}><input type="radio" name="avatar-color" value={key} checked={fields.avatar_color === key} onChange={() => setFields({ ...fields, avatar_color: key })} aria-label={colorLabels[key]} /><span style={{ background: color }}>{fields.avatar_color === key && <Check size={18} />}</span></label>)}</fieldset>
          <div className="profile-form-footer"><button className="primary" disabled={save.isPending}><Save size={16} /> {save.isPending ? 'Đang lưu…' : 'Lưu thay đổi'}</button></div>
        </form> : <div className="profile-security">
          <form onSubmit={event => { event.preventDefault(); setPasswordError(''); if (password !== confirm) { setPasswordError('Mật khẩu xác nhận chưa khớp.'); return; } changePassword.mutate(); }}>
            <div className="profile-section-heading"><span className="section-number"><KeyRound size={19} /></span><div><h2>Đổi mật khẩu</h2></div></div>
            <label>Mật khẩu hiện tại<input required type="password" maxLength={256} autoComplete="current-password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>
            <div className="profile-form-grid"><label>Mật khẩu mới<input required type="password" minLength={12} maxLength={256} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label><label>Xác nhận mật khẩu mới<input required type="password" minLength={12} maxLength={256} autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} /></label></div>
            <div className="data-foot">Ít nhất 12 ký tự, có chữ hoa, chữ thường, số và ký hiệu.</div>{passwordError && <ErrorState message={passwordError} />}<button className="primary" disabled={changePassword.isPending}>{changePassword.isPending ? 'Đang đổi…' : 'Đổi mật khẩu'}</button>
          </form>
          <div className="profile-session-heading"><div><h2>Phiên đăng nhập</h2></div><button onClick={() => setRevokeOpen(true)}><LogOut size={15} /> Đăng xuất mọi thiết bị</button></div>
          {sessions.isPending ? <EmptyState>Đang tải các phiên…</EmptyState> : sessions.error ? <ErrorState message={sessions.error.message} retry={() => sessions.refetch()} /> : <><div className="session-list">{sessions.data?.data.map((session: any, index: number) => <div className="session-row" key={index}><span className="session-icon"><Fingerprint size={22} /></span><div><strong>{browserName(session.user_agent)}</strong><small>Bắt đầu: {date(session.created_at)}</small><small>Cập nhật: {date(session.last_seen_at || session.created_at)}</small></div><span className="badge green">Còn hiệu lực</span></div>)}</div>{!sessions.data?.data.length && <EmptyState>Chưa có phiên refresh đang hoạt động.</EmptyState>}
            <div className="pagination"><button disabled={sessionPage === 1} onClick={() => setSessionPage(sessionPage - 1)}>Trước</button><span>Trang {sessionPage}</span><button disabled={sessionPage * 10 >= sessions.data?.meta.total} onClick={() => setSessionPage(sessionPage + 1)}>Sau</button></div></>}
        </div>}
      </div>
    </section>
    {revokeOpen && <ConfirmDialog title="Đăng xuất mọi thiết bị?" pending={revoke.isPending} onClose={() => setRevokeOpen(false)} onConfirm={() => revoke.mutate()}><div>Phiên hiện tại cũng sẽ bị thu hồi. Bạn cần đăng nhập lại bằng mật khẩu hiện có.</div>{revoke.error && <ErrorState message={revoke.error.message} />}</ConfirmDialog>}
  </div>;
}
