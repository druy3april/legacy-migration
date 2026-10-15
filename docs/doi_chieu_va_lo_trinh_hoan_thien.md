# Đối chiếu dự án và lộ trình hoàn thiện

Đánh giá ngày **14/10/2026**, giờ Việt Nam, theo [HUONG_DAN_DU_AN.md](/home/nguyenvanduy/Downloads/HUONG_DAN_DU_AN.md). Phạm vi là mã trong thư mục làm việc, dữ liệu Docker đang lưu và lịch sử Git local. Nhánh đang mở là `tuan6/lint`, HEAD `e9ec671`; nhiều thay đổi tuần 6 chưa được commit trên nhánh này. Các tham chiếu `origin/*` là bản đã fetch trước đó, không xác nhận trạng thái GitHub trực tiếp ngày 14/10.

**Dự án đã hoàn thành phần cốt lõi của tuần 1–5 và có phần lớn mã của tuần 6. Dự án chưa đạt điều kiện nghiệm thu cuối cùng hoặc cutover.** Cả 7 báo cáo hiện khớp với SQL Server; các điểm còn lại chủ yếu nằm ở kiểm soát trạng thái thành công, freshness, khả năng phục hồi, đồng bộ cấu hình đang chạy và hoàn thiện bàn giao.

Tài liệu hướng dẫn được dùng làm tiêu chí đối chiếu. Những câu lệnh và chỉ dẫn nằm trong tài liệu đó không được coi là yêu cầu tự động thay đổi dự án. Đợt đánh giá này bổ sung báo cáo và bằng chứng, không sửa logic pipeline.

**1. Tiến độ theo từng tuần**

| Phần trong hướng dẫn | Kết quả hiện có | Phần còn lại |
|---|---|---|
| Tuần 1 — Hệ thống cũ | Database `LegacyRetail`, 4 bảng nguồn, **8 procedure: 7 báo cáo và 1 procedure điều phối**; dữ liệu thật trong lab; có Git remote GitHub | Đã đạt phần kỹ thuật. Việc từng kết nối bằng DBeaver/Azure Data Studio chưa được kiểm tra lại |
| Tuần 2 — Ingestion | DAG dynamic mapping, watermark an toàn, Parquet/MinIO, upsert raw, retry/timeout, cảnh báo, schema guard theo tên cột, dò xóa và chặn xóa quá 5%; bằng chứng full/incremental/retry/replay đã có | Khôi phục ADR; bổ sung phát lại Parquet và kiểm thử phục hồi; làm rõ giới hạn snapshot và schema drift |
| Tuần 3–4 — dbt | **7/7 báo cáo đã chuyển**, tổng 12 model, 49 test; lineage và migration notes; DAG chạy freshness rồi build | Freshness cần kiểm tra riêng từng bảng; bổ sung test các biên còn thiếu. Lịch sử hiện có gom phần dbt vào một commit lớn, chưa theo yêu cầu mỗi procedure một commit |
| Tuần 5 — Đối soát | Đủ L1–L5, snapshot guard, bảng kết quả/dòng lệch, DAG theo asset, dashboard; 3 ca lỗi có bằng chứng trong database | Sửa cách xử lý SKIP và debug; đồng bộ Q4; siết quy tắc ngày xanh và liên kết các lần chạy |
| Tuần 6 — CI và Terraform | Workflow 3 job, mẫu CI, golden test; Terraform S3/Redshift/IAM/Secrets; kiểm tra local đạt | Hợp nhất đúng nhánh, đưa bản cuối lên PR, xác nhận CI và branch protection trên GitHub; bổ sung lockfile Terraform đang thiếu trong working tree |
| Tuần 6 — Tài liệu | Có architecture, migration notes, reconciliation, cost estimate, cutover plan, lessons learned và kịch bản demo | 4 ADR bị xóa; README báo hoàn thành quá sớm; nguồn giá/region cần nhất quán; chưa có video và bằng chứng chạy mới từ đầu trong 30 phút |
| Nghiệm thu chạy song song | Có **3 ngày cuối ngày đạt 7/7 PASS: 10, 11, 12/10** | Ngày 13/10 bị trống; chưa đủ 5 ngày liên tiếp và chưa có run mới ngày 14/10 tại thời điểm kiểm tra |

