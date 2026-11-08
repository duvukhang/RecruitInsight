# Fixtures tự tạo

`tinix-shape.synthetic.jsonl` là 100 dòng **tổng hợp tự tạo cho kiểm thử mapping**, chỉ mô phỏng tên cột của adapter Tinix. Không sao chép corpus Tinix/VietJobs, không phải quan sát thị trường, tên doanh nghiệp luôn có SYNTHETIC. Có thể tái sử dụng fixture này để kiểm thử RecruitInsight cùng source repository; không suy rộng quyền đó sang dữ liệu public của bên thứ ba.

Các tests còn sinh 1.000 dòng trong tmp để kiểm tra streaming/byte cap, không commit corpus hoặc text tuyển dụng gốc. Permission status của fixture là SYNTHETIC_FIXTURE.
