# Quản trị người dùng và phiên đăng nhập

Giữ ba role ADMIN/ANALYST/VIEWER và bootstrap từ cấu hình hiện có. Policy server tập trung tại `domain/permissions.py`; frontend tại `permissions.tsx`. Backend luôn là nơi quyết định quyền.

| Chức năng | ADMIN | ANALYST | VIEWER |
| --- | --- | --- | --- |
| Analytics/jobs, metadata published | Có | Có | Có |
| Registry/diagnostics, prediction và lịch sử riêng | Có | Có | Không |
| Upload/staged/ETL, raw reports/export | Có | Không | Không |
| Train/activate/rollback, normalization/FX | Có | Không | Không |
| Users/audit/system | Có | Không | Không |

Trang Người dùng: tìm username theo prefix, lọc role/trạng thái, tạo, đổi quyền, khóa/mở, reset mật khẩu, thu hồi phiên; mutation có hộp xác nhận native dialog và trạng thái pending/error. Username 3–128, ký tự ASCII chữ/số/_.-, unique case-sensitive. Password 12–256 ký tự, có hoa/thường/số/ký hiệu. Không trả hash/token; không ghi password vào audit. CLI users create dùng chung service/policy.

Đổi role/status/password hoặc revoke-sessions tăng auth_version atomically trên user, xóa refresh sessions. JWT và refresh đều kiểm epoch với user DB; token cũ không dùng được, kể cả refresh race. User cũ không có epoch dùng 0. Claims role không quyết định quyền. UI kiểm `/auth/me` khi mở phiên, focus và mỗi 30 giây; session bị thu hồi đưa về đăng nhập và xóa Query cache. URL trái quyền hiển thị 403 trước mount trang bảo vệ; menu và shortcut theo cùng policy.

## Last-admin trên Mongo standalone

Mọi mutation quản lý user/CLI được tuần tự hóa bằng unique `_id=users` trong `admin_mutation_locks`. Check cuối cùng và update nằm trong critical section. Không cho tự disable. Không cho hạ quyền/khóa admin hoạt động cuối cùng. Hai requests đồng thời chỉ một request hạ được admin khi còn hai admin; request kia nhận 409.

**Khóa không có TTL/tự hết hạn**: owner cũ có thể resume sau khi hết lease, vì vậy TTL không bảo vệ invariant trên standalone Mongo. Khi process chết trong critical section, hệ thống fail closed: mutation trả ADMIN_WRITE_BUSY, đọc và đăng nhập vẫn hoạt động. Thao tác phục hồi cần người vận hành dừng tất cả API/CLI writers, kiểm tra admin hoạt động trong DB, ghi nhận sự cố rồi xóa duy nhất document lock `users` bằng công cụ DB quản trị; chỉ start writers sau khi kiểm tra. Không xóa lock khi process khác còn có thể chạy. Phiên nâng cấp không tự chạy thao tác phục hồi này.

Users mutation và audit outbox commit cùng một Mongo document. Audit event chứa ID/actor/action/target/timestamp, không chứa password. Ghi sang audit_logs bằng `$setOnInsert` ID ổn định; replay không trùng. Khi API crash giữa hai bước, GET audit-logs replay tối đa 100 users có outbox mỗi lần, không mất dấu vết user mutation. Đây là eventual delivery, không phải transaction đa collection. Legacy audit detail objects không được trả ra API.

API chỉ ADMIN:

- GET/POST `/users`; GET hỗ trợ q/role/enabled/page/page_size (tối đa 100).
- PATCH `/users/{id}` với role/enabled; extra/null/empty bị từ chối.
- POST `/users/{id}/reset-password` với password mới.
- POST `/users/{id}/revoke-sessions`.
- GET `/audit-logs` với action/actor_id/page/page_size.

401 cho phiên không hợp lệ, 403 trước khi tìm target với non-admin, 404 target không tồn tại cho admin, 409 username/invariant/concurrent writer, 422 schema. History predictions vẫn scope user_id; ADMIN không đọc được history cá nhân người khác qua prediction detail.