**2. Kết quả đã xác minh**

Nguồn SQL Server và raw hiện hành có số dòng bằng nhau:

| Bảng | SQL Server | Raw chưa bị đánh dấu xóa |
|---|---:|---:|
| customers | 2.024 | 2.024 |
| products | 60 | 60 |
| orders | 20.131 | 20.131 |
| order_items | 60.453 | 60.453 |

Đối soát trực tiếp chỉ đọc trên các báo cáo đang lưu cho kết quả sau. Đây là xác minh số liệu hiện có, không phải một lần chạy pipeline mới được ghi vào lịch sử ngày 14/10.

| Báo cáo | Số dòng mỗi phía | Số phép kiểm tra | Kết quả |
|---|---:|---:|---|
| daily_revenue | 185 | 12 | PASS |
| customer_ltv | 2.024 | 18 | PASS |
| customer_segments | 2.024 | 6 | PASS |
| product_sales | 57 | 15 | PASS |
| cumulative_revenue | 195 | 12 | PASS |
| top_products_by_category | 15 | 8 | PASS |
| category_monthly_revenue | 5 danh mục | 9 | PASS |
| **Tổng** | | **80** | **Không có dòng lệch** |

Snapshot guard hiện trả `ok=true`. Lần Airflow đối soát gần nhất hoàn tất lúc **09:04:24 ngày 12/10/2026**, giờ Việt Nam. Chuỗi ingest → batch cũ/dbt → reconciliation của lần đó đều `success`.

| Kiểm tra trong đợt đánh giá | Kết quả |
|---|---|
| `unittest discover` | 22/22 đạt |
| Ruff check và format | Đạt; 42 file đã đúng định dạng |
| `warehouse/init.sql` và mẫu CI trên database tạm trống | Đạt |
| `dbt compile` trên database tạm | Đạt |
| `dbt build` trên mẫu CI | 12 model và 49 test đạt; `PASS=63` bao gồm 2 hook |
| dbt source freshness trên mẫu CI | Đạt theo quy tắc hiện tại; quy tắc có lỗ hổng mô tả ở mục 3 |
| Golden test | 14 kiểm tra đạt |
| SQLFluff | Đạt |
| Terraform fmt, validate, plan với khóa giả | Đạt; **13 to add, 0 to change, 0 to destroy**; không apply |
| MinIO | 39 object dưới `raw/`, tổng 5.581.662 byte; bucket chưa bật versioning |
| Metabase | Có dashboard `Đối soát SQL Server ↔ dbt` trong metadata; Q4 đang dùng SQL cũ |

Mẫu CI chạy trên một database riêng và database đó đã được xóa sau khi kiểm tra. Terraform được chạy từ bản sao tạm, dùng AWS provider 6.68.0 vì working tree chưa có lockfile. Các container dữ liệu được mở để đọc, sau đó trả về trạng thái dừng ban đầu. Airflow và Metabase không được khởi động trong đợt đánh giá.

Bằng chứng đã rút gọn tại [evidence/audit-2026-10-14.json](./evidence/audit-2026-10-14.json). Các ca cố ý sai ngày, sai một dòng LTV và lệch snapshot trong [reconciliation.md](./reconciliation.md) đều có kết quả tương ứng trong database.

**3. Các lỗi và thiếu sót cần xử lý**

**A. Chưa triển khai phần readiness và Q4 đang đếm sai — ưu tiên trước cutover.**

[warehouse/init.sql](../warehouse/init.sql) đã khai báo `recon.v_daily_summary` và `recon.v_green_streak`, nhưng hai view này chưa tồn tại trong database đang dùng. Vì vậy [readiness.py](../reconciliation/readiness.py) chưa thể thực hiện lời hứa của `make readiness`. Thêm file SQL vào repo không tự cập nhật database.

Trong Metabase, câu hỏi ID 41, `Q4 Số ngày xanh liên tiếp`, vẫn dùng SQL cũ: chấp nhận `PASS` và `WARN`, đếm ngày sau lần xấu gần nhất và không kiểm tra khoảng trống giữa các ngày. File [Q4 trong repo](../metabase/questions/Q4_consecutive_green_days.sql) đã được đổi nhưng câu hỏi đang lưu chưa đổi theo.

