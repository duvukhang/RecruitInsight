import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
export const permissions: Record<string, readonly string[]> = {
  read: ['ADMIN', 'ANALYST', 'VIEWER'], predict: ['ADMIN', 'ANALYST'], manage: ['ADMIN'],
};
export const routePermission: Record<string, string> = {
  '/datasets': 'manage', '/sources': 'manage', '/quality': 'manage', '/etl': 'manage',
  '/settings': 'manage', '/users': 'manage', '/audit': 'manage',
  '/models': 'predict', '/predictions': 'predict',
};
export function can(role: string, permission = 'read') { return permissions[permission]?.includes(role) ?? false; }
export function Forbidden() {
  return <section className="empty forbidden" role="alert"><strong>403 · Không có quyền truy cập</strong>
    <span>Vai trò hiện tại không được phép mở chức năng này.</span><Link to="/">Về tổng quan</Link></section>;
}
export function PermissionGate({ role, permission, children }: { role: string; permission: string; children: ReactNode }) {
  return can(role, permission) ? <>{children}</> : <Forbidden />;
}
