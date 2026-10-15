# Hoàn thiện kiểm chứng và vận hành dự án di chuyển báo cáo

Các báo cáo SQL Server đã có model dbt tương ứng, nhưng SKIP/debug/run thiếu có
thể bị tính xanh và file snapshot chưa đủ cho phục hồi lịch sử. Thay đổi bổ sung
run header đủ bảy báo cáo, fingerprint toàn nội dung, batch/build ID, freshness
từng bảng và snapshot manifest chứa tombstone.

Có hai bộ dashboard BI, sửa quyền pivot sau DROP/CREATE và link chuyển nguồn
localhost:3001 với guard readiness; rollback không cần warehouse hoạt động.
Bổ sung video portfolio ba phút, ADR, chi phí cùng region và bằng chứng thực tế.

Validation: 44 Python/SQL tests; 12 models/49 dbt tests; 15 golden assertions;
7/7 báo cáo khớp; restore snapshot thật hai lần; diễn tập HTTP route OLD–NEW–OLD;
Terraform 13 add/0 change/0 destroy, không apply. CI GitHub ba job đều xanh.

Hiện 1/5 ngày xanh thật; chưa thực hiện Go/cutover thật. Cold-start 30 phút trên
máy mới chưa đo. PR giữ mở để review, không bỏ qua ruleset main.