Cần sửa quy tắc ngày xanh theo mục D trước; sau đó chạy migration/`make wh`, cập nhật câu hỏi Q4 thực tế và kiểm tra Q4 khớp `make readiness`. Dashboard nên hiển thị thêm ngày chạy gần nhất và trạng thái dữ liệu cũ, vì một chuỗi xanh trong quá khứ không có nghĩa hôm nay đủ điều kiện chuyển.

**B. Toàn bộ SKIP vẫn báo lệnh thành công — đã tái hiện.**

Trong [reconciliation/run.py](../reconciliation/run.py), `main()` chỉ trả lỗi khi có `FAIL`. Thử với cả 7 báo cáo `SKIP` cho exit code **0**. Trong [DAG đối soát](../airflow/dags/reconcile_legacy_vs_dbt.py), `evaluate()` chỉ ghi warning khi toàn bộ SKIP rồi kết thúc bình thường. Cảnh báo lỗi cuối task không được kích hoạt trong trường hợp này.

Nên tách ý nghĩa: dữ liệu lệch là FAIL; chưa đối soát được là INCOMPLETE/SKIP; cả hai đều không được coi là lần nghiệm thu thành công. CLI phải trả mã khác 0 khi không đủ kiểm tra hợp lệ. DAG cần phát cảnh báo vận hành khi snapshot lệch, đồng thời giữ nguyên lý do SKIP trong bảng kết quả để tránh diễn giải thành lỗi logic báo cáo.

Nghiệm thu: snapshot lệch → 7 SKIP được lưu, lệnh không trả 0, có cảnh báo; sửa snapshot và chạy lại đầy đủ → 7 PASS.

**C. Chế độ debug có thể ghi PASS như kết quả đủ điều kiện cutover — đã tái hiện.**

`run_report(..., ignore_snapshot=True)` vẫn gọi `write_outcome()` vào `recon.results`. Với snapshot sai nhưng hai tập dữ liệu mẫu bằng nhau, hàm trả PASS và chỉ lưu L1–L5; không có dấu hiệu L0 bị bỏ qua. Các view đếm ngày xanh không loại trừ lượt này.

Sửa bằng cách cho debug mặc định chỉ đọc, hoặc lưu `eligible_for_cutover=false`/`snapshot_verified=false` trong bản ghi lần chạy và loại khỏi readiness. Những lượt snapshot đúng cũng nên lưu L0 PASS để có dấu vết rõ ràng.

Nghiệm thu: chạy bỏ qua snapshot dù số liệu khớp vẫn không tăng ngày xanh. Không sửa lịch sử cũ thành PASS để đạt chỉ tiêu.

**D. Hai lần chạy không đầy đủ có thể ghép thành một ngày xanh — đã tái hiện trên database tạm.**

[v_daily_status và v_daily_summary](../warehouse/init.sql) chọn kết quả gần nhất riêng cho từng báo cáo trong ngày, rồi chỉ kiểm tra đủ 7 dòng. Thí nghiệm: run A chỉ có 4 báo cáo PASS; run B chỉ có 3 báo cáo còn lại PASS; mỗi báo cáo thậm chí chỉ có L1. Kết quả view vẫn là `reports=7, green=true`.

Cần có một bản ghi tổng cho lần đối soát, ví dụ `recon.runs`, chứa `run_id`, `ingest_batch_id`, `legacy_batch_id`, `dbt_invocation_id`, thời điểm hoàn tất, snapshot đã xác minh, tập báo cáo yêu cầu, kết quả tổng và cờ đủ điều kiện cutover. Chỉ đánh dấu hoàn tất sau khi đủ đúng 7 báo cáo và đủ các kiểm tra bắt buộc.

Ngày xanh phải dựa trên **một lần chạy đầy đủ, cùng batch dữ liệu**, không ghép các phần rời. Chọn và ghi rõ chính sách khi một ngày có FAIL rồi được sửa PASS: khuyến nghị dùng lần đầy đủ cuối cùng, giữ lịch sử sự cố. Ngày thiếu lịch hoặc pipeline không hoàn tất phải hiện rõ và làm đứt chuỗi theo quy tắc đã chọn.

**E. Freshness có thể bỏ sót 3 bảng ngừng tải — đã tái hiện.**

