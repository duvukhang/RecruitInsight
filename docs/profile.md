# Hồ sơ cá nhân

Mở http://localhost:8080/profile hoặc bấm avatar góc phải trên. ADMIN, ANALYST và VIEWER đều có hồ sơ riêng, lưu trong MongoDB, dùng cùng cơ chế đăng nhập hiện hữu.

- Sửa tên hiển thị, email liên hệ, tổ chức, giới thiệu và màu avatar. Email chỉ là thông tin liên hệ, chưa có xác minh email. Avatar dùng chữ đầu và màu, chưa hỗ trợ tải ảnh.
- Tên đăng nhập và vai trò chỉ đọc. API tự lấy tài khoản từ bearer token; không nhận user ID, role hoặc enabled khi sửa hồ sơ.
- Đổi mật khẩu phải nhập mật khẩu hiện tại; mật khẩu mới ít nhất 12 ký tự, gồm hoa/thường/số/ký hiệu. Tối đa 5 lần thử mỗi phút cho mỗi tài khoản. Sau khi đổi, mọi access/refresh token cũ bị thu hồi; cần đăng nhập lại.
- Tab bảo mật liệt kê các phiên refresh còn hiệu lực của chính tài khoản, phân trang 10 phiên; trình duyệt được suy ra từ User-Agent thiết bị khai báo. Ngày cập nhật là lần đăng nhập/refresh gần nhất, không phải thời điểm hoạt động cuối cùng. Không hiển thị token hoặc hash.
- Đăng xuất mọi thiết bị có xác nhận và thu hồi cả phiên hiện tại. Không có thao tác thu hồi từng thiết bị.

Thay đổi hồ sơ, mật khẩu và thu hồi phiên được ghi audit theo actor/target/action, không ghi nội dung giới thiệu, email, mật khẩu hoặc token. Trường hồ sơ mới là tùy chọn nên tài khoản cũ dùng username và màu xanh ngọc mặc định.