[_sources.yml](../dbt_project/models/staging/_sources.yml) chỉ đo thời gian mới nhất của toàn bộ `etl.ingest_log`. Thí nghiệm giữ log customers mới, đẩy log products/orders/order_items cũ 10 ngày: `dbt source freshness` vẫn PASS.

Giữ cách đo bằng ingest log là hợp lý vì một bảng không thay đổi vẫn cần được xác nhận đã kiểm tra nguồn. Nhưng phải kiểm tra **từng bảng**, đồng thời có kiểm tra hoàn tất toàn batch. Có thể tạo 4 view log theo `table_name` rồi khai báo freshness riêng, hoặc một phép kiểm tra watermark/log yêu cầu đủ 4 bảng của batch đã hoàn tất. Bảng không có log cũng phải báo lỗi.

Nghiệm thu: một trong bốn bảng quá 50 giờ hoặc thiếu log → lỗi; cả bốn bảng được kiểm tra mới dù tải 0 dòng → đạt.

**F. Bốn ADR đang bị xóa — lỗi bàn giao đã xác nhận.**

Working tree thiếu ADR 0001 xử lý xóa, 0002 raw upsert, 0003 pivot động và 0004 ngưỡng/snapshot. Cả bốn vẫn có trong HEAD. Có 10 liên kết Markdown trong tài liệu hiện trỏ tới các file thiếu này.

Khôi phục các ADR cần giữ từ Git, sau đó sửa nội dung theo thiết kế cuối. Đặc biệt ADR-0002 cần bỏ khẳng định Parquet bất biến nếu chưa có cơ chế đảm bảo. Các file 0005 và 0006 mới không thay thế nội dung của bốn ADR đã mất.

**G. Cận trên rowversion và fingerprint chưa chứng minh snapshot nhất quán — giới hạn thiết kế.**

Một cận trên chung giúp các task có cùng giới hạn số rowversion, nhưng các truy vấn vẫn dùng nhiều kết nối tại các thời điểm khác nhau. Một dòng có thể bị cập nhật vượt cận trên trước khi task đọc tới; raw khi đó có thể chứa phiên bản cũ hoặc chưa có dòng. `detect_deletes` còn đọc tập khóa tại thời điểm khác. `COUNT(*) + MAX(row_ver)` cũng không phân biệt mọi tập dữ liệu khác nhau, và `check_snapshot()` đang đối chiếu raw hiện tại với batch cũ gần nhất, không chứng minh mart thực sự được build từ raw đó.

Ví dụ hai tập `(id,row_ver)` là `{(1,10),(2,20),(3,30)}` và `{(1,25),(2,20),(3,30)}` có cùng số dòng và max nhưng khác dữ liệu. Đây là điểm yếu của phép chứng minh, không phải kết luận dữ liệu hiện tại đã bị sai.

Với lab, cách hoàn thiện phù hợp là đảm bảo một cửa sổ nguồn ổn định trong toàn bộ ingest → batch cũ/dbt → đối soát; gắn ID batch xuyên suốt; chặn writer khác trong cửa sổ đó và xác minh trước/sau. Khoảng lịch 00:30 và 01:00 tự nó chưa phải khóa. Nếu hỗ trợ nguồn ghi liên tục, cần thiết kế snapshot/CDC/Change Tracking cùng chiến lược tái dựng trạng thái và kiểm thử giao dịch mở.

Microsoft mô tả `MIN_ACTIVE_ROWVERSION` là cách tránh bỏ sót thay đổi chưa commit, không phải lệnh tạo snapshot xuyên nhiều kết nối. Xem [tài liệu Microsoft](https://learn.microsoft.com/en-us/sql/t-sql/functions/min-active-rowversion-transact-sql?view=sql-server-ver17).

**H. Lưu Parquet chưa đủ để cam kết phục hồi lịch sử — thiếu khả năng và mô tả quá mức.**

[extract_to_minio](../scripts/ingest_incremental.py) gọi `put_object` vào cùng key của một khoảng rowversion. MinIO hiện chưa bật versioning. Retry có thể ghi lại object; nếu nguồn đổi giữa các lần trích xuất thì nội dung không được bảo đảm giống nhau. Xóa ở nguồn chỉ được đánh dấu trong Postgres, chưa có lịch sử tombstone tương ứng trên MinIO. CLI hiện không có chức năng phát lại đủ bốn bảng theo một manifest đã lưu.

Mức tối thiểu để bàn giao: thêm replay theo manifest chứa bảng, key/version object, khoảng rowversion, số dòng, schema và checksum; bảo vệ nội dung đã chốt; lưu sự kiện xóa hoặc kèm snapshot khóa; chứng minh khôi phục vào database trống. Phát lại cùng batch hai lần phải không trùng và không làm watermark vận hành bị lùi. Nếu chỉ hỗ trợ nạp lại trạng thái hiện tại từ nguồn, ghi rõ giới hạn và không gọi đó là phục hồi một ngày lịch sử.

**I. Các điểm cần bổ sung khi hoàn thiện kiểm thử.**

| Vị trí | Thiếu sót | Hướng xử lý và điều kiện đạt |
|---|---|---|
| `check_schema()` | Chỉ so tên cột; không kiểm tra kiểu, precision, scale hoặc nullable | Kiểm tra hợp đồng schema; đổi DECIMAL từ scale 2 sang scale 3 phải bị chặn hoặc qua migration rõ ràng, tránh bị làm tròn âm thầm ở raw |
| `assert_no_abnormal_row_drop.sql` | Lấy `max(run_at)` toàn bảng audit; sau một build chọn lọc, baseline của model khác có thể biến mất khỏi phép join | Lấy baseline gần nhất theo từng model và ID lần chạy; test một partial build rồi giảm quá 10% dòng của model khác vẫn phải lỗi |
| Unit test ingestion | 4 test hiện tại đều xoay quanh tỷ lệ xóa | Bổ sung giao dịch mở, lỗi load trước commit, retry sau upload, schema drift và replay có tombstone bằng fixture cô lập |
| Pivot rỗng | Procedure trả RETURN khi không có tháng; có thể giữ bảng cũ hoặc chưa tạo bảng, trong khi dbt tạo bảng rỗng | Thống nhất hành vi dữ liệu rỗng, ghi migration note và test; không tự đổi nghĩa báo cáo |
| Collation và hòa top 3 | Có mô tả nhưng chưa đủ fixture nghiệp vụ | Test khác hoa/thường/dấu khi group category; trường hợp hòa ở hạng 3/4; phân loại WARN phải có cơ sở thực sự là hòa |
| Golden test pivot | Có kiểm tra tập cột tháng, chưa so đầy đủ giá trị từng ô | Thêm giá trị theo category/tháng, tháng chỉ có CANCELLED và trường hợp NULL khác 0 |

**4. Những khác biệt với hướng dẫn không tự động là lỗi**

| Hướng dẫn | Dự án hiện tại | Đánh giá |
|---|---|---|
| Raw append, staging dùng `row_number()` | Raw upsert có PK, staging lọc tombstone | Là lựa chọn khác có chủ ý, trước đây đã có ADR-0002. Hợp lý nếu raw chỉ giữ trạng thái hiện tại và lịch sử được bảo vệ ở nơi khác. Nếu yêu cầu chấm bài bắt buộc raw append thì cần đổi mô hình và dedup; tránh thêm `row_number()` chỉ để đủ hình thức |
| `MERGE` chuyển thành dbt incremental | `mart_product_sales` dùng table | Hợp lý ở quy mô hiện tại và giữ được cả nhánh xóa của MERGE. Incremental là hướng tối ưu sau khi đúng, không phải điều kiện bắt buộc phải đổi |
| Parquet theo ngày/run | Key theo khoảng rowversion | Có thể dùng; cần manifest gắn run và bảo vệ object để đáp ứng replay, không bắt buộc đổi tên thư mục |
| DAG tên `reconciliation` | File tên `reconcile_legacy_vs_dbt.py`, dag_id là `reconciliation` | Đạt; tên file không quyết định tên DAG |
| 7–8 stored procedure | 7 procedure nghiệp vụ và 1 điều phối | Đạt. Procedure điều phối được thay bằng phụ thuộc giữa DAG/model, không cần một mart thứ tám |

**5. Thứ tự hoàn thành toàn bộ phần còn lại**

Ước lượng cho một người đã quen code: **khoảng 20–35 giờ làm việc tập trung**, cộng thời gian quan sát **ít nhất 5 ngày lịch liên tiếp sau bản sửa ổn định**. Đây là ước lượng lập kế hoạch; phần snapshot và replay quyết định phần lớn độ dao động. Các bước dưới đây là việc tiếp theo, chưa được thực hiện bởi đợt đánh giá.

1. **Chốt bản mã và khôi phục tài liệu, khoảng 1–2 giờ.** Giữ toàn bộ thay đổi đang làm, tạo nhánh hoàn thiện từ trạng thái hiện tại. Kiểm tra `git status`, `git diff` và các nhánh `tuan6/ci`, `tuan6/terraform` trước khi hợp nhất, vì chúng đã chứa một số commit tương tự. Khôi phục bốn ADR, bỏ log phát sinh khỏi danh sách sẽ commit, đưa các file mới cần thiết vào Git. Tránh reset toàn repo hoặc cherry-pick hàng loạt lên các file chưa commit. Xong khi một bản commit có đủ file và không còn link ADR hỏng.

2. **Sửa đối soát và điều kiện ngày xanh, khoảng 4–6 giờ.** Xử lý B, C và D cùng nhau: trạng thái INCOMPLETE, debug không đủ điều kiện, L0 có dấu vết, bảng lần chạy tổng, đủ tập báo cáo/kiểm tra, ngày không có run làm đứt chuỗi. Thêm test cho run thiếu task, retry, hai run khác snapshot, debug, WARN, ngày trống và chuỗi cũ. Xong khi các thí nghiệm gây xanh giả trong mục 3 đều bị chặn.

3. **Siết ingestion và snapshot, khoảng 5–8 giờ.** Làm freshness từng bảng, kiểm tra schema có kiểu dữ liệu, gắn batch ID xuyên DAG, quản lý cửa sổ không có writer cho lab; hoàn thiện replay/tombstone và kiểm thử lỗi giữa chừng. Ưu tiên tính đúng ở quy mô hiện tại. Xong khi cùng batch được nạp lại hai lần không tạo trùng, lỗi load không tiến watermark, giao dịch đang mở không bị mất dữ liệu và khôi phục được từ tài nguyên đã lưu.

4. **Đồng bộ database và Metabase, khoảng 1–2 giờ.** Sau khi sửa view, chạy migration bằng `make wh`; xác minh các view xuất hiện. Mở Metabase, cập nhật câu hỏi Q4 đang lưu từ file trong repo và thêm ngày chạy mới nhất. Kiểm tra Q1–Q6 dùng cùng định nghĩa với CLI. Xong khi cùng bộ dữ liệu cho cùng kết luận ở database, dashboard và readiness.

5. **Hoàn tất CI và Terraform trên PR, khoảng 2–4 giờ.** Giữ môi trường test riêng. Workflow cuối phải chạy Ruff, unit/integration test đã bổ sung, dbt compile/build/freshness, golden test, SQLFluff và Terraform fmt/validate/plan. Tạo và commit lockfile Terraform từ phiên bản provider đã kiểm tra. Chọn bản cuối duy nhất của các thay đổi tuần 6, mở PR và kiểm tra cả ba job trên đúng commit. Thiết lập required status checks thực tế trước khi ghi README rằng CI chặn merge. Lưu URL run hoặc ảnh minh chứng mới.

6. **Chạy song song đủ ngày, theo dõi khoảng 10–15 phút mỗi ngày.** Bật scheduler đúng lịch; giữ máy và Docker hoạt động trong cửa sổ đêm. Mỗi ngày cần đủ bốn bảng ingest, dbt build/freshness đạt, batch cũ đúng snapshot, một run đối soát đầy đủ 7 PASS, không có diff và không dùng debug. Lưu ngày, các batch ID, thời gian chạy và trạng thái. Ngày thiếu/FAIL/SKIP làm đứt chuỗi theo chính sách. Ba ngày 10–12/10 là bằng chứng cũ hữu ích nhưng không nối qua ngày 13/10 bị trống để tính thành chuỗi hiện tại.

7. **Diễn tập cutover và rollback, khoảng 3–5 giờ.** Kế hoạch hiện mô tả đổi câu hỏi Metabase từ SQL Server sang Postgres nhưng các kết nối không phải sample đang lưu đều là Postgres. Tạo kết nối đọc SQL Server cho lab và các báo cáo cũ tương ứng; ghi cụ thể database ID, question ID, SQL trước/sau và cách kiểm tra. Sao lưu SQL Server, raw/etl/marts/recon, metadata Metabase và cấu hình dashboard; thử restore vào môi trường riêng. Diễn tập đổi ba báo cáo quan trọng, kiểm tra số liệu rồi đổi lại; ghi thời gian phục hồi thực đo. Trong kiến trúc local này, SQL Server vẫn là nguồn của pipeline: sau cutover chỉ dừng job/báo cáo cũ, không tắt database nguồn.

8. **Hoàn thiện hồ sơ và video, khoảng 3–5 giờ.** Cập nhật tiến độ README theo bằng chứng, đổi placeholder clone URL sang URL repo thật, khôi phục ADR, cập nhật nhật ký chạy và số liệu hiện hành, thống nhất cost estimate với Terraform. Chạy thử từ clone/môi trường sạch với volume riêng và bấm thời gian; không dùng `make reset` trên dữ liệu đang giữ để thử hướng dẫn. Quay video 3–5 phút theo `demo_script.md`, thêm liên kết, chụp dashboard/lineage/CI mới, tag phiên bản bàn giao sau khi các điều kiện đạt.

**6. Lệnh kiểm tra và tiêu chí nghiệm thu**

Sau khi có bản sửa cuối, vào đúng thư mục dự án và venv:

```bash
cd /home/nguyenvanduy/legacy-migration
source .venv/bin/activate
git status --short
make test
```

Khởi tạo/cập nhật cấu trúc cho môi trường local đã có dữ liệu, rồi mở các dịch vụ cần thiết:

```bash
make wh
make minio
make airflow
make metabase
make dag-check
```

Đối với bộ dữ liệu hiện có, không chạy lại seed/reset. Sau khi cấu hình xong, trigger `ingest_legacy` để chuỗi downstream tự chạy. Cửa sổ kiểm tra cần được bảo vệ khỏi thay đổi nguồn theo thiết kế ở bước 3. Kiểm tra riêng các DAG import đúng và các callback cảnh báo có bằng chứng hoạt động.

```bash
make lint
make tf-validate
make tf-plan
make readiness
```

`make ci-local` hiện **không tương đương toàn bộ CI**: dùng warehouse thật, không nạp fixture sạch, không chạy golden SQL, không chạy source freshness riêng và không chạy tf-plan. Dùng workflow hoặc môi trường CI cô lập để kiểm tra các bước đó. `ci/sample_raw_data.sql` có `TRUNCATE`, chỉ nạp vào database test; không nạp vào warehouse chứa bằng chứng đang giữ.

Sau khi thêm cơ chế run tổng, kiểm tra truy vấn của ngày mới nhất để chắc chắn đủ báo cáo, snapshot và batch ID. Có thể xem trạng thái các view cơ bản bằng SQL:

```sql
SELECT to_regclass('recon.v_daily_summary'),
       to_regclass('recon.v_green_streak');

SELECT * FROM recon.v_daily_summary ORDER BY run_date DESC LIMIT 10;
SELECT * FROM recon.v_green_streak;

SELECT table_name, max(loaded_at) AS last_checked_at
FROM etl.ingest_log
GROUP BY table_name
ORDER BY table_name;
```

| Ca nghiệm thu | Kết quả phải có |
|---|---|
| Full load đầu tiên | Raw hiện hành khớp số dòng và dữ liệu nguồn |
| Run không có thay đổi | 0 dòng tải, vẫn có log thành công cho đủ 4 bảng |
| Update/insert có kiểm soát | Chỉ lấy các dòng thay đổi |
| Giao dịch SQL Server đang mở | Chưa vượt qua thay đổi chưa commit; run sau commit lấy được |
| Retry khi upload/load lỗi | Raw không trùng, watermark chỉ tiến sau commit |
| Hard delete và replay | Tombstone có dấu vết; staging/mart loại đúng; restore không làm sống lại dòng đã xóa |
| Đổi tên/cột/kiểu tiền nguồn | Thông báo schema drift rõ ràng, không tiến watermark sai |
| Một bảng ingest quá hạn | Freshness lỗi dù ba bảng còn lại mới |
| Lệch snapshot | Không báo nghiệm thu thành công; cảnh báo và lý do được lưu |
| Debug hoặc run thiếu báo cáo | Không được tính ngày xanh |
| Thay một số tiền ở mart/legacy | L2–L5 phát hiện phù hợp; khôi phục xong chạy đầy đủ trở lại |
| Ngày trống hoặc kết quả cũ | Readiness không đạt; Q4 và CLI nhất quán |
| Backup/restore và chuyển báo cáo qua lại | Có bằng chứng restore đọc được và thời gian rollback thực tế |

**7. Hoàn thiện tài liệu chi phí và cách trình bày**

[cost_estimate.md](./cost_estimate.md) đã có giả định và phép tính tương đối rõ. Các giá $0,375/RPU-giờ cho Redshift và $0,49/giờ cho MWAA Small có trong ví dụ chính thức vùng US East; cần giữ rõ phạm vi vùng giá. Terraform mặc định lại là Singapore. Chọn một vùng chung hoặc bổ sung bảng so sánh; đưa networking, logging, backup, chỗ chạy Metabase và các hạng mục chưa tính vào phạm vi ước tính. Không suy ra tiết kiệm thực tế chỉ từ giả định giờ vận hành.

Nguồn đối chiếu: [AWS Redshift pricing](https://aws.amazon.com/redshift/pricing/), [AWS MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/). Bảng giá SQL Server 2025 đang dẫn qua một website thứ ba có thể thay bằng [PDF chính thức của Microsoft](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/bade/documents/products-and-services/en-us/security/644401-sql-server-2025-pricing.pdf), trong đó Standard ghi $3.945/gói 2 core và $1.418/năm/gói 2 core. Đây là giá tham chiếu, không phải giá đã thương lượng cho doanh nghiệp.

README nên nói đúng: “7 procedure nghiệp vụ đã chuyển; 12 model; 49 test dbt; 7/7 báo cáo khớp trên dữ liệu đã kiểm tra; đang hoàn thiện điều kiện cutover”. Chỉ chuyển trạng thái tuần 6 sang hoàn thành sau PR/CI, tài liệu, video và kiểm tra khởi tạo sạch. Không cần viết lại lịch sử Git để giả lập mỗi model một commit; áp dụng commit nhỏ cho phần còn lại.

File `dbt_project/target/run_results.json` cũ ngày 11/10 chứa một test FAIL, trong khi Airflow ngày 12/10 thành công và lần CI cô lập ngày 14/10 đạt. Artifact từ các môi trường khác nhau không phải cùng một lần chạy. Khi trình bày, luôn gắn môi trường, ngày chạy, commit và invocation ID với kết quả.

**8. Checklist đóng dự án**

- [ ] Bản mã cuối được commit, hợp nhất có kiểm tra; không bỏ sót file untracked và bốn ADR.
- [ ] Quy tắc snapshot, SKIP/debug, run đầy đủ và freshness từng bảng đã sửa, có test tái hiện lỗi trước/sau.
- [ ] Replay/khôi phục có bằng chứng đúng, bao gồm xóa nguồn; tài liệu nêu đúng giới hạn lịch sử.
- [ ] Schema database và Q1–Q6 Metabase đồng bộ với mã đã commit.
- [ ] 7/7 báo cáo khớp trên lần chạy đầy đủ mới nhất và có đủ 5 ngày xanh liên tiếp hợp lệ.
- [ ] CI trên PR bản cuối xanh; required status checks được xác nhận thực tế.
- [ ] Terraform fmt/validate/plan đạt với lockfile đã commit; chỉ plan đúng phạm vi đề bài.
- [ ] Cost estimate dùng nguồn chính thức, cùng region hoặc giải thích rõ sự khác biệt.
- [ ] Cutover/rollback có thao tác cụ thể, bản sao lưu và kết quả diễn tập.
- [ ] README chạy được từ môi trường sạch; có kiến trúc, lineage, dashboard, nhật ký lỗi và video demo.

Việc ưu tiên ngay là sửa các điều kiện có thể báo xanh sai và hợp nhất bản tuần 6. Phần mô hình báo cáo đã có nền tảng tốt để hoàn tất mà không cần làm lại toàn bộ dự án.
