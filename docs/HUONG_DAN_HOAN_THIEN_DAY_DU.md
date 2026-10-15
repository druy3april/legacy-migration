# Hướng dẫn hoàn thiện toàn bộ dự án Legacy Migration

**Dành cho project `/home/nguyenvanduy/legacy-migration`, kiểm tra ngày 14/10/2026.**

Tài liệu này gồm đánh giá hiện trạng, toàn bộ mã cần thêm/sửa dưới dạng một bản vá đầy đủ, lệnh triển khai, kiểm thử, cập nhật Metabase, chạy song song, cutover/rollback, CI, chi phí và demo. Bạn thực hiện trên project đang có; không cần viết lại các phần đã chạy đúng.

**Cập nhật 15/10/2026: bản vá đã được áp dụng vào project này. Không áp dụng lại phụ lục.**
Phụ lục B là toàn bộ code thêm/sửa cho mục 5, không phải phần việc làm thêm.
Source hiện tại đã có các sửa tiếp theo; xem `docs/evidence/completion-2026-10-15.md`
để biết trạng thái mới nhất. Nội dung kiểm tra ngày 14/10 bên dưới là lịch sử.
Mã đề xuất ban đầu được dựng và kiểm tra trong bản sao riêng, bằng database/bucket tạm. Tài liệu hướng dẫn gốc được dùng làm tiêu chí đối chiếu; các câu yêu cầu trong đó không được coi là lệnh tự động chạy trên máy bạn.

## 1. Dự án đã đến đâu?

| Yêu cầu trong hướng dẫn gốc | Bằng chứng của project hiện tại | Việc còn lại |
|---|---|---|
| Tuần 1: SQL Server, dữ liệu và 7–8 procedure | Có 7 procedure nghiệp vụ + 1 procedure điều phối | Giữ lại; sửa nhánh pivot khi nguồn rỗng |
| Tuần 2: incremental, watermark, retry, delete, schema drift | Có ingestion 4 bảng, upsert, MinIO, Airflow, tombstone và các bằng chứng thử nghiệm | Kiểm tra kiểu schema; file bất biến; snapshot/replay cả tombstone; đồng bộ hành vi CLI và DAG |
| Tuần 3–4: chuyển đủ procedure sang dbt | Có 12 model, 7 mart, 49 dbt test; migration notes, lineage | Freshness từng bảng; baseline row count từng model; ghi nhận full build gắn batch |
| Tuần 5: đối soát 5 cấp, cảnh báo, dashboard | Đối chiếu đọc dữ liệu hiện tại: 7/7 báo cáo PASS, 80 phép so, 0 dòng lệch; có 3 ca lỗi cố ý | Chặn SKIP/debug/run thiếu bị tính xanh; kiểm tra cùng dữ liệu; cập nhật Q4 thực tế |
| Tuần 6: CI và Terraform | Có workflow, fixture, Terraform; đã validate/plan được | Commit phần còn untracked và lockfile, mở PR, chứng minh status checks chặn merge |
| Tuần 6: chi phí và cutover | Có bản tài liệu ban đầu | Đồng nhất region/giả định; tạo kết nối BI nguồn cũ; diễn tập chuyển và quay về |
| Hoàn tất bàn giao | Có README, ảnh, kịch bản demo | 5 ngày xanh thật, video 3–5 phút, thử chạy từ clone sạch, lưu bằng chứng |

Số dòng nguồn/raw active tại lần audit: customers **2.024**, products **60**, orders **20.131**, order_items **60.453**. Lịch sử có kết quả xanh ngày **10, 11, 12/10/2026**; chưa có bằng chứng ngày 13. Vì vậy chưa thể kết luận đủ 5 ngày liên tiếp.

Phần chuyển logic nghiệp vụ đã làm tốt và khá đầy đủ. Phần còn thiếu chủ yếu là độ tin cậy khi vận hành và bằng chứng nghiệm thu. Không dùng một tỷ lệ phần trăm để đánh đồng “đã có code” với “đã triển khai và chứng minh chạy đúng”.

### Các lỗi cụ thể cần sửa

1. CLI chỉ trả lỗi khi FAIL: toàn SKIP vẫn trả mã 0; DAG có thể xanh dù chưa đối soát được.
2. `--ignore-snapshot` có thể lưu PASS dùng nhầm cho nghiệm thu.
3. Cách gộp theo ngày có thể cộng 4 báo cáo của run A với 3 của run B thành đủ 7.
4. Freshness dùng max thời điểm toàn ingest log: một bảng mới che ba bảng quá cũ.
5. Count + max rowversion không chứng minh toàn bộ nội dung khớp. Cận rowversion chung cũng không tạo snapshot transaction chung.
6. Chưa có ràng buộc rõ giữa ingestion, batch cũ và lần build dbt thực sự đã hoàn tất.
7. Incremental Parquet cùng key có thể bị ghi đè; thiếu replay đầy đủ trạng thái xóa.
8. Kiểm tra schema chỉ có tên cột, bỏ sót đổi precision/scale, độ dài, nullable.
9. Row-count audit lấy mốc thời gian chung có thể bỏ mất baseline của model không nằm trong một partial build.
10. Procedure pivot `RETURN` sớm khi không có đơn hàng, có thể giữ lại bảng hôm trước.
11. Database thật chưa có hai view readiness; Q4 Metabase đang lưu query cũ, chấp nhận WARN và không kiểm tra khoảng trống ngày.
12. Bốn ADR bị xóa khỏi working tree; README ghi “hoàn thành” và khẳng định branch protection khi chưa đủ bằng chứng.

### Khác biệt kiến trúc được giữ lại

Hướng dẫn gốc đề xuất raw append và staging lấy phiên bản mới nhất. Project đang dùng **raw upsert + tombstone**. Bản vá giữ phương án này, bổ sung snapshot Parquet bất biến để có đường phục hồi rõ ràng và ghi lại trong ADR-0002. Đây là khác biệt có chủ đích, không phải đã thực hiện đúng nguyên văn yêu cầu append. Nếu người chấm bắt buộc append, cần thống nhất lại tiêu chí trước khi nộp; chuyển sang append là một thay đổi kiến trúc khác.

## 2. Mã bổ sung hoạt động thế nào?

```text
ingest đủ 4 bảng + kiểm tra xóa
  → source/raw fingerprint khớp
  → lưu snapshot + manifest lên MinIO
  → etl.ingest_batches
       ├→ legacy batch: kiểm tra fingerprint trước/sau + ingest_run_id
       └→ dbt wrapper: freshness 4 bảng + full build + ingest_run_id
  → recon.runs RUNNING
  → 7 báo cáo, đủ các kiểm tra L0–L5
  → kiểm tra lại snapshot, đóng run
  → PASS và eligible_for_cutover=true
  → một run đầy đủ/ngày VN, 5 ngày lịch liên tiếp
```

Fingerprint dùng SHA-256 nội dung tất cả cột nghiệp vụ và rowversion, sắp theo khóa, bên raw lọc tombstone. Snapshot phục hồi lưu cả dòng active lẫn tombstone. Hai mục đích này khác nhau và đều được kiểm tra.

Khóa advisory PostgreSQL chỉ bảo vệ những đường ghi đi qua pipeline này. Hash trước/sau là cơ chế phát hiện nguồn thay đổi trong lab; nó không thay thế distributed snapshot hoặc CDC. Khi cutover phải có cửa sổ đóng băng ghi. Khi nguồn ghi liên tục ở production, cần thiết kế snapshot/CDC có mốc LSN và quyền hạn vận hành phù hợp.

**Quy tắc trạng thái:**

| Trường hợp | Kết quả |
|---|---|
| Full build, đúng batch, đủ 7 báo cáo, đủ check, đều PASS | Được tính ngày xanh |
| Một báo cáo PASS khi chạy riêng | Hữu ích để debug; không đủ điều kiện cutover |
| Toàn SKIP, snapshot khác hoặc thiếu kiểm tra | CLI trả lỗi; DAG không được xanh |
| WARN | Giữ để điều tra; không tính ngày xanh |
| `--ignore-snapshot` | Không ghi kết quả; trả mã 2 |
| `make dbt-build SELECT=...` chỉ build một phần | Ghi PARTIAL, trả mã 2; phải full build lại trước nghiệm thu |
| Ingestion của ngày cũ hoặc build mới nhất hỏng | Không dùng PASS cũ để chứng nhận lần hiện tại |

Các bản ghi đối soát lịch sử không có run header vẫn được giữ, nhưng không tự “nâng cấp” thành ngày xanh theo tiêu chuẩn mới. Chuỗi nghiệm thu bắt đầu lại khi triển khai và chạy full pipeline đúng quy tắc mới.

## 3. Kết quả kiểm tra bản mã trong tài liệu

Đã kiểm tra trên bản sao riêng ngày 14/10/2026:

- Ruff lint và format: PASS.
- **39 test Python/SQL: PASS**, gồm 5 integration test PostgreSQL; khi chạy unit riêng không có database test thì 5 test SQL được skip có chủ đích.
- dbt compile/build: **12 model + 49 test PASS**.
- Freshness: **4 nguồn theo từng bảng PASS**.
- **15 golden assertions PASS**, bao gồm so toàn bộ 9 ô pivot của fixture và phân biệt NULL với 0.
- End-to-end SQL Server → MinIO → PostgreSQL → dbt → đối soát: **7/7 PASS**.
- Retry ingestion không tạo trùng; debug không ghi kết quả; nguồn đổi làm SKIP và exit khác 0.
- Hard delete được lưu thành tombstone; phục hồi cùng snapshot hai lần PASS.
- Partial build mới hơn chặn nghiệm thu dù trước đó từng full build PASS.
- Procedure pivot trả bảng rỗng khi nguồn hết đơn hàng.
- Import 4 DAG trong container Airflow riêng không có mạng: PASS. Đây là kiểm tra import; bạn vẫn cần thử scheduler/Asset thật ở mục 8.
- Terraform cấu hình hiện có đã fmt/validate/plan PASS: **13 add, 0 change, 0 destroy**, không apply; bản vá thêm lockfile provider AWS 6.68.0.
- Migration schema cũ → mới trên database test: PASS; dữ liệu raw và lịch sử cũ được giữ nguyên.
- Bản vá trích từ chính Markdown: kiểm tra áp dụng được với working tree hiện tại; áp dụng và hoàn tác trên bản sao đều khớp SHA-256 của cả 39 file.

Chưa có bằng chứng từ bản triển khai của bạn cho: GitHub PR CI mới, branch protection, 5 ngày xanh sau sửa, cutover/rollback, video và thời gian chạy clone sạch. Đây là những bước bạn thực hiện bên dưới, không phải kết quả đã đạt.

## 4. Sao lưu trước khi áp dụng

Các lệnh dưới đây dùng Bash; từ terminal hiện tại bạn có thể chạy `bash` rồi làm tiếp. Giữ cùng terminal để dùng các biến đã đặt. Không chạy `make reset`, không xóa volume, không `git reset --hard`.

```bash
cd /home/nguyenvanduy/legacy-migration
migration_saved_umask=$(umask)
umask 077
migration_backup_dir="$PWD/backups/pre-completion-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$migration_backup_dir"
git status --short > "$migration_backup_dir/git-status.txt"
git rev-parse HEAD > "$migration_backup_dir/head.txt"
git diff --binary > "$migration_backup_dir/working-tree.patch"
git diff --cached --binary > "$migration_backup_dir/staged.patch"
tar --exclude='./.git' --exclude='./.venv' --exclude='./backups' \
    --exclude='./logs' --exclude='./dbt_project/target' --exclude='./terraform/.terraform' \
    -czf "$migration_backup_dir/source-before.tar.gz" .
```

Bản tar lưu cả file chưa commit và `.env`; giữ riêng tư, không đẩy thư mục backups lên GitHub. Patch code ở cuối tài liệu dựa trên **working tree đã kiểm tra**, gồm các thay đổi chưa commit của bạn, không chỉ dựa trên commit `e9ec671`.

Tạm dừng Airflow trong lúc nâng cấp. Nếu đang có tác vụ chạy, đợi nó kết thúc rồi dừng:

```bash
docker compose stop airflow
docker compose up -d --wait postgres sqlserver minio
docker compose exec -T postgres bash -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$migration_backup_dir/warehouse.dump"
docker compose exec -T postgres bash -c \
  'pg_dump -U "$POSTGRES_USER" -d metabase -Fc' \
  > "$migration_backup_dir/metabase.dump"
docker compose exec -T postgres bash -c \
  'pg_dump -U "$POSTGRES_USER" -d airflow -Fc' \
  > "$migration_backup_dir/airflow.dump"
docker compose exec -T sqlserver mkdir -p /var/opt/mssql/backup
PYTHONPATH=scripts:. .venv/bin/python - <<'PY'
from generate_data import get_connection
with get_connection() as conn:
    conn.autocommit(True)
    cur = conn.cursor()
    path = '/var/opt/mssql/backup/pre_completion.bak'
    cur.execute('BACKUP DATABASE LegacyRetail TO DISK=%s WITH COPY_ONLY, INIT, CHECKSUM', (path,))
    while cur.nextset():
        pass
    cur.execute('RESTORE VERIFYONLY FROM DISK=%s WITH CHECKSUM', (path,))
    while cur.nextset():
        pass
print('SQL Server backup verified')
PY
docker compose cp sqlserver:/var/opt/mssql/backup/pre_completion.bak \
  "$migration_backup_dir/LegacyRetail.bak"
# Khôi phục quyền mặc định trước khi tạo/sửa mã nguồn.
umask "${migration_saved_umask:-022}"
```

Nếu metadata database `airflow` hoặc `metabase` chưa từng được tạo thì bỏ qua dump tương ứng, không coi file dump rỗng là thành công. Với project đã audit, hai database này có tồn tại. `RESTORE VERIFYONLY` kiểm tra cấu trúc backup; một lần restore vào database thử vẫn cần thiết nếu muốn chứng minh khả năng phục hồi SQL Server hoàn chỉnh.

## 5. Trích bản vá từ chính file này và áp dụng

Bản vá đầy đủ nằm ở phụ lục cuối, không có đoạn `...` thay cho phần code phải viết. Lệnh này trích đúng khối bản vá; chưa sửa file nào:

```bash
cd /home/nguyenvanduy/legacy-migration
python3 - <<'PY'
from pathlib import Path
text = Path('docs/HUONG_DAN_HOAN_THIEN_DAY_DU.md').read_text()
section = text.rsplit('<!-- BEGIN_PROJECT_PATCH -->', 1)[1]
section = section.split('<!-- END_PROJECT_PATCH -->', 1)[0]
patch = section.split('~~~~diff\n', 1)[1].rsplit('\n~~~~', 1)[0] + '\n'
Path('/tmp/legacy-complete.patch').write_text(patch)
print('Đã trích /tmp/legacy-complete.patch')
PY
git apply --stat /tmp/legacy-complete.patch
git apply --check /tmp/legacy-complete.patch
```

Chỉ khi `--check` không báo lỗi mới áp dụng:

```bash
(umask 022; git apply /tmp/legacy-complete.patch)
git diff --check
```

Nếu `--check` báo file/context khác, không dùng `--reject` hoặc ép ghi đè. Thường là bạn đã sửa source sau ngày audit, hoặc đã áp dụng rồi. Kiểm tra `git apply -R --check /tmp/legacy-complete.patch`: nếu lệnh này thành công thì patch đang có trên cây file. Nếu cả hai đều lỗi, đối chiếu file được báo với bản backup và các đoạn diff của chính file đó.

Bản vá không commit, không push, không đổi nhánh, không tự sửa database. Nó khôi phục 4 ADR, thêm mã và test, sửa các file đang có. Xem danh sách file ở phụ lục.

## 6. Nâng schema và chạy thủ công lần đầu

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-dbt.txt -r requirements-dev.txt
make wh
make minio
```

`make wh` áp dụng `warehouse/init.sql`: tạo bảng/header/view mới bằng lệnh có thể chạy lại. Nó không tự tạo run header cho kết quả cũ. Đừng chạy fixture `ci/sample_raw_data.sql` vào warehouse thật vì fixture có TRUNCATE.

Nạp lại định nghĩa stored procedure để sửa pivot rỗng, giữ dữ liệu nguồn:

```bash
docker compose exec -T sqlserver bash -c \
  '/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d LegacyRetail -b' \
  < sql/02_stored_procedures.sql
```

Chạy đúng chuỗi, dừng nếu một bước lỗi:

```bash
set -o pipefail
mkdir -p artifacts
make ingest-all 2>&1 | tee artifacts/ingest-first.log
make legacy-batch 2>&1 | tee artifacts/legacy-first.log
make dbt-build 2>&1 | tee artifacts/dbt-first.log
make recon 2>&1 | tee artifacts/recon-first.log
```

Bốn lệnh tách nhau để dễ xem log; nếu một lệnh thất bại, sửa lỗi trước khi chạy lệnh kế. Tránh `make batch` hoặc gọi dbt trực tiếp cho lần nghiệm thu: các đường đó không ghi batch/build header mới. Dùng `make legacy-batch`, `make dbt-build`.

Kiểm tra trong `make wh-sql`:

```sql
SELECT run_id, finished_at, manifest_key
FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 3;

SELECT build_id, ingest_run_id, status, invocation_id, artifact_path
FROM etl.dbt_builds ORDER BY started_at DESC LIMIT 3;

SELECT run_id, status, eligible_for_cutover, started_at, finished_at
FROM recon.runs ORDER BY started_at DESC LIMIT 3;

SELECT * FROM recon.v_daily_summary ORDER BY run_date DESC LIMIT 10;
SELECT * FROM recon.v_green_streak;
```

Kỳ vọng mới nhất: build PASS; run PASS + eligible=true; ngày hiện tại đủ 7 PASS, 0 diff, green=true. Bộ specs hiện tại sinh **87 checks** khi thêm L0 cho mỗi báo cáo. Đếm nhanh:

```sql
SELECT report, count(*) AS checks, bool_and(status = 'PASS') AS all_pass
FROM recon.results
WHERE run_id = (SELECT run_id FROM recon.runs ORDER BY started_at DESC LIMIT 1)
GROUP BY report ORDER BY report;
```

Nếu SKIP vì nguồn thay đổi, đợi nguồn yên rồi chạy lại cả chuỗi. Không dùng `--ignore-snapshot` để biến một lần chưa đạt thành đạt.

## 7. Kiểm thử bắt buộc trước khi bật lịch

```bash
make test
make ci-local 2>&1 | tee artifacts/ci-local.log
make integration-test 2>&1 | tee artifacts/integration-test.log
```

`make ci-local` tạo database `test_ci_<id>` riêng, chạy Ruff, 39 test, dbt compile/build/freshness, 15 golden assertions, SQLFluff; xóa database test trong `finally`; sau đó chạy Terraform validate/plan. Nếu máy chưa có Terraform, cài theo `terraform/README.md`, hoặc kiểm tra phần data riêng bằng:

```bash
PYTHONPATH=scripts:. .venv/bin/python scripts/ci_local.py
```

`make integration-test` tạo database SQL Server `GuideTest_<id>`, Postgres `test_e2e_<id>`, database phục hồi `restore_e2e_<id>` và bucket `guide-test-<id>`. Chỉ tạo/xóa tài nguyên do lần test đó sở hữu. Test có chủ đích sinh SKIP và PARTIAL; các exit khác 0 ở những bước đó là kết quả mong đợi. Thành công cuối cùng phải có `E2E PASS` và exit 0 của toàn script.

### Ma trận nghiệm thu kỹ thuật

| Ca thử | Cách thực hiện | Phải thấy |
|---|---|---|
| Full load và retry | integration-test | Lượt 2 sum(row_count)=0; khóa không nhân đôi |
| Nguồn sửa sau đối soát | integration-test | Snapshot sai → SKIP, CLI exit 1 |
| Debug | integration-test | Count recon.results không tăng, exit 2 |
| Hard delete | integration-test | `_deleted_at` được ghi; build/recon vẫn khớp |
| Replay | integration-test | RESTORE PASS hai lần, cả tombstone khớp |
| Partial build | integration-test | PARTIAL; đối soát tiếp không eligible |
| Pivot nguồn rỗng | integration-test | Bảng cũ không giữ doanh thu hôm trước |
| Hai run 4+3 báo cáo | test_warehouse_guards | Không thành ngày xanh |
| Bỏ một ngày lịch | test_warehouse_guards | Chuỗi bị ngắt |
| Dữ liệu cũ nhiều ngày | test_warehouse_guards | Green streak cũ không còn đủ điều kiện |
| Một bảng mới, ba bảng cũ | test_warehouse_guards | Freshness riêng phản ánh bảng cũ |
| Thiếu log một bảng | test_warehouse_guards | Mốc freshness 1970, không PASS giả |
| Đổi numeric scale | test_operational_guards | Contract phát hiện |
| Manifest sai hash | test_operational_guards | Từ chối restore |
| Phiên bản code/schema sạch | ci-local + PR CI | Cả test và golden đều xanh |

Các bằng chứng giao dịch đang mở, schema thêm cột và clear task đã có trong `docs/evidence/tuan2*.md`. Khi muốn tái diễn sau bản vá, làm trên môi trường thử hoặc dùng database riêng. `scripts/hold_transaction.sql` sửa một customer thật; không chạy giữa chuỗi 5 ngày đang nghiệm thu mà không ghi nhận thay đổi đó.

## 8. Bật lại Airflow và kiểm tra Asset chain

Trước khi bật, kiểm tra `.env` phần cảnh báo. Khi chỉ diễn tập, để trống ba biến `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_APP_PASSWORD` để callback chỉ ghi log; nếu dùng email thật, xác nhận người nhận bạn muốn thông báo.

```bash
make airflow
make dag-check
make airflow-pass
```

Mở Airflow ở `http://localhost:8080`. Khi triển khai lần đầu, pause `simulate_source_activity` để nguồn không đổi trong lần kiểm tra. Kiểm tra lần lượt:

1. Trigger **ingest_legacy** và chờ tất cả task thành công, nhất là task tổng kết xuất manifest.
2. Asset raw kích hoạt **legacy_nightly_batch** và **transform_dbt**.
3. Chờ cả hai thành công, rồi **reconciliation** tự chạy.
4. Task evaluate phải thành công và `recon.runs.eligible_for_cutover=true`.
5. Bật lại simulate và lịch ingestion sau khi nghiệm thu chuỗi đầu tiên.

Nếu DAG mới chưa hiện, đợi scheduler parse lại rồi dùng `make dag-check`.

**Lỗi quyền đọc sau khi làm theo bản hướng dẫn trước ngày 15/10/2026:** `umask 077`
ở bước backup có thể còn hiệu lực khi `git apply`, khiến file source mới có quyền
`600`. Container chạy bằng user `airflow` (UID 50000), không đọc được file do user
host sở hữu. DAG vẫn nằm trên đĩa nhưng không xuất hiện trên UI; lỗi quét file có
thể chỉ nằm trong log dag-processor, không xuất hiện ở list-import-errors.

Khôi phục umask của terminal và chỉ bổ sung quyền đọc cho các file source được
mount vào Airflow (không đổi quyền `.env` hoặc backups):

```bash
umask "${migration_saved_umask:-022}"
python3 - <<'PY'
from pathlib import Path
import stat
for directory in ['airflow/dags', 'scripts', 'reconciliation', 'dbt_project']:
    for path in Path(directory).rglob('*'):
        if {'__pycache__', 'target', 'logs', '.venv', '.git'} & set(path.parts):
            continue
        if path.is_file() and path.suffix in {'.py', '.sql', '.yml', '.yaml', '.sh'}:
            mode = stat.S_IMODE(path.stat().st_mode)
            path.chmod(mode | stat.S_IRGRP | stat.S_IROTH)
PY
docker compose exec -T airflow test -r /opt/airflow/dags/ingest_legacy.py
make dag-check
```

Sau khi sửa quyền, dag-processor cần đến lượt quét lại danh sách file (có thể
mất vài phút). Nếu không có tác vụ đang chạy, dùng `docker compose restart airflow`
để quét ngay; sau đó refresh trang DAGs và bỏ bộ lọc tìm kiếm/trạng thái.
Không cần xóa DAG hoặc reset dữ liệu. Nếu transform lỗi import `reconciliation`, kiểm tra mount `./reconciliation:/opt/airflow/libs/reconciliation` và PYTHONPATH trong Compose. Nếu build đầy đủ lỗi vì raw đổi, dừng chạy CLI đồng thời với DAG rồi trigger lại ingestion.

Không chỉ nhìn DAG màu xanh: lưu thêm run ID, ingest ID, build ID và SQL kiểm tra mục 6. Import DAG đã được kiểm tra ở bản nháp, nhưng delivery của Asset và scheduler sau khi bạn triển khai vẫn cần bằng chứng thực tế.

## 9. Cập nhật Metabase đúng chỗ

Audit thấy Q4 đang lưu trong Metabase là question ID **41**, tên **Q4 Số ngày xanh liên tiếp**. ID có thể thay đổi sau restore, nên tìm theo tên trước. Sửa file SQL trong repo không tự sửa question đã lưu trong Metabase.

```bash
make metabase
```

Mở `http://localhost:3000`, vào dashboard đối soát, mở question Q4, sửa native SQL và Save:

```sql
SELECT green_days AS "Số ngày xanh liên tiếp"
FROM recon.v_green_streak;
```

Kiểm tra số Q4 đúng bằng kết quả SQL trong warehouse. Ngay sau nâng cấp có thể là 0 hoặc 1; đó là đúng vì lịch sử cũ chưa được chứng nhận bằng header mới. Q1/Q2/Q3 có thể giữ vai trò xem lịch sử; Q4 và quyết định cutover dùng view mới.

Thêm một bảng theo dõi run đầy đủ để phân biệt các lần chạy riêng từng báo cáo:

```sql
SELECT run_id, started_at, finished_at, status, eligible_for_cutover
FROM recon.runs
ORDER BY started_at DESC
LIMIT 30;
```

Chụp lại dashboard sau khi cập nhật, thay ảnh cũ ở `docs/images/recon-dashboard.png`. Ảnh phải phản ánh ngày và dữ liệu thật.

### Chuẩn bị báo cáo nghiệp vụ để diễn tập chuyển nguồn

Hai kết nối BI hiện được thấy đều là PostgreSQL. Dashboard đối soát là dashboard giám sát; nó chưa chứng minh đã chuyển một báo cáo nghiệp vụ từ SQL Server sang PostgreSQL.

Trong SQL Server tạo login chỉ đọc cho lab. Thay chuỗi mật khẩu mẫu trước khi chạy trong DBeaver hoặc `make sql`; không commit mật khẩu:

```sql
USE master;
GO
CREATE LOGIN bi_legacy_reader WITH PASSWORD = 'THAY_BANG_MAT_KHAU_MANH_RIENG';
GO
USE LegacyRetail;
GO
CREATE USER bi_legacy_reader FOR LOGIN bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.daily_revenue TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.customer_ltv TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.customer_segments TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.product_sales TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.cumulative_revenue TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.top_products_by_category TO bi_legacy_reader;
GRANT SELECT ON OBJECT::dbo.category_monthly_revenue TO bi_legacy_reader;
GO
```

Nếu login/user đã tồn tại, không chạy lại CREATE; giữ login hiện có và chạy GRANT. Bảng pivot bị DROP/CREATE mỗi lần batch, nên quyền cấp trên object pivot có thể bị mất: **source hiện tại tự khôi phục GRANT pivot sau mỗi lần batch tạo lại bảng**, hoặc để DBA thiết kế schema/role reporting riêng cho vận hành lâu dài. Không cấp quyền ghi để chữa lỗi đọc.

Trong Metabase thêm database SQL Server: host `sqlserver`, port `1433`, database `LegacyRetail`, user trên. Kết nối PostgreSQL: host `postgres`, port `5432`, database theo `.env` (hiện là `warehouse`), user `bi_reader`; cho phép đọc schema `marts` và `recon`. Hostname dùng tên service vì Metabase chạy trong Docker, không dùng `localhost` để trỏ sang container khác.

Tạo hai bộ question OLD/NEW và hai dashboard nghiệp vụ, dùng bảng tương ứng:

| Tên báo cáo | OLD trên SQL Server | NEW trên PostgreSQL |
|---|---|---|
| Daily revenue | `SELECT * FROM dbo.daily_revenue ORDER BY revenue_date` | `SELECT * FROM marts.mart_daily_revenue ORDER BY revenue_date` |
| Customer LTV | `SELECT * FROM dbo.customer_ltv ORDER BY customer_id` | `SELECT * FROM marts.mart_customer_ltv ORDER BY customer_id` |
| Customer segments | `SELECT * FROM dbo.customer_segments ORDER BY customer_id` | `SELECT * FROM marts.mart_customer_segments ORDER BY customer_id` |
| Product sales | `SELECT * FROM dbo.product_sales ORDER BY product_id` | `SELECT * FROM marts.mart_product_sales ORDER BY product_id` |
| Cumulative revenue | `SELECT * FROM dbo.cumulative_revenue ORDER BY revenue_date` | `SELECT * FROM marts.mart_cumulative_revenue ORDER BY revenue_date` |
| Top products | `SELECT * FROM dbo.top_products_by_category ORDER BY category, rank_in_category` | `SELECT * FROM marts.mart_top_products_by_category ORDER BY category, rank_in_category` |
| Category/month | `SELECT * FROM dbo.category_monthly_revenue ORDER BY category` | `SELECT * FROM marts.mart_category_monthly_revenue ORDER BY category` |

Lưu URL dashboard OLD và NEW, database ID và question ID vào bảng bằng chứng cutover. Chuyển dashboard/link người dùng sang bộ NEW là thao tác chuyển có thể quay lại rõ ràng; không cần sửa câu hỏi cũ để mất cấu hình rollback.

## 10. Phục hồi snapshot và phân biệt với tải lại nguồn

Lấy manifest mới nhất:

```bash
migration_manifest=$(docker compose exec -T postgres bash -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT manifest_key FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"')
printf '%s\n' "$migration_manifest"
make restore-raw MANIFEST="$migration_manifest" RESTORE_DB=restore_rehearsal_20261014
make restore-raw MANIFEST="$migration_manifest" RESTORE_DB=restore_rehearsal_20261014
```

Cả hai lần phải in `RESTORE PASS`. Lần 2 dùng cùng snapshot nên không nhân đôi. Với snapshot khác, chọn tên database `restore_...` mới. Script từ chối ghi đè database đang dùng hoặc database chứa dữ liệu khác.

Lưu manifest key và kết quả vào nhật ký. Đây là khôi phục dữ liệu raw tại một checkpoint đã lưu, bao gồm `_deleted_at`. Nó không khôi phục mã nguồn, metadata BI hoặc cấu hình Airflow; các phần đó thuộc backup riêng ở mục 4. Nó cũng không tự nối tiếp watermark của nguồn SQL Server đã restore/chuyển database.

Nếu nguồn hiện tại có dữ liệu khác, hạ watermark để đọc lại sẽ lấy **trạng thái nguồn hiện tại**, không phải ảnh chụp quá khứ. Không quảng bá cách đó là time travel. Khi raw hỏng, ưu tiên restore sang database riêng, kiểm tra, rồi lập kế hoạch chuyển có kiểm soát; không truncate warehouse đang dùng để thử nghiệm.

## 11. Chạy song song đủ 5 ngày thật

Giữ máy/Docker chạy và lịch DAG hoạt động. Mỗi ngày phải có ít nhất một full run hoàn chỉnh; lần full run gần nhất trong ngày quyết định trạng thái ngày đó. Partial/debug không tạo thêm ngày. Ngày hôm nay hoặc hôm qua là mốc kết thúc hợp lệ, tránh biến một chuỗi cũ thành trạng thái sẵn sàng hiện tại.

```bash
make readiness
```

Nếu bắt đầu ngày 14/10 và ngày nào cũng thành công, các ngày 14–18/10 là 5 ngày lịch. Chạy năm lần trong ngày 14 vẫn chỉ là **một ngày**. Không chỉnh `checked_at`, `started_at`, `finished_at` để tạo bằng chứng.

Sau mỗi ngày, lưu nội dung này vào `docs/evidence/parallel-run.md` (bạn điền kết quả thật):

| Ngày VN | Ingest run ID | Build ID | Recon run ID | 7/7 PASS | Diff | Green | Link log/ảnh |
|---|---|---|---|---|---:|---|---|
| YYYY-MM-DD | ... | ... | ... | ... | ... | ... | ... |

Giữ `CUTOVER_GREEN_DAYS=5` khi nghiệm thu. Nếu thử `--days 1` để học cách hoạt động, ghi rõ thử nghiệm; không dùng ảnh đó làm bằng chứng đạt yêu cầu 5 ngày.

## 12. CI, Git và Terraform

Working tree hiện có nhiều file chưa commit. Trước khi push, giữ cả các phần bạn đã làm từ trước: `.github`, `ci`, `terraform`, docs mới và readiness. Không tự cherry-pick nhánh khác chỉ vì tên nhánh có “terraform/ci”; có thể trùng hoặc làm mất bản đang sửa.

Tạo nhánh từ working tree hiện tại nếu muốn gom đợt hoàn thiện:

```bash
git switch -c codex/hoan-thien-du-an
```

Tên đã tồn tại thì chọn tên mới, không force thay nhánh. Commit theo nhóm rõ ràng: ingestion/replay; build/reconciliation; tests/CI; docs/Terraform. Trước mỗi commit dùng `git diff`, `git diff --cached` và `git status`. Với nhiều file mới, có thể stage nhóm thư mục cụ thể:

```bash
git add .github ci scripts reconciliation tests warehouse airflow/dags dbt_project sql
git add Makefile .gitignore .env.example README.md docs terraform
git diff --cached --stat
git diff --cached --check
```

Kiểm tra nội dung staged trước commit; `.env`, backups, logs, artifacts, `.terraform/`, tfstate không được nằm trong commit. `.terraform.lock.hcl` phải có. Không thêm `git add -f` để vượt ignore.

Push nhánh, mở pull request trên GitHub và chờ đủ ba job:

- **Python - ruff + unit test**.
- **dbt build trên dữ liệu mẫu + SQLFluff**.
- **Terraform - fmt + validate + plan giả lập**.

Trong Settings → Rules/Branches của repository, cấu hình nhánh `main` yêu cầu pull request và cả ba status checks trước merge; yêu cầu quyền quản trị repo để đổi cài đặt này. Lưu ảnh rule và URL PR xanh. Chứng minh chặn merge bằng một PR thử sửa sai expected value, thấy CI đỏ và merge bị chặn, rồi revert thay đổi thử đó trước khi merge. CI local xanh không chứng minh rule GitHub đã bật.

Terraform:

```bash
make tf-validate
make tf-plan
TF_VAR_aws_region=us-east-1 make tf-plan
```

Lệnh cuối là phương án cùng region với bảng chi phí US East; default Terraform vẫn Singapore. Chỉ plan, không apply. Với state rỗng, cấu hình hiện tại dự kiến 13 tài nguyên thêm mới. Plan mẫu chưa gồm MWAA/VPC hoàn chỉnh và không chứng minh đã triển khai cloud.

## 13. Hoàn thiện bảng chi phí

Bản vá thay nguồn giá license SQL Server sang tài liệu Microsoft và ghi rõ giới hạn dự toán. Hoàn thiện `docs/cost_estimate.md` theo đúng hai lựa chọn:

- Giữ số minh họa **us-east-1**, chạy plan tham chiếu cùng region và ghi rõ đây là kịch bản US East.
- Hoặc dùng **ap-southeast-1** cho cả thiết kế và estimate: nhập các giả định vào AWS Pricing Calculator, lưu bản xuất hoặc link estimate có region, ngày tra và từng hạng mục. Không đổi nhãn region mà giữ giá US East.

Đơn vị/công thức cần có: GB-tháng lưu trữ; PUT/GET requests; RPU × giờ thực chạy; Airflow/MWAA môi trường chạy liên tục; metadata; network/NAT; secret; log; backup; BI hosting; công vận hành. Lab SQL Server Developer không phát sinh license production; giá Standard chỉ là kịch bản doanh nghiệp giả định.

Không kết luận “cloud rẻ hơn” chỉ từ số giờ vận hành giả định. Đo thời gian pipeline thật trước; ghi rõ số truy vấn/ngày, thời gian giữ snapshot và retention. Full snapshot mỗi batch tăng dung lượng; cần phản ánh điều đó vào giả định lưu trữ.

Nguồn chính thức để kiểm tra giá:

- [Amazon Redshift pricing](https://aws.amazon.com/redshift/pricing/).
- [Amazon MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/).
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/).
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/).
- [Microsoft SQL Server pricing datasheet](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/bade/documents/products-and-services/en-us/security/644401-sql-server-2025-pricing.pdf).
- [AWS Pricing Calculator](https://calculator.aws/).

## 14. Diễn tập cutover và rollback

### Chuẩn bị

Ghi vai trò của bạn trong lab là data engineer/DBA/người dùng thử. Nếu có người phối hợp, điền tên và kênh liên lạc thực tế; không coi mẫu email trong runbook là thư đã gửi.

Điều kiện Go: CI PR xanh, đúng rule chặn merge, restore snapshot thành công, đủ 5 ngày readiness, lần full pipeline cuối PASS, OLD/NEW dashboard đều truy cập được. Nếu chưa đủ 5 ngày có thể diễn tập thao tác trên lab, nhưng ghi **diễn tập trước khi đủ điều kiện**, không ghi đã cutover được phê duyệt.

### Thực hiện

1. Ghi thời gian bắt đầu, URL OLD và NEW, phiên bản code (`git rev-parse HEAD`), người thực hiện.
2. Pause `simulate_source_activity`; ngừng các lệnh simulate khác, chờ run đang chạy xong.
3. Chạy chuỗi cuối `ingest_legacy → legacy_nightly_batch + transform_dbt → reconciliation`.
4. Kiểm tra SQL mục 6 và `make readiness`. Bất kỳ SKIP/WARN/FAIL hoặc snapshot không khớp: dừng chuyển.
5. Sau batch cuối, cấp lại quyền đọc object pivot nếu cần. Mở OLD và NEW, kiểm tra cùng kỳ và cùng run; không so NEW với số hôm qua.
6. Chuyển link/dashboard chính người dùng mở từ OLD sang NEW. Ghi URL trước/sau; giữ nguyên dashboard OLD để quay lại.
7. Kiểm tra 7 báo cáo: đặc biệt daily revenue, customer segments, top products và pivot. Chụp ảnh cả hai phía.
8. Ghi thời gian hoàn tất, thời gian gián đoạn và kết quả. Bật lại simulate/lịch theo dõi sau khi xác nhận.
9. Tiếp tục chạy nguồn cũ và đối soát trong thời gian quan sát đã chọn (runbook dùng 14 ngày). Chưa tắt procedure/job cũ khi chưa hết cửa sổ rollback.

### Diễn tập quay về

Trong lab, chủ động tuyên bố một tình huống thử, ví dụ “dashboard NEW không truy cập được”, không cần phá dữ liệu thật:

1. Ghi thời điểm quyết định rollback.
2. Chuyển link/dashboard chính về URL OLD đã lưu.
3. Xác nhận kết nối SQL Server và 7 bảng báo cáo cũ vẫn đọc được; kiểm tra kỳ dữ liệu cuối.
4. Ghi thời điểm người dùng truy cập lại được, tính RTO thực đo. Mục tiêu lab có thể đặt ≤10 phút; chưa đo thì chưa ghi đạt.
5. Tiếp tục duy trì nguồn và batch cũ; giữ log hệ mới để sửa lỗi. Sau sửa phải full build/đối soát lại trước khi đề xuất chuyển tiếp.

Rollback BI không đồng nghĩa restore warehouse. Không cần xóa raw/marts hoặc hạ watermark để quay dashboard về OLD. Backup database là phương án phục hồi riêng khi dữ liệu/cấu hình hỏng.

Mẫu `docs/evidence/cutover-rehearsal.md` để điền:

```markdown
# Diễn tập cutover/rollback
- Ngày giờ và múi giờ:
- Commit:
- Người thực hiện/vai trò:
- Trạng thái: diễn tập / đủ điều kiện Go / No-Go
- PR CI:
- Readiness (số ngày, since/until):
- Ingest run / legacy batch / dbt build / recon run:
- Manifest phục hồi và kết quả restore:
- OLD dashboard URL / database ID / question IDs:
- NEW dashboard URL / database ID / question IDs:
- Thời điểm chuyển NEW:
- Kết quả so 7 báo cáo cùng kỳ:
- Tình huống thử rollback:
- Thời điểm quyết định rollback:
- Thời điểm OLD phục vụ lại:
- RTO đo được:
- Ảnh/log minh chứng:
- Vấn đề còn tồn tại và cách xử lý:
```

### Hoàn tác riêng bản vá source nếu cần

Dừng Airflow, sao lưu các sửa đổi phát sinh sau khi áp dụng patch. Kiểm tra:

```bash
git apply -R --check /tmp/legacy-complete.patch
```

Chỉ nếu khớp và bạn muốn quay code về trước bản vá:

```bash
git apply -R /tmp/legacy-complete.patch
```

Lệnh này không hoàn tác migration database. Các bảng thêm có thể để lại để giữ bằng chứng; không DROP dữ liệu để “làm sạch”. Muốn khôi phục cấu hình/data chính xác về trước nâng cấp, phục hồi backup vào database mới và kiểm tra trước khi chuyển ứng dụng. Không dùng `git reset --hard` vì working tree ban đầu đã có nhiều sửa đổi của bạn.

## 15. README, chạy từ clone sạch và demo

### Chạy clone sạch

Sau khi PR hoàn tất, dùng máy/VM hoặc Docker host riêng để kiểm tra README. Compose đặt `container_name` cố định; chỉ đổi thư mục hoặc `docker compose -p` không đủ để chạy song song hai bộ cùng máy. Không dùng `make reset` trên bộ đang giữ bằng chứng.

Quy trình máy sạch:

```bash
git clone <URL_REPO_CUA_BAN> legacy-migration
cd legacy-migration
make env
# Sửa mật khẩu lab trong .env, không gửi file này lên GitHub.
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dbt.txt -r requirements-dev.txt
make up
make data
make wh
make minio
make ingest-all
make legacy-batch
make dbt-build
make recon
make airflow
make dag-check
make metabase
make dbt-docs
```

Ghi thời điểm bắt đầu/kết thúc, cấu hình RAM/CPU, mạng, lỗi và bước sửa. Tiêu chí 30 phút chỉ được ghi đạt khi có lần thực chạy; tách thời gian tải image/dependency để người đọc hiểu. Tạo Metabase theo mục 9 trên môi trường mới, không giả định metadata BI tự có từ repo.

### Cập nhật hồ sơ dự án

- README: trạng thái thực tế; ảnh dashboard mới; ảnh lineage; URL PR CI; link video.
- `docs/migration_notes.md`: giữ mapping cả 7 procedure; giải thích thay CURSOR/WHILE/temp tables/MERGE/PIVOT, trạng thái đơn hàng và ngày chốt segment cố định.
- 6 ADR: giữ đầy đủ; raw upsert, delete, snapshot, ngưỡng tiền, pivot, chọn dbt phải khớp code.
- `docs/reconciliation.md`: ghi quy tắc mới và phân biệt lịch sử trước/sau guard.
- `docs/lessons_learned.md`: thêm lỗi thật đã gặp trong quá trình áp dụng, không ghi giả kết quả.
- Thư mục evidence: bảng 5 ngày, run IDs, log CI, kết quả restore, diễn tập cutover/rollback.

### Kịch bản demo 4–5 phút

| Thời gian | Hiển thị | Nội dung nói |
|---|---|---|
| 0:00–0:35 | Sơ đồ kiến trúc | 7 báo cáo T-SQL được chuyển sang dbt; mục tiêu là giữ đúng số liệu |
| 0:35–1:15 | Một procedure khó và model tương ứng | CURSOR/WHILE được thay bằng xử lý tập hợp/window; pivot giữ NULL, ngày và danh sách tháng |
| 1:15–2:00 | Airflow + ingest log | Tải lần đầu/lượt sau, watermark an toàn, xử lý delete, batch ID |
| 2:00–2:45 | dbt lineage + run PASS | 12 model, 49 test; full build gắn ingestion |
| 2:45–3:30 | Dashboard + ca lỗi có ghi nhận | 7 báo cáo, L0–L5; SKIP khác PASS, debug không đủ điều kiện |
| 3:30–4:15 | Readiness + restore/cutover evidence | Đủ 5 ngày thật; chuyển NEW và rollback OLD; RTO đã đo |
| 4:15–4:45 | PR CI + Terraform plan + cost | CI chặn lỗi; chỉ plan hạ tầng; chi phí có giả định/region rõ |

Ẩn `.env`, password Airflow, token và email riêng trước khi quay. Chỉ nói các con số bạn có bằng chứng. Nếu chưa đủ 5 ngày, ghi rõ đó là phần đang tiếp tục, không dựng ảnh giả.

Mẫu giới thiệu sau khi đã nghiệm thu: “Tôi chuyển 7 stored procedure báo cáo SQL Server thành 12 model dbt với 49 test, xây ingestion rowversion và đối soát 5 cấp có kiểm tra batch. Tôi đã thử hard delete, replay snapshot, 5 ngày chạy song song và cutover/rollback trên lab.” Thay số liệu nếu code sau đó thay đổi.

## 16. Checklist kết thúc

- [ ] Source được backup, bản vá áp dụng không lỗi.
- [ ] Schema mới và procedure pivot được triển khai.
- [ ] Lần full pipeline hiện tại PASS, eligible=true.
- [ ] Unit/SQL tests, dbt, freshness, golden, SQLFluff và Terraform đều PASS.
- [ ] Integration lab PASS, đã thử restore hai lần.
- [ ] Airflow Asset chain chạy tự động thành công trên bản triển khai.
- [ ] Q4 trong Metabase dùng view mới, đúng số với warehouse.
- [ ] Có kết nối OLD SQL Server và NEW PostgreSQL, 7 question mỗi bên.
- [ ] Có 5 ngày lịch liên tiếp theo guard mới, không sửa timestamp.
- [ ] PR CI xanh và rule chặn merge được chứng minh.
- [ ] Chi phí cùng region, giả định và nguồn chính thức; ghi các khoản chưa tính.
- [ ] Cutover và rollback đã diễn tập, ghi URL/ID và thời gian thực đo.
- [ ] README/ADR/migration notes/cutover/evidence phản ánh đúng kết quả.
- [ ] Clone sạch chạy được theo README, ghi thời gian.
- [ ] Có video demo 3–5 phút và link trong README.

Thứ tự nên làm: **backup → áp dụng patch → migrate → manual full run → tests → Airflow → Metabase/OLD–NEW → CI → 5 ngày song song → diễn tập → clone sạch và video**. Có thể làm tài liệu/CI/chi phí trong lúc đợi đủ 5 ngày; không cần đợi xong ngày thứ 5 mới bắt đầu tất cả các phần đó.

## Phụ lục A. Danh sách file trong bản vá

- `.github/workflows/ci.yml`
- `.gitignore`
- `Makefile`
- `README.md`
- `airflow/dags/ingest_legacy.py`
- `airflow/dags/reconcile_legacy_vs_dbt.py`
- `airflow/dags/transform_dbt.py`
- `ci/assert_expected_marts.sql`
- `dbt_project/models/staging/_sources.yml`
- `dbt_project/tests/assert_no_abnormal_row_drop.sql`
- `docs/adr/0001-xu-ly-dong-bi-xoa.md`
- `docs/adr/0002-raw-dang-upsert.md`
- `docs/adr/0003-bao-cao-pivot-dong.md`
- `docs/adr/0004-nguong-sai-so-va-snapshot-doi-soat.md`
- `docs/adr/0005-bat-thay-doi-bang-rowversion.md`
- `docs/adr/0006-chon-dbt-cho-tang-bien-doi.md`
- `docs/cost_estimate.md`
- `docs/cutover_plan.md`
- `docs/migration_notes.md`
- `docs/reconciliation.md`
- `reconciliation/build.py`
- `reconciliation/db.py`
- `reconciliation/fingerprint.py`
- `reconciliation/ingest_batch.py`
- `reconciliation/legacy_batch.py`
- `reconciliation/lifecycle.py`
- `reconciliation/readiness.py`
- `reconciliation/run.py`
- `scripts/archive_raw.py`
- `scripts/ci_local.py`
- `scripts/ingest_incremental.py`
- `scripts/integration_lab.py`
- `scripts/schema_contract.py`
- `sql/02_stored_procedures.sql`
- `terraform/.terraform.lock.hcl`
- `tests/test_operational_guards.py`
- `tests/test_warehouse_guards.py`
- `warehouse/init.sql`
- `warehouse/raw_restore.sql`

## Phụ lục B. Toàn bộ mã thêm/sửa

Đây là unified diff hoàn chỉnh. Dòng `+` là nội dung thêm; dòng `-` là nội dung bỏ. Dùng mục 5 để trích và áp dụng tự động.

<!-- BEGIN_PROJECT_PATCH -->
~~~~diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 92a9412..a08fd43 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -53,11 +53,11 @@ jobs:
         env:
           POSTGRES_USER: warehouse
           POSTGRES_PASSWORD: warehouse_ci
-          POSTGRES_DB: warehouse
+          POSTGRES_DB: test_ci
         ports:
           - 5432:5432
         options: >-
-          --health-cmd "pg_isready -U warehouse -d warehouse"
+          --health-cmd "pg_isready -U warehouse -d test_ci"
           --health-interval 5s
           --health-timeout 5s
           --health-retries 10
@@ -66,12 +66,13 @@ jobs:
       POSTGRES_PORT: "5432"
       POSTGRES_USER: warehouse
       POSTGRES_PASSWORD: warehouse_ci
-      POSTGRES_DB: warehouse
+      POSTGRES_DB: test_ci
+      MIGRATION_TEST_DB: test_ci
       PGHOST: localhost
       PGPORT: "5432"
       PGUSER: warehouse
       PGPASSWORD: warehouse_ci
-      PGDATABASE: warehouse
+      PGDATABASE: test_ci
       DBT_PROFILES_DIR: ${{ github.workspace }}/dbt_project
       DBT_SEND_ANONYMOUS_USAGE_STATS: "false"
     steps:
@@ -86,7 +87,7 @@ jobs:
             requirements-dev.txt
 
       - name: Cài dbt + SQLFluff
-        run: pip install -r requirements-dbt.txt -r requirements-dev.txt
+        run: pip install -r requirements.txt -r requirements-dbt.txt -r requirements-dev.txt
 
       - name: Khởi tạo warehouse (schema raw, etl, recon, view)
         run: psql -v ON_ERROR_STOP=1 -f warehouse/init.sql
@@ -94,6 +95,9 @@ jobs:
       - name: Nạp dữ liệu mẫu vào raw
         run: psql -v ON_ERROR_STOP=1 -f ci/sample_raw_data.sql
 
+      - name: Unit và SQL integration tests
+        run: python -m unittest discover -s tests -v
+
       - name: dbt compile
         working-directory: dbt_project
         run: dbt compile
diff --git a/.gitignore b/.gitignore
index 2f5130f..21d662c 100644
--- a/.gitignore
+++ b/.gitignore
@@ -10,4 +10,7 @@ terraform/.terraform/
 *.tfstate
 *.tfstate.*
 tfplan
-airflow/logs/
\ No newline at end of file
+airflow/logs/
+logs/
+backups/
+artifacts/
diff --git a/Makefile b/Makefile
index 4803320..ceeab0b 100644
--- a/Makefile
+++ b/Makefile
@@ -1,5 +1,6 @@
 -include .env
 export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT
+PYTHON = .venv/bin/python
 
 COMPOSE = docker compose
 SQLCMD  = /opt/mssql-tools18/bin/sqlcmd
@@ -85,7 +86,7 @@ reset:
 	$(COMPOSE) down -v
 
 data:
-	python scripts/generate_data.py
+	$(PYTHON) scripts/generate_data.py
 
 batch:
 	$(COMPOSE) exec -T sqlserver bash -c '$(SQLCMD) -C -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -d LegacyRetail -b -Q "EXEC dbo.sp_run_nightly_batch"'
@@ -102,26 +103,26 @@ wh-sql:
 
 minio:
 	$(COMPOSE) up -d minio
-	python scripts/init_minio.py
+	$(PYTHON) scripts/init_minio.py
 
 extract-full:
-	python scripts/extract_full.py
+	$(PYTHON) scripts/extract_full.py
 
 load-customers:
-	python scripts/load_to_postgres.py
+	$(PYTHON) scripts/load_to_postgres.py
 
 TABLE ?= customers
 
 ingest:
-	python scripts/ingest_incremental.py $(TABLE)
+	PYTHONPATH=scripts:. $(PYTHON) scripts/ingest_incremental.py $(TABLE)
 
 ARGS ?=
 
 simulate:
-	python scripts/simulate_changes.py $(ARGS)
+	$(PYTHON) scripts/simulate_changes.py $(ARGS)
 
 ingest-all:
-	python scripts/ingest_incremental.py all
+	PYTHONPATH=scripts:. $(PYTHON) scripts/ingest_incremental.py all
 
 airflow:
 	$(COMPOSE) up -d --build airflow
@@ -147,14 +148,14 @@ dbt-debug:
 	$(DBT_LOCAL) debug --profiles-dir .
 
 dbt-build:
-	$(DBT_LOCAL) build --profiles-dir . $(if $(SELECT),-s $(SELECT),)
+	PYTHONPATH=scripts:. $(PYTHON) -m reconciliation.build $(if $(SELECT),--select "$(SELECT)",)
 
 dbt-docs:
 	$(DBT_LOCAL) docs generate --profiles-dir .
 	$(DBT_LOCAL) docs serve --profiles-dir . --port 8081
 
 dbt-airflow:
-	$(DBT_IN_AIRFLOW) build
+	$(COMPOSE) exec -e DBT_BIN=/home/airflow/dbt-venv/bin/dbt -e DBT_PROJECT_DIR=/opt/airflow/dbt_project airflow python -m reconciliation.build
 
 test:
 	.venv/bin/python -m unittest discover -s tests -v
@@ -182,7 +183,9 @@ lint:                    ## lint Python + SQL (SQLFluff cần Postgres đang ch
 	.venv/bin/ruff format --check .
 	.venv/bin/sqlfluff lint dbt_project/models dbt_project/tests
 
-ci-local: lint test dbt-build tf-validate   ## giống CI trên GitHub, nhưng dùng dữ liệu thật trong warehouse local
+ci-local:   ## database test cô lập + cùng các kiểm tra như CI
+	PYTHONPATH=scripts:. $(PYTHON) scripts/ci_local.py
+	$(MAKE) tf-validate tf-plan
 	@echo "ci-local: tất cả các bước đều xanh"
 
 readiness:               ## exit 0 khi đủ điều kiện cutover (docs/cutover_plan.md)
@@ -204,3 +207,13 @@ tf-validate: tf-init
 
 tf-plan: tf-init
 	$(TF) plan -input=false -lock=false
+
+.PHONY: restore-raw integration-test
+
+integration-test:
+	PYTHONPATH=scripts:. $(PYTHON) scripts/integration_lab.py
+
+# MANIFEST=manifests/<sha256>.json RESTORE_DB=restore_lab
+restore-raw:
+	@test -n "$(MANIFEST)" && test -n "$(RESTORE_DB)"
+	PYTHONPATH=scripts:. $(PYTHON) scripts/archive_raw.py "$(MANIFEST)" --database "$(RESTORE_DB)"
diff --git a/README.md b/README.md
index 02b621e..43a356b 100644
--- a/README.md
+++ b/README.md
@@ -85,8 +85,9 @@ Không muốn dùng Airflow thì chạy tay theo đúng thứ tự:
 make ingest-all && make legacy-batch && make dbt-build && make recon
 ```
 
-`make ingest-all` không chạy bước phát hiện dòng bị xóa; nếu nguồn đã có xóa
-cứng, hãy dùng DAG `ingest_legacy`.
+`make ingest-all` chạy cả phát hiện xóa và lưu snapshot Parquet đầy đủ.
+`make dbt-build` ghi lại batch đầu vào và kết quả build. Build một phần qua
+`SELECT=...` trả mã 2 và không dùng để nghiệm thu; sau khi debug phải build lại toàn bộ.
 
 **3. Dashboard và tài liệu dbt**
 
@@ -106,15 +107,16 @@ make dbt-docs    # http://localhost:8081, xem lineage
 | `make test` | Unit test cho logic đối soát, guard phát hiện xóa, điều kiện cutover |
 | `make lint` | Ruff + SQLFluff (cần `make wh` đang chạy) |
 | `make dbt-build` | Build và test toàn bộ model trên dữ liệu thật |
-| `make ci-local` | Chạy lại các bước CI trên máy: lint, test, dbt build, Terraform validate |
+| `make ci-local` | Tạo database test riêng, chạy lint/test/dbt/golden, tự xóa database test; Terraform validate/plan |
 | `make readiness` | In 10 ngày đối soát gần nhất; exit 0 khi đủ 5 ngày xanh liên tiếp |
 | `make tf-plan` | Terraform plan hạ tầng AWS bằng khóa giả, không cần tài khoản |
 
 GitHub Actions ([ci.yml](./.github/workflows/ci.yml)) chạy ở mỗi pull request:
 Postgres trống, nạp [dữ liệu mẫu](./ci/sample_raw_data.sql) có sẵn các trường hợp
 biên, `dbt build`, rồi so con số mart với
-[kết quả kỳ vọng](./ci/assert_expected_marts.sql). Nhánh `main` được bảo vệ:
-không merge được khi CI đỏ.
+[kết quả kỳ vọng](./ci/assert_expected_marts.sql). Cần bật ruleset/branch protection
+và yêu cầu đủ ba status checks trên GitHub; YAML CI tự nó không chặn merge.
+Chỉ ghi nhận CI/branch protection hoàn tất khi có URL PR xanh và bằng chứng cấu hình.
 
 Xem toàn bộ lệnh bằng `make help`.
 
@@ -152,15 +154,27 @@ legacy-migration/
 └── .github/workflows/    # CI
 ```
 
+## Kiểm thử tích hợp và phục hồi
+
+```bash
+PYTHONPATH=scripts:. .venv/bin/python scripts/integration_lab.py
+make restore-raw MANIFEST=manifests/<sha256>.json RESTORE_DB=restore_lab
+```
+
+Bài test tạo database và bucket tạm riêng, kiểm tra tải lặp, xóa cứng, đối soát,
+khôi phục hai lần và build một phần; tự dọn tài nguyên test. Lệnh restore chỉ nhận
+database `restore_*`, từ chối ghi đè database đang dùng. Nó khôi phục raw và
+tombstone, không thay watermark của pipeline đang chạy.
+
 ## Tiến độ
 
 | Tuần | Nội dung | Trạng thái |
 |---|---|---|
 | 1 | Hệ thống nguồn SQL Server và 7 stored procedure | Hoàn thành |
-| 2 | Ingestion tăng dần qua Airflow, Parquet/MinIO, raw PostgreSQL | Hoàn thành |
+| 2 | Ingestion, replay snapshot có tombstone | Có mã và bài test cô lập; cần lưu bằng chứng trên bản triển khai |
 | 3–4 | Chuyển 7 procedure sang dbt, test, lineage | Hoàn thành |
-| 5 | Đối soát 5 cấp, DAG tự động, dashboard Metabase | Hoàn thành |
-| 6 | CI, Terraform, chi phí, cutover/rollback, tài liệu | Hoàn thành |
+| 5 | Đối soát 5 cấp, DAG, dashboard | Cần triển khai guard mới và cập nhật Q4 trên Metabase |
+| 6 | CI, Terraform, chi phí, cutover/rollback, tài liệu | Chưa nghiệm thu: cần PR CI xanh và diễn tập cutover/rollback |
 | 6 | Video demo | Đã có kịch bản, chưa quay |
 | — | Chạy song song tới khi đủ 5 ngày xanh | Đang đếm (`make readiness`) |
 
diff --git a/airflow/dags/ingest_legacy.py b/airflow/dags/ingest_legacy.py
index 27922ff..8aa2560 100644
--- a/airflow/dags/ingest_legacy.py
+++ b/airflow/dags/ingest_legacy.py
@@ -79,6 +79,12 @@ def ingest_legacy():
 
     @task(outlets=[WAREHOUSE_RAW])
     def summarize(results: list[dict[str, Any]], deletion_results: list[dict[str, Any]]) -> None:
+        from airflow.sdk import get_current_context
+
+        from reconciliation.ingest_batch import complete_ingestion
+
+        manifest = complete_ingestion(get_current_context()["run_id"])
+        LOGGER.info("Completed batch manifest: %s", manifest)
         row_counts = {str(result["table"]): int(result["rows"]) for result in results}
         total_rows = sum(row_counts.values())
         deleted_counts = {str(result["table"]): int(result["deleted"]) for result in deletion_results}
diff --git a/airflow/dags/reconcile_legacy_vs_dbt.py b/airflow/dags/reconcile_legacy_vs_dbt.py
index e88c5fd..8518cc8 100644
--- a/airflow/dags/reconcile_legacy_vs_dbt.py
+++ b/airflow/dags/reconcile_legacy_vs_dbt.py
@@ -41,9 +41,13 @@ REPORTS = [
 def reconciliation():
     @task
     def check_snapshot() -> dict:
+        from airflow.sdk import get_current_context
+
+        from reconciliation.lifecycle import begin_run
         from reconciliation.run import check_snapshot as _check
 
         snapshot = _check()
+        begin_run(get_current_context()["run_id"], REPORTS, snapshot)
         LOGGER.info("Snapshot: %s", snapshot)
         return snapshot
 
@@ -59,17 +63,15 @@ def reconciliation():
 
     @task
     def evaluate(results: list[dict]) -> None:
-        by_status: dict[str, list[str]] = {}
-        for r in results:
-            by_status.setdefault(r["status"], []).append(r["report"])
-        LOGGER.info("Tổng hợp đối soát: %s", by_status)
-        if "FAIL" in by_status:
-            # Không retry: lệch số liệu không tự hết khi chạy lại -> gửi cảnh báo ngay
-            raise AirflowFailException(
-                f"Đối soát FAIL: {', '.join(by_status['FAIL'])}. Xem recon.results / recon.row_diffs theo run_id này."
-            )
-        if set(by_status) == {"SKIP"}:
-            LOGGER.warning("Toàn bộ báo cáo SKIP vì snapshot lệch: hôm nay chưa được kiểm chứng")
+        from airflow.sdk import get_current_context
+
+        from reconciliation.lifecycle import finish_run
+        from reconciliation.run import check_snapshot as verify_snapshot
+
+        outcome = finish_run(get_current_context()["run_id"], verify_snapshot())
+        LOGGER.info("Reports: %s; run outcome: %s", results, outcome)
+        if not outcome["eligible_for_cutover"]:
+            raise AirflowFailException(f"Run chưa đủ điều kiện nghiệm thu: {outcome['status']}")
 
     snapshot = check_snapshot()
     results = reconcile.partial(snapshot=snapshot).expand(report=REPORTS)
diff --git a/airflow/dags/transform_dbt.py b/airflow/dags/transform_dbt.py
index c193fe3..5a99c75 100644
--- a/airflow/dags/transform_dbt.py
+++ b/airflow/dags/transform_dbt.py
@@ -34,20 +34,13 @@ DBT_PATH_ARGS = "--target-path /tmp/dbt_target --log-path /tmp/dbt_logs"
     tags=["legacy", "dbt"],
 )
 def transform_dbt():
-    freshness = BashOperator(
-        task_id="dbt_source_freshness",
-        bash_command=(f"cd {DBT_DIR} && {DBT} source freshness --profiles-dir {DBT_DIR} {DBT_PATH_ARGS}"),
-        env=DBT_ENV,
-        append_env=True,
-    )
-    build = BashOperator(
+    BashOperator(
         task_id="dbt_build",
-        bash_command=f"cd {DBT_DIR} && {DBT} build --profiles-dir {DBT_DIR} {DBT_PATH_ARGS}",
-        env=DBT_ENV,
+        bash_command="python -m reconciliation.build",
+        env={**DBT_ENV, "DBT_BIN": DBT, "DBT_PROJECT_DIR": DBT_DIR},
         append_env=True,
-        outlets=[WAREHOUSE_MARTS],  # chỉ phát khi dbt build xanh -> kích hoạt đối soát
+        outlets=[WAREHOUSE_MARTS],
     )
-    freshness >> build
 
 
 transform_dbt()
diff --git a/ci/assert_expected_marts.sql b/ci/assert_expected_marts.sql
index eecaaa9..fb3c8d9 100644
--- a/ci/assert_expected_marts.sql
+++ b/ci/assert_expected_marts.sql
@@ -78,9 +78,26 @@ BEGIN
         failures := failures || format(E'\n  - %s: kỳ vọng %s, thực tế %s', 'mart_category_monthly_revenue: cột tháng', '2026-07,2026-08,2026-09', actual);
     END IF;
 
+    -- Compare all 9 pivot cells, including NULL versus zero; names alone are insufficient.
+    IF EXISTS (
+        WITH expected(category, jul, aug, sep) AS (
+            VALUES ('Điện tử', 7500000.00::numeric, 84400000.00::numeric, 316300000.00::numeric),
+                   ('Gia dụng', 650000.00::numeric, 3100000.00::numeric, NULL::numeric),
+                   ('Thực phẩm', NULL::numeric, 450000.00::numeric, NULL::numeric)
+        ), actual_pivot AS (
+            SELECT category, "2026-07", "2026-08", "2026-09"
+            FROM marts.mart_category_monthly_revenue
+        )
+        (SELECT * FROM expected EXCEPT ALL SELECT * FROM actual_pivot)
+        UNION ALL
+        (SELECT * FROM actual_pivot EXCEPT ALL SELECT * FROM expected)
+    ) THEN
+        failures := failures || E'\n  - mart_category_monthly_revenue: sai ô pivot/NULL';
+    END IF;
+
     IF failures <> '' THEN
         RAISE EXCEPTION 'Mart lệch so với kết quả kỳ vọng:%', failures;
     END IF;
-    RAISE NOTICE 'Toàn bộ % kiểm tra golden đều khớp', 14;
+    RAISE NOTICE 'Toàn bộ % kiểm tra golden đều khớp', 15;
 END
 $$;
diff --git a/dbt_project/models/staging/_sources.yml b/dbt_project/models/staging/_sources.yml
index 1664d5f..69a4237 100644
--- a/dbt_project/models/staging/_sources.yml
+++ b/dbt_project/models/staging/_sources.yml
@@ -13,9 +13,23 @@ sources:
   - name: etl
     schema: etl
     tables:
-      - name: ingest_log
-        description: "Mỗi lần chạy ingestion ghi một dòng cho mỗi bảng, kể cả khi 0 dòng"
+      - name: freshness_customers
         loaded_at_field: loaded_at
         freshness:
           warn_after: {count: 26, period: hour}
-          error_after: {count: 50, period: hour}
\ No newline at end of file
+          error_after: {count: 50, period: hour}
+      - name: freshness_products
+        loaded_at_field: loaded_at
+        freshness:
+          warn_after: {count: 26, period: hour}
+          error_after: {count: 50, period: hour}
+      - name: freshness_orders
+        loaded_at_field: loaded_at
+        freshness:
+          warn_after: {count: 26, period: hour}
+          error_after: {count: 50, period: hour}
+      - name: freshness_order_items
+        loaded_at_field: loaded_at
+        freshness:
+          warn_after: {count: 26, period: hour}
+          error_after: {count: 50, period: hour}
diff --git a/dbt_project/tests/assert_no_abnormal_row_drop.sql b/dbt_project/tests/assert_no_abnormal_row_drop.sql
index 1bb0e09..5e48842 100644
--- a/dbt_project/tests/assert_no_abnormal_row_drop.sql
+++ b/dbt_project/tests/assert_no_abnormal_row_drop.sql
@@ -3,11 +3,11 @@
 {{ config(severity = 'error') }}
 
 with previous as (
-    select
+    select distinct on (rc.model_name)
         rc.model_name,
         rc.row_count
     from audit.row_counts as rc
-    where rc.run_at = (select max(latest.run_at) from audit.row_counts as latest)
+    order by rc.model_name asc, rc.run_at desc
 ),
 
 current_counts as (
diff --git a/docs/adr/0001-xu-ly-dong-bi-xoa.md b/docs/adr/0001-xu-ly-dong-bi-xoa.md
new file mode 100644
index 0000000..d98e9b3
--- /dev/null
+++ b/docs/adr/0001-xu-ly-dong-bi-xoa.md
@@ -0,0 +1,51 @@
+# ADR-0001: Xử lý dòng bị xóa ở nguồn
+
+- Trạng thái: Đã chấp nhận
+- Ngày: 2026-10-09
+
+## Bối cảnh
+
+SQL Server `rowversion` thay đổi khi dòng được INSERT hoặc UPDATE. Khi dòng bị
+DELETE, nó biến mất khỏi nguồn và không có `rowversion` mới để luồng incremental
+phát hiện. Vì vậy bản ghi tương ứng vẫn nằm trong raw và có thể bị tính thừa ở
+các báo cáo. Ví dụ: `order_items` bị xóa khi khách bỏ bớt món hàng.
+
+## Các phương án
+
+| Phương án | Ưu | Nhược |
+|---|---|---|
+| Soft delete ở nguồn (`is_deleted`) | Đơn giản nhất cho phía tải | Cần sửa ứng dụng cũ, thường không được phép trong dự án di chuyển |
+| So sánh tập khóa hằng đêm | Không sửa nguồn; dễ hiểu và dễ kiểm thử | Quét toàn bộ khóa mỗi lần chạy; phát hiện xóa trễ tối đa một chu kỳ chạy |
+| Change Tracking | SQL Server ghi nhận khóa của dòng bị xóa với chi phí thấp | Cần DBA bật trên database; có thời hạn lưu, quá hạn phải đồng bộ lại |
+| CDC | Có cả giá trị trước/sau khi thay đổi | Cần SQL Server Agent, tốn tài nguyên và phức tạp hơn |
+
+## Quyết định
+
+Chọn so sánh tập khóa. Đây là phương án không yêu cầu thay đổi hệ thống nguồn,
+đồng thời phù hợp với dữ liệu hiện tại ở quy mô vài chục nghìn dòng mỗi bảng.
+Sau mỗi lần nạp incremental, task `detect_deletes` đọc tập khóa chính hiện có ở
+nguồn, so với raw và đánh dấu các dòng không còn trong nguồn bằng `_deleted_at`.
+Raw không xóa vật lý các dòng này để giữ dấu vết phục vụ kiểm tra.
+
+Chuyển sang Change Tracking khi một bảng vượt khoảng 1.000.000 khóa hoặc việc
+quét khóa toàn bảng mất trên 5 phút trong cửa sổ nạp đêm, sau khi DBA duyệt cấu
+hình retention và có quy trình phát hiện watermark đã quá hạn.
+
+## Hệ quả
+
+- Bốn bảng raw có cột `_deleted_at TIMESTAMPTZ`; schema được nâng cấp an toàn
+  bằng `ADD COLUMN IF NOT EXISTS`.
+- Dòng bị xóa vẫn được giữ trong raw. Các mô hình staging tuần 3 trở đi phải lọc
+  `WHERE _deleted_at IS NULL` khi biểu diễn trạng thái hiện hành.
+- Phát hiện xóa chạy sau khi nạp mỗi bảng. Việc đánh dấu không thay đổi
+  `rowversion` watermark; mỗi lần quét chỉ đánh dấu những dòng chưa có
+  `_deleted_at`.
+- `rowversion` không ghi nhận DELETE; độ trễ phát hiện tối đa là một chu kỳ chạy.
+- Tập khóa được truyền theo lô vào bảng tạm Postgres, không cần giữ toàn bộ khóa
+  của bảng trong bộ nhớ Python.
+- Trước khi đánh dấu, detector chặn nếu tỷ lệ dòng raw đang hoạt động dự kiến bị
+  đánh dấu xóa vượt `MAX_DELETE_RATIO` (mặc định `0.05`). Chỉ tăng ngưỡng có chủ
+  ý sau khi xác minh nguồn nếu một đợt xóa hợp lệ lớn hơn ngưỡng.
+
+- Cả CLI `make ingest-all` và DAG đều phát hiện xóa. Snapshot manifest lưu cả
+  tombstone để replay không làm sống lại dòng đã xóa.
diff --git a/docs/adr/0002-raw-dang-upsert.md b/docs/adr/0002-raw-dang-upsert.md
new file mode 100644
index 0000000..979a10f
--- /dev/null
+++ b/docs/adr/0002-raw-dang-upsert.md
@@ -0,0 +1,36 @@
+# ADR-0002: Raw upsert và snapshot bất biến để phục hồi
+
+- Trạng thái: Đã chấp nhận cho lab
+- Cập nhật: 2026-10-14
+
+## Quyết định
+
+Raw giữ trạng thái hiện tại bằng upsert theo khóa và rowversion; staging lọc
+`_deleted_at IS NULL`. Đây là khác biệt có chủ đích so với đề xuất raw append
+trong hướng dẫn gốc. Không cần viết lại 12 model chỉ để đổi cách lưu raw.
+
+Incremental dùng key `raw/<bảng>/incremental/rv_<from>_<to>_<sha256>.parquet`.
+Ghi object với `IfNoneMatch="*"`; retry chỉ chấp nhận object có nội dung giống
+hệt. Cùng khoảng watermark nhưng bytes khác phải thành key khác, không ghi đè.
+
+Sau khi đủ bốn bảng và source/raw khớp, lưu snapshot đầy đủ của raw, bao gồm
+`_loaded_at`, `_deleted_at`, theo key nội dung và một manifest có SHA-256.
+`etl.ingest_batches.manifest_key` trỏ tới manifest. Snapshot đã phát hành không
+bị thay đổi bởi code này; tài khoản quản trị vẫn có quyền xóa object. Production
+cần thêm versioning/Object Lock, retention và sao lưu khác tài khoản.
+
+## Phục hồi
+
+`make restore-raw MANIFEST=manifests/<sha256>.json RESTORE_DB=restore_lab`
+khôi phục vào database mới, kiểm tra hash file, schema, số dòng, dữ liệu active
+và toàn bộ tombstone. Chạy lại cùng manifest không nhân bản. Snapshot khác phải
+vào database khác. Watermark của pipeline đang chạy không bị thay đổi.
+
+Phục hồi snapshot khác với tải lại nguồn hiện tại: hạ watermark không tạo được
+lịch sử đã mất ở SQL Server. Khi nối nguồn vào database phục hồi cần quy trình
+rebaseline riêng; không dùng bộ đếm rowversion giữa hai database SQL Server.
+
+## Đánh đổi
+
+Mỗi batch lưu full snapshot phù hợp lab ~83 nghìn dòng; lịch sử tốn dung lượng.
+Quy mô lớn chuyển CDC/Change Tracking + lịch sử thay đổi và checkpoint định kỳ.
diff --git a/docs/adr/0003-bao-cao-pivot-dong.md b/docs/adr/0003-bao-cao-pivot-dong.md
new file mode 100644
index 0000000..343f327
--- /dev/null
+++ b/docs/adr/0003-bao-cao-pivot-dong.md
@@ -0,0 +1,47 @@
+# ADR-0003: Giữ báo cáo PIVOT động dạng dọc làm nguồn chính
+
+- Trạng thái: Đã chấp nhận
+- Ngày: 2026-10-09
+
+## Bối cảnh
+
+`dbo.sp_refresh_category_monthly_revenue` tạo cột động theo các tháng xuất hiện
+trong đơn hàng. Schema của bảng đích vì vậy thay đổi khi có tháng mới. dbt cần
+một model ổn định để downstream tham chiếu, kiểm thử và đối chiếu.
+
+## Các phương án
+
+| Phương án | Ưu | Nhược |
+|---|---|---|
+| Chỉ giữ dạng ngang/PIVOT động | Gần cấu trúc báo cáo SQL Server hiện tại | Số cột thay đổi theo dữ liệu; khó tham chiếu và test ổn định trong dbt |
+| Chỉ giữ dạng dọc | Schema cố định; dễ lọc tháng, kiểm thử và làm phân tích tiếp | Người dùng quen báo cáo mỗi tháng một cột phải đổi cách đọc |
+| Dạng dọc làm nguồn chính, dạng ngang làm mart tương thích | Có mô hình ổn định và vẫn giữ giao diện báo cáo cũ | Cần duy trì thêm một model pivot với cột động |
+
+## Quyết định
+
+Chọn phương án thứ ba. `int_category_monthly_revenue` là nguồn chuẩn ở dạng
+dọc gồm `category`, `year_month`, `revenue`. `mart_category_monthly_revenue`
+là lớp tương thích dạng ngang, sinh các cột tháng có trong orders tại lúc dbt
+chạy.
+
+Danh sách tháng lấy từ mọi order hiện hành, còn doanh thu chỉ tính các đơn
+`PAID`, `SHIPPED`, `COMPLETED`, để khớp ý nghĩa procedure cũ. Do đó tháng chỉ
+có đơn ngoài các status này có thể tồn tại như một cột với giá trị `NULL`.
+
+## Hệ quả
+
+- Downstream mới nên tham chiếu model dạng dọc để schema và test không phụ
+  thuộc lịch chạy.
+- Báo cáo cần mỗi tháng một cột có thể dùng mart ngang; cần chạy lại
+  `dbt build` để cập nhật schema khi xuất hiện tháng mới.
+- Khi đối soát, so cả tháng trong danh sách cột lẫn giá trị; không coi `NULL`
+  của tháng không có doanh thu đủ điều kiện là doanh thu 0 nếu giao diện cần
+  phân biệt hai trạng thái.
+- Bằng chứng đối chiếu hiện tại nằm tại
+  [`../evidence/dbt-sqlserver-reconciliation.md`](../evidence/dbt-sqlserver-reconciliation.md).
+
+## Nguồn không còn đơn hàng
+
+Procedure được sửa để xóa bảng pivot cũ và tạo bảng rỗng chỉ có `category`.
+Trước đây `RETURN` sớm giữ số liệu hôm trước. Đây là sửa lỗi baseline cần ghi rõ
+trong migration notes; không che giấu sai khác bằng cách nới ngưỡng đối soát.
diff --git a/docs/adr/0004-nguong-sai-so-va-snapshot-doi-soat.md b/docs/adr/0004-nguong-sai-so-va-snapshot-doi-soat.md
new file mode 100644
index 0000000..363bb04
--- /dev/null
+++ b/docs/adr/0004-nguong-sai-so-va-snapshot-doi-soat.md
@@ -0,0 +1,60 @@
+# ADR-0004: Ngưỡng sai số và snapshot đối soát
+
+- Trạng thái: Đã chấp nhận
+- Ngày: 2026-10-11
+
+## Bối cảnh
+
+Đối soát SQL Server với dbt/Postgres so sánh các báo cáo được tạo bởi hai
+engine khác nhau. Báo cáo cũ và mart mới có thể được tính tại hai thời điểm
+khác nhau nếu nguồn thay đổi giữa ingestion và batch. Một số sai khác, như hòa
+doanh thu ở ranh giới top 3, không có quy tắc phân hạng tương ứng trong
+procedure cũ. Ngoài ra, ngày hiện được tính theo UTC; đổi sang giờ Việt Nam sẽ
+thay đổi phân bổ ngày và có thể làm thay đổi báo cáo nghiệp vụ.
+
+## Các phương án
+
+| Phương án | Ưu | Nhược |
+|---|---|---|
+| (a) So tuyệt đối và chạy tay khi rảnh | Quy tắc đơn giản; sai khác nào cũng lộ rõ | Bất tiện với sai số biểu diễn; không bảo đảm cùng snapshot; đối soát không đều và hòa hạng dễ thành lỗi giả |
+| (b) Ngưỡng sai số + snapshot fingerprint + `SKIP` | Tự động hóa được; chỉ kết luận khi cùng lát cắt nguồn; phân biệt sai khác chấp nhận được | Phải duy trì fingerprint và điều tra nếu `SKIP` kéo dài |
+| (c) Đóng băng nguồn mỗi lần đối soát | Hai phía dùng cùng một snapshot dễ xác định | Cần dừng/khóa ghi ở hệ thống cũ; ảnh hưởng vận hành và không phù hợp chạy song song liên tục |
+
+## Quyết định
+
+Chọn phương án **(b)**.
+
+- Tiền được chuẩn hóa về hai chữ số thập phân; chấp nhận độ lệch tuyệt đối
+  không quá **0,01 VND**.
+- So sánh theo năm cấp: số dòng/tập cột, aggregate, nhóm, từng khóa và
+  checksum. Giá trị `NULL` không đồng nhất với 0.
+- Kết quả có bốn trạng thái: `PASS` (khớp), `WARN` (chênh lệch được chấp nhận,
+  như hòa hạng hoặc checksum khác trong ngưỡng L4), `SKIP` (snapshot không
+  khớp hoặc chưa đủ điều kiện kết luận), `FAIL` (sai khác ngoài quy tắc chấp
+  nhận).
+- Hòa doanh thu tại ranh giới top 3 chỉ là `WARN` khi measure doanh thu bằng
+  nhau và chỉ khác cột sản phẩm do procedure cũ không quy định tie-break.
+- Fingerprint bốn bảng gồm số dòng, max rowversion và SHA-256 toàn bộ giá trị
+  đã chuẩn hóa, sắp theo khóa. Batch cũ kiểm tra trước/sau; ingestion và dbt
+  cùng ghi `ingest_run_id`. Đối soát kiểm tra lại fingerprint trước và sau.
+- Chỉ build đầy đủ mới có trạng thái PASS. Build mới hơn bị lỗi hoặc PARTIAL
+  chặn nghiệm thu; không dùng PASS cũ để thay thế.
+- Một run phải đủ L0–L5 cho cả bảy báo cáo, tất cả PASS, cùng snapshot và không
+  có dòng lệch mới đủ điều kiện cutover. Debug không ghi kết quả; SKIP trả lỗi.
+- Đây là phép kiểm tra ổn định trong cửa sổ lab, không phải distributed snapshot.
+  Đóng băng ghi lúc cutover. Nếu nguồn ghi liên tục, cần CDC/LSN hoặc snapshot
+  transaction đồng bộ; hash trước/sau không tự tạo snapshot isolation.
+
+## Hệ quả
+
+- `SKIP` tránh ghi nhận sai khác giả do hai phía tính từ dữ liệu khác thời
+  điểm; `SKIP` kéo dài vẫn là **sự cố vận hành**, cần khôi phục ingestion và
+  đồng bộ snapshot thay vì bỏ qua điều kiện.
+- Trạng thái chi tiết ở `recon.results`; trạng thái toàn run ở `recon.runs`.
+  DAG chỉ xanh khi run đủ điều kiện; WARN vẫn phải điều tra, không tính ngày xanh.
+- Quy tắc ngày UTC được giữ nguyên trong thời gian di chuyển. Đổi sang ngày giờ
+  Việt Nam là **thay đổi nghiệp vụ** sau cutover, chỉ thực hiện khi nghiệp vụ
+  duyệt; không sửa đồng thời với việc chuyển nền tảng (“làm đúng trước”, quy
+  tắc 4).
+- Quy trình và kết quả kiểm chứng được ghi trong
+  [`../reconciliation.md`](../reconciliation.md).
diff --git a/docs/adr/0005-bat-thay-doi-bang-rowversion.md b/docs/adr/0005-bat-thay-doi-bang-rowversion.md
index c45351f..cfc2381 100644
--- a/docs/adr/0005-bat-thay-doi-bang-rowversion.md
+++ b/docs/adr/0005-bat-thay-doi-bang-rowversion.md
@@ -29,19 +29,20 @@ Dùng watermark `rowversion`, lưu ở `etl.watermarks.last_rowversion` dạng
 - Cận trên an toàn của mỗi lần chạy là `MIN_ACTIVE_ROWVERSION() - 1`, không dùng
   `@@DBTS`, để không bỏ sót dòng của transaction đang mở
   ([lessons_learned.md](../lessons_learned.md), mục 1).
-- Một lần chạy đọc cận trên **một lần** rồi dùng chung cho cả 4 bảng, để 4 bảng
-  là cùng một lát cắt nguồn.
+- Một lần chạy đọc cận trên **một lần** rồi dùng chung cho cả 4 bảng, để giới hạn
+  khoảng tải; cách này không tạo snapshot transaction giữa bốn kết nối. Sau tải
+  phải kiểm tra full fingerprint và chốt batch; không khớp thì chạy lại.
 - Điều kiện tải: `row_ver > watermark_cũ AND row_ver <= cận_trên`. Watermark chỉ
   được cập nhật trong cùng transaction với lệnh nạp raw, nên lỗi giữa chừng không
   làm mất dữ liệu.
-- Trước mỗi lần tải, so danh sách cột nguồn với cấu hình; khác nhau thì dừng với
+- Trước mỗi lần tải, so tên cột, kiểu, độ dài, precision/scale, nullable và datetime precision; khác nhau thì dừng với
   `SchemaDriftError` thay vì ghi sai.
 - DELETE được xử lý riêng bằng so sánh tập khóa ([ADR-0001](./0001-xu-ly-dong-bi-xoa.md)).
 
 ## Hệ quả
 
 - Không cần sửa ứng dụng hay xin quyền DBA để bật tính năng mới.
-- Chạy lại cùng khoảng watermark cho ra cùng file Parquet và upsert không tạo
+- File Parquet được định danh bằng SHA-256 và upsert không tạo
   trùng ([ADR-0002](./0002-raw-dang-upsert.md)).
 - Khi dữ liệu lớn hoặc cần bắt DELETE ngay trong lần tải, chuyển sang Change
   Tracking theo ngưỡng đã ghi trong ADR-0001.
diff --git a/docs/adr/0006-chon-dbt-cho-tang-bien-doi.md b/docs/adr/0006-chon-dbt-cho-tang-bien-doi.md
index 220430d..cae11ec 100644
--- a/docs/adr/0006-chon-dbt-cho-tang-bien-doi.md
+++ b/docs/adr/0006-chon-dbt-cho-tang-bien-doi.md
@@ -44,3 +44,9 @@ cho từng procedure).
   mục 7).
 - Model có pivot động phụ thuộc dữ liệu lúc biên dịch; đã thêm điều kiện để
   `dbt compile` chạy được trên database mới ([lessons_learned.md](../lessons_learned.md), mục 10).
+
+## Theo dõi build
+
+CLI và Airflow chạy qua `reconciliation.build`: giữ khóa ghi raw của pipeline,
+kiểm tra freshness từng bảng, ghi batch đầu vào và invocation ID. Chỉ build đủ
+model/test mới PASS; build một phần phục vụ debug trả mã 2 và không dùng cutover.
diff --git a/docs/cost_estimate.md b/docs/cost_estimate.md
index 87d67bb..e81bf83 100644
--- a/docs/cost_estimate.md
+++ b/docs/cost_estimate.md
@@ -35,7 +35,15 @@ bạn tự điền theo thực tế.
 
 Trang giá chính thức của AWS chỉ hiển thị sẵn số liệu ví dụ của **US East (N.
 Virginia)**, nên bảng dưới dùng giá us-east-1. Region gần Việt Nam là
-ap-southeast-1 (Singapore), thường đắt hơn; cập nhật lại bằng Pricing Calculator.
+ap-southeast-1 (Singapore); bảng này chưa phải dự toán triển khai Singapore.
+Để minh họa plan cùng region với bảng giá: `TF_VAR_aws_region=us-east-1 make tf-plan`.
+Nếu dùng default Singapore, tạo lại estimate từ Pricing Calculator với region đó
+và lưu bản xuất estimate. Không chỉ đổi nhãn region trên bảng giá.
+
+Ngày rà soát nguồn: 2026-10-14; các số dưới đây là baseline tham khảo theo trang
+nguồn, chưa phải báo giá đầy đủ. Chưa gồm S3 requests, network/NAT, logging,
+backup, BI hosting, thuế và chi phí di chuyển. Mục đích học tập; phải bổ sung các
+hạng mục này trước khi quyết định ngân sách.
 
 ## 2. Đơn giá đã tra
 
@@ -47,7 +55,7 @@ ap-southeast-1 (Singapore), thường đắt hơn; cập nhật lại bằng Pri
 | Amazon MWAA, môi trường Small | $0,49 / giờ | [Amazon MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/) |
 | Amazon MWAA, lưu metadata | $0,10 / GB-tháng | như trên |
 | Secrets Manager | $0,40 / secret-tháng; $0,05 / 10.000 lần gọi API | [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/) |
-| SQL Server 2025 Standard, thuê bao | $1.418 / năm cho gói 2 core (tối thiểu 4 core mỗi server) | Bảng giá SQL Server 2025 của Microsoft, theo [datasheet tổng hợp](https://www.licensingschool.co.uk/wp-content/uploads/2025/11/SQL-Server-2025-Pricing-Datasheet.pdf) |
+| SQL Server 2025 Standard, thuê bao | $1.418 / năm cho gói 2 core (tối thiểu 4 core mỗi server) | Bảng giá SQL Server 2025 của Microsoft, theo [datasheet chính thức Microsoft](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/bade/documents/products-and-services/en-us/security/644401-sql-server-2025-pricing.pdf) |
 | SQL Server 2025 Standard, mua đứt | $3.945 / gói 2 core (giá bán lẻ ước tính) | như trên |
 
 Môi trường lab dùng SQL Server **Developer**, miễn phí nhưng không được dùng cho
@@ -98,8 +106,8 @@ Nhận xét:
    phải tiết kiệm hạ tầng.
 2. **MWAA chiếm khoảng 94% chi phí AWS ở quy mô lab** vì chạy liên tục bất kể
    khối lượng. Đây là chỗ đầu tiên cần tối ưu.
-3. **Khi dữ liệu tăng, AWS tăng chậm hơn**: Redshift Serverless tính theo thời
-   gian có truy vấn, còn SQL Server phải mua thêm core và máy mạnh hơn trước.
+3. Với giả định thời gian truy vấn trong bảng, chi phí AWS tăng ít hơn. Đây
+   là kết quả của giả định; cần benchmark khi tăng dữ liệu, không mặc định tăng 100 lần vẫn chỉ tốn 2 giờ/ngày.
 4. Kết luận phụ thuộc mạnh vào giả định giá máy chủ và giờ vận hành; thay bằng
    số thật trước khi dùng để ra quyết định.
 
diff --git a/docs/cutover_plan.md b/docs/cutover_plan.md
index 1d21aa3..022e0e3 100644
--- a/docs/cutover_plan.md
+++ b/docs/cutover_plan.md
@@ -1,5 +1,9 @@
 # Kế hoạch cutover và rollback
 
+> Trạng thái: runbook cần diễn tập; chưa có bằng chứng cutover/rollback thành công.
+> Sau khi triển khai bản vá, đối chiếu quy trình chi tiết trong
+> `HUONG_DAN_HOAN_THIEN_DAY_DU.md`, mục cutover và rollback.
+
 Mục tiêu: chuyển 7 báo cáo từ job ban đêm trên SQL Server sang pipeline Airflow
 + dbt mà người dùng báo cáo không thấy số liệu sai, và quay lại được hệ thống cũ
 trong vài phút nếu có sự cố.
@@ -40,7 +44,7 @@ Tất cả phải đúng tại thời điểm họp Go/No-Go (T-1):
 
 | # | Điều kiện | Cách kiểm tra |
 |---|---|---|
-| 1 | Đủ **5 ngày đối soát xanh liên tiếp**: đủ 7 báo cáo, tất cả PASS, 0 dòng lệch, không bỏ trống ngày nào | `make readiness` trả exit code 0; Q4 trên dashboard ≥ 5 |
+| 1 | Đủ **5 ngày đối soát xanh liên tiếp**: mỗi ngày một run hoàn chỉnh, đủ 7 báo cáo, tất cả PASS, 0 dòng lệch, không bỏ trống ngày nào | `make readiness` trả exit code 0; Q4 trên dashboard ≥ 5 |
 | 2 | Không có `SKIP` kéo dài hay `WARN` chưa được duyệt trong 5 ngày đó | Q2 trên dashboard |
 | 3 | `dbt build` và `dbt source freshness` xanh ở lần chạy gần nhất | Airflow, DAG `transform_dbt` |
 | 4 | CI xanh trên nhánh `main` | Tab Actions trên GitHub |
@@ -76,7 +80,7 @@ chuỗi đếm lại từ 0.
    nghiệp vụ trên Metabase từ bảng `dbo.*` (SQL Server) sang bảng `marts.*`
    (PostgreSQL) theo bảng ở mục 1. Ghi lại danh sách câu hỏi đã đổi để rollback.
 5. **Kiểm tra nhanh:** chủ sở hữu nghiệp vụ mở 3 báo cáo quan trọng nhất (doanh
-   thu ngày, phân khúc khách hàng, top sản phẩm) và so với số của hôm trước.
+   thu ngày, phân khúc khách hàng, top sản phẩm) và so với kết quả SQL Server trong cùng lần chốt cuối cùng.
 6. **Bật lại nguồn:** bật lại `simulate_source_activity` (lab) hoặc mở lại giao dịch.
 7. **Thông báo hoàn tất** qua email và nhóm chat, kèm cách báo lỗi.
 
diff --git a/docs/migration_notes.md b/docs/migration_notes.md
index ac9a8a6..5441851 100644
--- a/docs/migration_notes.md
+++ b/docs/migration_notes.md
@@ -119,3 +119,9 @@ asset raw để `legacy_nightly_batch` và `transform_dbt` chạy; DAG
 trigger trực tiếp reconciliation và không chạy `simulate` giữa ingestion với
 hai nhánh batch/dbt. Kết quả bằng chứng ban đầu đã lưu tại
 [`evidence/dbt-sqlserver-reconciliation.md`](./evidence/dbt-sqlserver-reconciliation.md).
+
+## Sửa lỗi baseline pivot rỗng (2026-10-14)
+
+Khi không còn order, procedure cũ RETURN trước khi xóa bảng pivot, giữ số hôm
+trước. Sửa để tạo bảng rỗng chỉ có category. Ca này được kiểm tra trong
+`scripts/integration_lab.py`; không coi số tồn dư cũ là yêu cầu nghiệp vụ.
diff --git a/docs/reconciliation.md b/docs/reconciliation.md
index 9a622f4..7e4d249 100644
--- a/docs/reconciliation.md
+++ b/docs/reconciliation.md
@@ -245,3 +245,12 @@ sau mỗi lần xác nhận kết quả trên Q2/Q4, hoặc chạy `make readine
   chuẩn chung.
 - Snapshot bằng `COUNT` + `MAX(rowversion)` quét toàn bảng. Khi dữ liệu lớn,
   xem xét Change Tracking theo [ADR-0001](./adr/0001-xu-ly-dong-bi-xoa.md).
+
+## Cập nhật điều kiện nghiệm thu (2026-10-14)
+
+`recon.runs` là nguồn xác định một run hoàn chỉnh. `v_daily_summary` chỉ lấy một
+run đủ bảy báo cáo trong mỗi ngày VN; không ghép kết quả nhiều run. Lịch sử cũ
+chưa có header vẫn giữ để điều tra nhưng không được tự chuyển thành ngày xanh.
+Freshness kiểm tra riêng từng bảng. `--ignore-snapshot` chỉ in debug và trả mã 2,
+không ghi bảng kết quả. WARN/SKIP/INCOMPLETE không tính ngày xanh. Tài liệu lịch sử
+về fingerprint count/max được thay thế bằng ADR-0004 cập nhật.
diff --git a/reconciliation/build.py b/reconciliation/build.py
new file mode 100644
index 0000000..86273d7
--- /dev/null
+++ b/reconciliation/build.py
@@ -0,0 +1,71 @@
+"""Run dbt with a recorded input batch and preserve failed/partial build attempts."""
+
+import argparse
+import json
+import os
+import subprocess
+import sys
+import tempfile
+import uuid
+from pathlib import Path
+
+from psycopg.types.json import Jsonb
+
+from reconciliation.db import get_pg_connection
+from reconciliation.fingerprint import fingerprint
+from reconciliation.ingest_batch import latest_ingestion
+
+
+def main():
+    parser = argparse.ArgumentParser(description=__doc__)
+    parser.add_argument("--select")
+    args = parser.parse_args()
+    project = Path(os.getenv("DBT_PROJECT_DIR", str(Path(__file__).resolve().parents[1] / "dbt_project")))
+    dbt = os.getenv("DBT_BIN", str(Path(sys.executable).parent / "dbt"))
+    build_id = uuid.uuid4().hex
+    output = Path(tempfile.mkdtemp(prefix="migration-dbt-"))
+    env = dict(os.environ, DBT_TARGET_PATH=str(output / "target"), DBT_LOG_PATH=str(output / "logs"))
+    with get_pg_connection() as guard:
+        guard.autocommit = True
+        guard.execute("SELECT pg_advisory_lock(73001)")
+        try:
+            batch = latest_ingestion(guard)
+            before = fingerprint(guard)
+            if before != batch["fingerprint"]:
+                raise RuntimeError("Raw đã thay đổi sau batch hoàn tất; chạy lại ingestion")
+            guard.execute(
+                "INSERT INTO etl.dbt_builds(build_id,ingest_run_id,fingerprint,status) VALUES (%s,%s,%s,'RUNNING')",
+                (build_id, batch["run_id"], Jsonb(before)),
+            )
+            status, invocation = "FAIL", None
+            try:
+                common = ["--project-dir", str(project), "--profiles-dir", str(project)]
+                subprocess.run([dbt, "source", "freshness", *common], env=env, check=True)
+                command = [dbt, "build", *common]
+                if args.select:
+                    command.extend(["--select", args.select])
+                subprocess.run(command, env=env, check=True)
+                artifact = json.loads((output / "target/run_results.json").read_text())
+                manifest = json.loads((output / "target/manifest.json").read_text())
+                invocation = artifact["metadata"]["invocation_id"]
+                required = {
+                    node_id for node_id, node in manifest["nodes"].items() if node["resource_type"] in {"model", "test"}
+                }
+                passed = {r["unique_id"] for r in artifact["results"] if r["status"] in {"success", "pass"}}
+                if fingerprint(guard) != before:
+                    raise RuntimeError("Raw thay đổi trong khi build")
+                status = "PASS" if required <= passed else "PARTIAL"
+            finally:
+                guard.execute(
+                    "UPDATE etl.dbt_builds SET status=%s,invocation_id=%s,finished_at=now(),artifact_path=%s "
+                    "WHERE build_id=%s",
+                    (status, invocation, str(output), build_id),
+                )
+            print(f"dbt {status}: build_id={build_id}; artifacts={output}")
+            return 0 if status == "PASS" else 2
+        finally:
+            guard.execute("SELECT pg_advisory_unlock(73001)")
+
+
+if __name__ == "__main__":
+    sys.exit(main())
diff --git a/reconciliation/db.py b/reconciliation/db.py
index ab16643..ce1ce66 100644
--- a/reconciliation/db.py
+++ b/reconciliation/db.py
@@ -32,42 +32,38 @@ def fetch_dataset(conn, table: str, columns: list[str] | None = None) -> Dataset
 # ---------------------------------------------------------------- snapshot
 
 
-def legacy_fingerprint(mssql) -> dict[str, dict[str, int | None]]:
-    """Số dòng + rowversion lớn nhất của 4 bảng nguồn tại SQL Server."""
-    cur = mssql.cursor()
-    fingerprint = {}
-    for table in SOURCE_TABLES:
-        cur.execute(f"SELECT COUNT(*), MAX(CAST(row_ver AS BIGINT)) FROM dbo.{table}")
-        rows, max_rv = cur.fetchone()
-        fingerprint[table] = {"rows": int(rows), "max_rowver": None if max_rv is None else int(max_rv)}
-    cur.close()
-    return fingerprint
-
-
-def raw_fingerprint(pg) -> dict[str, dict[str, int | None]]:
-    """Cùng phép đo trên raw Postgres, chỉ tính dòng chưa bị đánh dấu xóa."""
-    fingerprint = {}
-    with pg.cursor() as cur:
-        for table in SOURCE_TABLES:
-            cur.execute(f"SELECT count(*), max(row_ver) FROM raw.{table} WHERE _deleted_at IS NULL")
-            rows, max_rv = cur.fetchone()
-            fingerprint[table] = {"rows": int(rows), "max_rowver": None if max_rv is None else int(max_rv)}
-    return fingerprint
+def legacy_fingerprint(mssql):
+    from reconciliation.fingerprint import fingerprint
+
+    return fingerprint(mssql, source=True)
+
+
+def raw_fingerprint(pg):
+    from reconciliation.fingerprint import fingerprint
+
+    return fingerprint(pg)
 
 
 def record_legacy_batch(
-    pg, batch_id: str, started_at: datetime, finished_at: datetime, before: dict, after: dict
+    pg,
+    batch_id: str,
+    started_at: datetime,
+    finished_at: datetime,
+    before: dict,
+    after: dict,
+    ingest_run_id: str | None = None,
 ) -> bool:
     stable = before == after
     with pg.cursor() as cur:
         cur.execute(
             "INSERT INTO recon.legacy_batches "
-            "(batch_id, started_at, finished_at, fingerprint_before, fingerprint_after, stable) "
-            "VALUES (%s, %s, %s, %s, %s, %s) "
+            "(batch_id, started_at, finished_at, fingerprint_before, fingerprint_after, stable, ingest_run_id) "
+            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
             "ON CONFLICT (batch_id) DO UPDATE SET started_at = EXCLUDED.started_at, "
             "finished_at = EXCLUDED.finished_at, fingerprint_before = EXCLUDED.fingerprint_before, "
-            "fingerprint_after = EXCLUDED.fingerprint_after, stable = EXCLUDED.stable",
-            (batch_id, started_at, finished_at, Jsonb(before), Jsonb(after), stable),
+            "fingerprint_after = EXCLUDED.fingerprint_after, stable = EXCLUDED.stable, "
+            "ingest_run_id=EXCLUDED.ingest_run_id",
+            (batch_id, started_at, finished_at, Jsonb(before), Jsonb(after), stable, ingest_run_id),
         )
     return stable
 
@@ -75,13 +71,13 @@ def record_legacy_batch(
 def latest_legacy_batch(pg) -> dict | None:
     with pg.cursor() as cur:
         cur.execute(
-            "SELECT batch_id, finished_at, fingerprint_after, stable "
+            "SELECT batch_id, finished_at, fingerprint_after, stable, ingest_run_id "
             "FROM recon.legacy_batches ORDER BY finished_at DESC LIMIT 1"
         )
         row = cur.fetchone()
     if row is None:
         return None
-    return {"batch_id": row[0], "finished_at": row[1], "fingerprint": row[2], "stable": row[3]}
+    return {"batch_id": row[0], "finished_at": row[1], "fingerprint": row[2], "stable": row[3], "ingest_run_id": row[4]}
 
 
 # ---------------------------------------------------------------- ghi kết quả
diff --git a/reconciliation/fingerprint.py b/reconciliation/fingerprint.py
new file mode 100644
index 0000000..b4eb719
--- /dev/null
+++ b/reconciliation/fingerprint.py
@@ -0,0 +1,46 @@
+"""Compare all source values, not only row counts and the largest rowversion."""
+
+import hashlib
+import json
+from datetime import date, datetime
+from decimal import Decimal
+
+from ingest_incremental import TABLES
+
+
+def canonical(value):
+    if isinstance(value, datetime):
+        return value.isoformat(timespec="microseconds")
+    if isinstance(value, date):
+        return value.isoformat()
+    if isinstance(value, Decimal):
+        return format(value, ".2f")
+    return value
+
+
+def fingerprint(conn, source=False):
+    result = {}
+    for name, cfg in TABLES.items():
+        columns = cfg["columns"] + ["row_ver"]
+        select = cfg["columns"] + (["CAST(row_ver AS BIGINT)"] if source else ["row_ver"])
+        where = "" if source else " WHERE _deleted_at IS NULL"
+        cursor = conn.cursor()
+        try:
+            cursor.execute(
+                f"SELECT {', '.join(select)} FROM {'dbo' if source else 'raw'}.{name}{where} ORDER BY {cfg['key']}"
+            )
+            digest = hashlib.sha256()
+            count, maximum = 0, None
+            while rows := cursor.fetchmany(2000):
+                for row in rows:
+                    values = [canonical(v) for v in row]
+                    if "is_active" in columns:
+                        values[columns.index("is_active")] = bool(values[columns.index("is_active")])
+                    digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode())
+                    digest.update(b"\n")
+                    count += 1
+                    maximum = max(maximum or 0, int(row[-1]))
+            result[name] = {"rows": count, "max_rowver": maximum, "sha256": digest.hexdigest()}
+        finally:
+            cursor.close()
+    return result
diff --git a/reconciliation/ingest_batch.py b/reconciliation/ingest_batch.py
new file mode 100644
index 0000000..567e90a
--- /dev/null
+++ b/reconciliation/ingest_batch.py
@@ -0,0 +1,42 @@
+"""Publish a completed ingestion only after source and raw contents match."""
+
+from archive_raw import archive
+from psycopg import IsolationLevel
+from psycopg.types.json import Jsonb
+
+from reconciliation.db import get_legacy_connection, get_pg_connection
+from reconciliation.fingerprint import fingerprint
+
+
+def complete_ingestion(run_id):
+    with get_legacy_connection() as source, get_pg_connection() as pg:
+        pg.isolation_level = IsolationLevel.REPEATABLE_READ
+        pg.execute("SELECT pg_advisory_xact_lock(73001)")
+        before = fingerprint(source, source=True)
+        current = fingerprint(pg)
+        if before != current:
+            raise RuntimeError("Nguồn và raw chưa cùng trạng thái; chạy lại ingestion đầy đủ")
+        with pg.cursor() as cur:
+            cur.execute("SELECT table_name FROM etl.ingest_log WHERE run_id=%s", (run_id,))
+            if {r[0] for r in cur.fetchall()} != set(current):
+                raise RuntimeError("Ingestion chưa có log đủ 4 bảng")
+        manifest_key = archive(run_id, pg, current)
+        after = fingerprint(source, source=True)
+        if before != after:
+            raise RuntimeError("Nguồn thay đổi khi chốt batch; chưa phát hành batch này")
+        pg.execute(
+            "INSERT INTO etl.ingest_batches(run_id, fingerprint, manifest_key) VALUES (%s,%s,%s) "
+            "ON CONFLICT(run_id) DO UPDATE SET fingerprint=EXCLUDED.fingerprint, "
+            "manifest_key=EXCLUDED.manifest_key, finished_at=now()",
+            (run_id, Jsonb(current), manifest_key),
+        )
+    return manifest_key
+
+
+def latest_ingestion(pg):
+    row = pg.execute(
+        "SELECT run_id,fingerprint,finished_at FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
+    ).fetchone()
+    if row is None:
+        raise RuntimeError("Chưa có batch ingestion hoàn tất: chạy make ingest-all hoặc DAG ingest_legacy")
+    return {"run_id": row[0], "fingerprint": row[1], "finished_at": row[2]}
diff --git a/reconciliation/legacy_batch.py b/reconciliation/legacy_batch.py
index 9926f79..c9095e3 100644
--- a/reconciliation/legacy_batch.py
+++ b/reconciliation/legacy_batch.py
@@ -20,8 +20,14 @@ class LegacyBatchUnstable(RuntimeError):
 
 
 def run_legacy_batch(batch_id: str) -> dict:
+    from reconciliation.ingest_batch import latest_ingestion
+
+    with get_pg_connection() as pg:
+        ingest = latest_ingestion(pg)
     with get_legacy_connection() as mssql:
         before = legacy_fingerprint(mssql)
+        if before != ingest["fingerprint"]:
+            raise LegacyBatchUnstable("Nguồn khác batch ingestion; cần chạy lại ingestion")
         started_at = datetime.now(UTC)
         cur = mssql.cursor()
         cur.execute("EXEC dbo.sp_run_nightly_batch")
@@ -30,7 +36,7 @@ def run_legacy_batch(batch_id: str) -> dict:
         after = legacy_fingerprint(mssql)
 
     with get_pg_connection() as pg:
-        stable = record_legacy_batch(pg, batch_id, started_at, finished_at, before, after)
+        stable = record_legacy_batch(pg, batch_id, started_at, finished_at, before, after, ingest["run_id"])
 
     if not stable:
         raise LegacyBatchUnstable(f"Nguồn thay đổi trong lúc chạy batch {batch_id}: trước={before}, sau={after}")
diff --git a/reconciliation/lifecycle.py b/reconciliation/lifecycle.py
new file mode 100644
index 0000000..cd15500
--- /dev/null
+++ b/reconciliation/lifecycle.py
@@ -0,0 +1,78 @@
+"""A run is certified only after all seven reports and their checks complete."""
+
+from collections import Counter, defaultdict
+
+from psycopg.types.json import Jsonb
+
+from reconciliation.db import get_pg_connection
+from reconciliation.specs import REPORTS
+
+
+def expected_levels(spec):
+    aggregates = sum(
+        2 if col.kind == "text" else 3 if col.kind == "date" else 4
+        for col in spec.value_columns
+        if col.name not in spec.tie_columns
+    )
+    return Counter(
+        {
+            "L0_snapshot": 1,
+            "L1_row_count": 2 if spec.pivot_id else 1,
+            "L2_aggregate": aggregates,
+            "L3_group": 1,
+            "L4_row": 1,
+            "L5_checksum": 1,
+        }
+    )
+
+
+def begin_run(run_id, reports, snapshot):
+    with get_pg_connection() as pg, pg.cursor() as cur:
+        cur.execute("DELETE FROM recon.results WHERE run_id=%s", (run_id,))
+        cur.execute("DELETE FROM recon.row_diffs WHERE run_id=%s", (run_id,))
+        cur.execute(
+            "INSERT INTO recon.runs(run_id, requested_reports, snapshot, status) VALUES (%s,%s,%s,'RUNNING') "
+            "ON CONFLICT(run_id) DO UPDATE SET requested_reports=EXCLUDED.requested_reports, "
+            "snapshot=EXCLUDED.snapshot, started_at=now(), finished_at=NULL, "
+            "status='RUNNING', eligible_for_cutover=false",
+            (run_id, reports, Jsonb(snapshot)),
+        )
+
+
+def classify_checks(rows, reports, snapshot_ok):
+    by_report = defaultdict(list)
+    for report, level, status in rows:
+        by_report[report].append((level, status))
+    complete = set(by_report) == set(reports)
+    for report in reports:
+        complete &= Counter(level for level, _ in by_report[report]) == expected_levels(REPORTS[report])
+    statuses = {status for _, _, status in rows}
+    if "FAIL" in statuses:
+        status = "FAIL"
+    elif "SKIP" in statuses or not snapshot_ok:
+        status = "SKIP"
+    elif not complete:
+        status = "INCOMPLETE"
+    elif "WARN" in statuses:
+        status = "WARN"
+    else:
+        status = "PASS"
+    eligible = complete and snapshot_ok and status == "PASS" and set(reports) == set(REPORTS)
+    return status, eligible
+
+
+def finish_run(run_id, snapshot_after):
+    with get_pg_connection() as pg, pg.cursor() as cur:
+        cur.execute("SELECT requested_reports,snapshot FROM recon.runs WHERE run_id=%s FOR UPDATE", (run_id,))
+        record = cur.fetchone()
+        if record is None:
+            raise RuntimeError("Run chưa được khởi tạo")
+        reports, snapshot_before = record
+        cur.execute("SELECT report,check_level,status FROM recon.results WHERE run_id=%s", (run_id,))
+        snapshot_ok = bool(snapshot_before.get("ok")) and snapshot_before == snapshot_after
+        status, eligible = classify_checks(cur.fetchall(), reports, snapshot_ok)
+        cur.execute(
+            "UPDATE recon.runs SET finished_at=now(),status=%s,eligible_for_cutover=%s WHERE run_id=%s",
+            (status, eligible, run_id),
+        )
+    return {"status": status, "eligible_for_cutover": eligible}
diff --git a/reconciliation/readiness.py b/reconciliation/readiness.py
index 0e42418..b1714c6 100644
--- a/reconciliation/readiness.py
+++ b/reconciliation/readiness.py
@@ -22,6 +22,10 @@ def evaluate(green_days: int, last_run_date: date | None, today: date, required:
 
     green_days là chuỗi xanh kết thúc ở last_run_date (ngày chạy gần nhất không xanh => 0).
     """
+    if required < 1:
+        raise ValueError("Số ngày yêu cầu phải >= 1")
+    if last_run_date is not None and last_run_date > today:
+        return ["Ngày đối soát nằm trong tương lai: kiểm tra đồng hồ hệ thống"]
     if last_run_date is None:
         return ["chưa có lần đối soát nào trong recon.results"]
     problems = []
diff --git a/reconciliation/run.py b/reconciliation/run.py
index 68c4240..bf64f12 100644
--- a/reconciliation/run.py
+++ b/reconciliation/run.py
@@ -9,10 +9,13 @@ import argparse
 import os
 import sys
 import uuid
+from datetime import datetime
 from decimal import Decimal
+from zoneinfo import ZoneInfo
 
 from reconciliation.compare import (
     FAIL,
+    PASS,
     SKIP,
     CheckResult,
     ReportOutcome,
@@ -32,31 +35,45 @@ TOLERANCE = Decimal(os.getenv("RECON_MONEY_TOLERANCE", "0.01"))
 
 
 def check_snapshot() -> dict:
-    """Báo cáo cũ và mart mới phải được tính từ CÙNG một trạng thái nguồn.
+    from reconciliation.db import legacy_fingerprint
+    from reconciliation.ingest_batch import latest_ingestion
 
-    So dấu vân tay (số dòng + rowversion lớn nhất của 4 bảng) lúc batch cũ chạy
-    với dấu vân tay của raw Postgres (dữ liệu mà dbt vừa dùng).
-    """
     with get_pg_connection() as pg:
+        try:
+            ingest = latest_ingestion(pg)
+        except RuntimeError as exc:
+            return {"ok": False, "reason": str(exc)}
         batch = latest_legacy_batch(pg)
         current = raw_fingerprint(pg)
-    if batch is None:
-        return {"ok": False, "batch_id": None, "reason": "Chưa có batch cũ nào được ghi nhận (chạy make legacy-batch)"}
-    if not batch["stable"]:
-        return {"ok": False, "batch_id": batch["batch_id"], "reason": "Batch cũ gần nhất chạy khi nguồn đang thay đổi"}
-    mismatched = {
-        t: {"legacy_batch": batch["fingerprint"].get(t), "raw": fp}
-        for t, fp in current.items()
-        if batch["fingerprint"].get(t) != fp
+        build = pg.execute(
+            "SELECT build_id,ingest_run_id,fingerprint,status,invocation_id "
+            "FROM etl.dbt_builds ORDER BY started_at DESC LIMIT 1"
+        ).fetchone()
+    result = {
+        "ok": False,
+        "reason": "Chưa đủ batch cũ và build dbt đã ghi nhận",
+        "ingest_run_id": ingest["run_id"],
+        "batch_id": batch["batch_id"] if batch else None,
+        "build_id": build[0] if build else None,
     }
-    if mismatched:
-        return {
-            "ok": False,
-            "batch_id": batch["batch_id"],
-            "reason": "Snapshot lệch giữa batch cũ và raw",
-            "tables": mismatched,
-        }
-    return {"ok": True, "batch_id": batch["batch_id"], "reason": "Snapshot khớp"}
+    if not batch or not build:
+        return result
+    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
+    if ingest["finished_at"].astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date() != today:
+        result["reason"] = "Chưa có ingestion hoàn tất trong ngày hôm nay"
+        return result
+    with get_legacy_connection() as mssql:
+        source = legacy_fingerprint(mssql)
+    matches = (
+        batch["stable"]
+        and build[3] == "PASS"
+        and batch["ingest_run_id"] == build[1] == ingest["run_id"]
+        and batch["fingerprint"] == build[2] == ingest["fingerprint"] == current == source
+    )
+    result.update(ok=bool(matches), reason="Snapshot khớp" if matches else "Snapshot hoặc batch ID không khớp")
+    result["fingerprint"] = current
+    result["dbt_invocation_id"] = build[4]
+    return result
 
 
 def run_report(name: str, run_id: str, snapshot: dict, ignore_snapshot: bool = False) -> dict:
@@ -84,6 +101,16 @@ def run_report(name: str, run_id: str, snapshot: dict, ignore_snapshot: bool = F
             with get_pg_connection() as pg:
                 new = fetch_dataset(pg, spec.new_table, columns)
             outcome = reconcile(spec, legacy, new, TOLERANCE)
+            outcome.results.insert(
+                0,
+                CheckResult(
+                    name,
+                    "L0_snapshot",
+                    "cùng batch dữ liệu",
+                    PASS if snapshot["ok"] else SKIP,
+                    details={k: v for k, v in snapshot.items() if k != "fingerprint"},
+                ),
+            )
         except Exception as exc:  # lỗi đọc bảng cũng là kết quả đối soát FAIL
             outcome = ReportOutcome(
                 name,
@@ -98,8 +125,9 @@ def run_report(name: str, run_id: str, snapshot: dict, ignore_snapshot: bool = F
                 ],
             )
 
-    with get_pg_connection() as pg:
-        write_outcome(pg, run_id, name, batch_id, outcome.results, outcome.diffs)
+    if not ignore_snapshot:
+        with get_pg_connection() as pg:
+            write_outcome(pg, run_id, name, batch_id, outcome.results, outcome.diffs)
 
     return {
         "report": name,
@@ -125,15 +153,23 @@ def main() -> int:
         for table, sides in snapshot["tables"].items():
             print(f"  {table}: batch cũ={sides['legacy_batch']} raw={sides['raw']}")
 
-    summaries = [
-        run_report(name, args.run_id, snapshot, args.ignore_snapshot) for name in (args.reports or list(REPORTS))
-    ]
+    from reconciliation.lifecycle import begin_run, finish_run
+
+    reports = args.reports or list(REPORTS)
+    if not args.ignore_snapshot:
+        begin_run(args.run_id, reports, snapshot)
+    summaries = [run_report(name, args.run_id, snapshot, args.ignore_snapshot) for name in reports]
 
     print(f"\nrun_id = {args.run_id}")
     print(f"{'Báo cáo':<28}{'Trạng thái':<12}{'Dòng lệch':>10}  Kiểm tra lỗi")
     for s in summaries:
         print(f"{s['report']:<28}{s['status']:<12}{s['diff_rows']:>10}  {', '.join(s['failed_checks'])}")
-    return 1 if any(s["status"] == FAIL for s in summaries) else 0
+    if args.ignore_snapshot:
+        print("DEBUG: không ghi kết quả, không đủ điều kiện cutover")
+        return 2
+    outcome = finish_run(args.run_id, check_snapshot())
+    print("Run:", outcome)
+    return 0 if outcome["status"] == PASS else 1
 
 
 if __name__ == "__main__":
diff --git a/scripts/archive_raw.py b/scripts/archive_raw.py
new file mode 100644
index 0000000..f2013be
--- /dev/null
+++ b/scripts/archive_raw.py
@@ -0,0 +1,133 @@
+"""Archive a complete raw snapshot including tombstones; restore only to restore_* databases."""
+
+import argparse
+import hashlib
+import io
+import json
+import os
+import re
+from pathlib import Path
+
+import psycopg
+import pyarrow as pa
+import pyarrow.parquet as pq
+from botocore.exceptions import ClientError
+from ingest_incremental import TABLES
+from init_minio import get_s3_client
+from load_to_postgres import get_pg_connection
+from psycopg import sql
+
+
+def digest(body):
+    return hashlib.sha256(body).hexdigest()
+
+
+def put_immutable(s3, bucket, key, body):
+    try:
+        s3.put_object(Bucket=bucket, Key=key, Body=body, IfNoneMatch="*")
+    except ClientError as exc:
+        if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
+            raise
+        existing = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
+        if digest(existing) != digest(body):
+            raise RuntimeError(f"Object đã tồn tại với nội dung khác: {key}") from exc
+
+
+def archive(run_id, pg, fingerprint):
+    """Caller owns a REPEATABLE READ transaction containing the validated raw state."""
+    s3, bucket = get_s3_client(), os.environ["MINIO_BUCKET"]
+    manifest = {"version": 1, "run_id": run_id, "fingerprint": fingerprint, "tables": {}}
+    for table, cfg in TABLES.items():
+        columns = cfg["columns"] + ["row_ver", "_loaded_at", "_deleted_at"]
+        with pg.cursor() as cur:
+            cur.execute(f"SELECT {', '.join(columns)} FROM raw.{table} ORDER BY {cfg['key']}")
+            rows = cur.fetchall()
+        data = pa.table({name: [row[i] for row in rows] for i, name in enumerate(columns)})
+        buffer = io.BytesIO()
+        pq.write_table(data, buffer)
+        body = buffer.getvalue()
+        checksum = digest(body)
+        key = f"raw/{table}/snapshots/{checksum}.parquet"
+        put_immutable(s3, bucket, key, body)
+        manifest["tables"][table] = {"key": key, "sha256": checksum, "columns": columns, "rows": len(rows)}
+    body = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()
+    key = f"manifests/{digest(body)}.json"
+    put_immutable(s3, bucket, key, body)
+    return key
+
+
+def validate_manifest(key, body):
+    if key != f"manifests/{digest(body)}.json":
+        raise ValueError("Manifest key/checksum mismatch")
+    manifest = json.loads(body)
+    if manifest.get("version") != 1 or set(manifest.get("tables", {})) != set(TABLES):
+        raise ValueError("Manifest phải chứa đúng 4 bảng và version=1")
+    for table, cfg in TABLES.items():
+        item = manifest["tables"][table]
+        columns = cfg["columns"] + ["row_ver", "_loaded_at", "_deleted_at"]
+        if item["columns"] != columns or item["key"] != f"raw/{table}/snapshots/{item['sha256']}.parquet":
+            raise ValueError(f"Manifest schema/key không hợp lệ: {table}")
+    return manifest
+
+
+def restore(key, database):
+    if not re.fullmatch(r"restore_[a-z0-9_]{1,40}", database):
+        raise ValueError("Database phục hồi phải có tên restore_<chữ thường/số/_>")
+    if database == os.environ["POSTGRES_DB"]:
+        raise ValueError("Không phục hồi đè database đang dùng")
+    s3, bucket = get_s3_client(), os.environ["MINIO_BUCKET"]
+    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
+    manifest = validate_manifest(key, body)
+    with get_pg_connection() as original:
+        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
+    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
+        if not admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
+            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
+    with psycopg.connect(**dict(params, dbname=database)) as target:
+        target.execute((Path(__file__).resolve().parents[1] / "warehouse/raw_restore.sql").read_text())
+        target.execute("CREATE TABLE IF NOT EXISTS etl.restore_manifest (key TEXT PRIMARY KEY)")
+        previous = target.execute("SELECT key FROM etl.restore_manifest").fetchall()
+        if previous:
+            if previous != [(key,)]:
+                raise RuntimeError("Database này đã chứa snapshot khác; hãy dùng tên restore_ mới")
+        else:
+            for table in TABLES:
+                if target.execute(f"SELECT EXISTS(SELECT 1 FROM raw.{table})").fetchone()[0]:
+                    raise RuntimeError("Database đích không rỗng; dừng để giữ dữ liệu")
+            for table, item in manifest["tables"].items():
+                content = s3.get_object(Bucket=bucket, Key=item["key"])["Body"].read()
+                if digest(content) != item["sha256"]:
+                    raise RuntimeError(f"Parquet checksum mismatch: {table}")
+                data = pq.read_table(io.BytesIO(content))
+                if data.column_names != item["columns"] or data.num_rows != item["rows"]:
+                    raise RuntimeError(f"Parquet schema/count mismatch: {table}")
+                rows = zip(*(data[c].to_pylist() for c in item["columns"]), strict=True)
+                with target.cursor() as cur:
+                    cur.executemany(
+                        f"INSERT INTO raw.{table} ({', '.join(item['columns'])}) "
+                        f"VALUES ({', '.join(['%s'] * len(item['columns']))})",
+                        rows,
+                    )
+            target.execute("INSERT INTO etl.restore_manifest VALUES (%s)", (key,))
+        # Compare both active data and complete archived rows, including tombstones.
+        from reconciliation.fingerprint import fingerprint
+
+        if fingerprint(target) != manifest["fingerprint"]:
+            raise RuntimeError("Fingerprint sau phục hồi không khớp")
+        for table, item in manifest["tables"].items():
+            with target.cursor() as cur:
+                cur.execute(f"SELECT {', '.join(item['columns'])} FROM raw.{table} ORDER BY {TABLES[table]['key']}")
+                rows = cur.fetchall()
+            archived = pq.read_table(io.BytesIO(s3.get_object(Bucket=bucket, Key=item["key"])["Body"].read()))
+            expected = list(zip(*(archived[c].to_pylist() for c in item["columns"]), strict=True))
+            if rows != expected:
+                raise RuntimeError(f"Nội dung phục hồi/tombstone không khớp: {table}")
+    print(f"RESTORE PASS: {database}; 4 bảng khớp manifest và tombstone")
+
+
+if __name__ == "__main__":
+    parser = argparse.ArgumentParser(description=__doc__)
+    parser.add_argument("manifest")
+    parser.add_argument("--database", required=True)
+    args = parser.parse_args()
+    restore(args.manifest, args.database)
diff --git a/scripts/ci_local.py b/scripts/ci_local.py
new file mode 100644
index 0000000..ef4b899
--- /dev/null
+++ b/scripts/ci_local.py
@@ -0,0 +1,82 @@
+"""Run CI in a newly created test_* database and remove only that database afterwards."""
+
+import os
+import shutil
+import subprocess
+import sys
+import tempfile
+import uuid
+from pathlib import Path
+
+import psycopg
+from init_minio import get_s3_client  # noqa: F401  (loads .env)
+from load_to_postgres import get_pg_connection
+from psycopg import sql
+
+
+def main():
+    root = Path(__file__).resolve().parents[1]
+    binary = Path(sys.executable).parent
+    name = "test_ci_" + uuid.uuid4().hex[:12]
+    output = Path(tempfile.mkdtemp(prefix="legacy-ci-"))
+    with get_pg_connection() as original:
+        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
+    env = dict(
+        os.environ,
+        POSTGRES_DB=name,
+        MIGRATION_TEST_DB=name,
+        PGDATABASE=name,
+        PGUSER=params["user"],
+        PGPASSWORD=params["password"],
+        PGHOST=params["host"],
+        PGPORT=str(params.get("port", "5432")),
+        DBT_TARGET_PATH=str(output / "target"),
+        DBT_LOG_PATH=str(output / "logs"),
+        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
+    )
+
+    def step(label, command, content=None):
+        print(f"\n--- {label} ---", flush=True)
+        subprocess.run(command, input=content, text=True, cwd=root, env=env, check=True)
+
+    def load(path):
+        command = (
+            ["psql", "-v", "ON_ERROR_STOP=1"]
+            if shutil.which("psql")
+            else [
+                "docker",
+                "compose",
+                "exec",
+                "-T",
+                "postgres",
+                "psql",
+                "-U",
+                params["user"],
+                "-d",
+                name,
+                "-v",
+                "ON_ERROR_STOP=1",
+            ]
+        )
+        step(str(path), command, (root / path).read_text())
+
+    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
+        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
+        try:
+            load(Path("warehouse/init.sql"))
+            load(Path("ci/sample_raw_data.sql"))
+            step("Ruff", [str(binary / "ruff"), "check", "."])
+            step("Format", [str(binary / "ruff"), "format", "--check", "."])
+            step("Unit + SQL integration tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
+            common = ["--project-dir", str(root / "dbt_project"), "--profiles-dir", str(root / "dbt_project")]
+            for action in ["compile", "build", "source freshness"]:
+                step("dbt " + action, [str(binary / "dbt"), *action.split(), *common])
+            load(Path("ci/assert_expected_marts.sql"))
+            step("SQLFluff", [str(binary / "sqlfluff"), "lint", "dbt_project/models", "dbt_project/tests"])
+            print(f"CI PASS; artifacts: {output}")
+        finally:
+            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
+
+
+if __name__ == "__main__":
+    main()
diff --git a/scripts/ingest_incremental.py b/scripts/ingest_incremental.py
index 4b6da69..b375b49 100644
--- a/scripts/ingest_incremental.py
+++ b/scripts/ingest_incremental.py
@@ -63,28 +63,24 @@ def guard_delete_ratio(
 
 
 def check_schema(src, table: str, cfg: dict) -> None:
+    from schema_contract import schema_differences
+
     cur = src.cursor()
     cur.execute(
-        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = %s",
+        "SELECT COLUMN_NAME,DATA_TYPE,CHARACTER_MAXIMUM_LENGTH,NUMERIC_PRECISION,"
+        "NUMERIC_SCALE,IS_NULLABLE,DATETIME_PRECISION FROM INFORMATION_SCHEMA.COLUMNS "
+        "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=%s",
         (table,),
     )
-    source_columns = {row[0] for row in cur.fetchall()}
-    expected_columns = set(cfg["columns"]) | {"row_ver"}
-
-    added = sorted(source_columns - expected_columns)
-    removed = sorted(expected_columns - source_columns)
-    if added or removed:
-        changes = []
-        if added:
-            changes.append(f"cột được thêm: {', '.join(added)}")
-        if removed:
-            changes.append(f"cột bị thiếu: {', '.join(removed)}")
-        raise SchemaDriftError(f"Schema nguồn dbo.{table} đã thay đổi ({'; '.join(changes)})")
+    changes = schema_differences(cur.fetchall(), table)
+    cur.close()
+    if changes:
+        raise SchemaDriftError(f"Schema nguồn dbo.{table} đã thay đổi: {'; '.join(changes)}")
 
 
 def get_watermark(pg, table: str) -> int:
     with pg.cursor() as cur:
-        cur.execute("SELECT last_rowversion FROM etl.watermarks WHERE table_name = %s", (table,))
+        cur.execute("SELECT last_rowversion FROM etl.watermarks WHERE table_name = %s FOR UPDATE", (table,))
         row = cur.fetchone()
     if row is None:
         raise RuntimeError(f"Chưa có dòng watermark cho bảng {table}, hãy chạy make wh")
@@ -119,8 +115,11 @@ def extract_to_minio(src, s3, bucket: str, table: str, cfg: dict, last: int, upp
     data = {name: [row[i] for row in rows] for i, name in enumerate(names)}
     buffer = io.BytesIO()
     pq.write_table(pa.table(data), buffer)
-    key = f"raw/{table}/incremental/rv_{last:020d}_{upper:020d}.parquet"
-    s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
+    from archive_raw import digest, put_immutable
+
+    body = buffer.getvalue()
+    key = f"raw/{table}/incremental/rv_{last:020d}_{upper:020d}_{digest(body)}.parquet"
+    put_immutable(s3, bucket, key, body)
     return key, len(rows)
 
 
@@ -157,6 +156,7 @@ def detect_deletes(table: str) -> int:
     key = cfg["key"]
     deleted_count = 0
     with get_connection() as src, get_pg_connection() as pg:
+        pg.execute("SELECT pg_advisory_xact_lock(73001)")
         src_cur = src.cursor()
         src_cur.execute(f"SELECT {key} FROM dbo.{table}")
         with pg.cursor() as pg_cur:
@@ -215,6 +215,7 @@ def ingest_table(table: str, upper: int | None = None, run_id: str = "manual") -
         raise ValueError(f"Chưa cấu hình bảng '{table}'. Các bảng có sẵn: {', '.join(TABLES)}")
 
     with get_connection() as src, get_pg_connection() as pg:
+        pg.execute("SELECT pg_advisory_xact_lock(73001)")
         check_schema(src, table, cfg)
         last = get_watermark(pg, table)
         upper = get_upper_bound(src) if upper is None else upper
@@ -261,6 +262,12 @@ def main() -> int:
         for selected_table in tables:
             result = ingest_table(selected_table, upper=upper, run_id=run_id)
             print(f"[{result['table']}] Đã tải {result['rows']} dòng (rowversion {result['from']}..{result['to']})")
+        if table == "all":
+            for selected_table in tables:
+                detect_deletes(selected_table)
+            from reconciliation.ingest_batch import complete_ingestion
+
+            print("Manifest:", complete_ingestion(run_id))
     except KeyError as exc:
         print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
         return 1
diff --git a/scripts/integration_lab.py b/scripts/integration_lab.py
new file mode 100644
index 0000000..0662e3d
--- /dev/null
+++ b/scripts/integration_lab.py
@@ -0,0 +1,191 @@
+"""Disposable end-to-end lab; requires the existing local SQL Server/Postgres/MinIO services."""
+
+import os
+import re
+import subprocess
+import sys
+import uuid
+from pathlib import Path
+
+import psycopg
+import pymssql
+from dotenv import load_dotenv
+from psycopg import sql
+
+load_dotenv()
+ROOT = Path(__file__).resolve().parents[1]
+
+
+def main():
+    from init_minio import get_s3_client
+    from load_to_postgres import get_pg_connection
+
+    suffix = uuid.uuid4().hex[:10]
+    database, source_db = "test_e2e_" + suffix, "GuideTest_" + suffix
+    restored, bucket = "restore_e2e_" + suffix, "guide-test-" + suffix
+    with get_pg_connection() as original:
+        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
+    s3 = get_s3_client()
+    sql_params = dict(
+        server=os.getenv("MSSQL_HOST", "localhost"),
+        port=int(os.getenv("MSSQL_PORT", "1433")),
+        user="sa",
+        password=os.environ["MSSQL_SA_PASSWORD"],
+        database="master",
+    )
+    env = dict(
+        os.environ,
+        POSTGRES_DB=database,
+        MSSQL_DATABASE=source_db,
+        MINIO_BUCKET=bucket,
+        MAX_DELETE_RATIO="0.10",
+        PYTHONPATH=str(ROOT / "scripts") + ":" + str(ROOT),
+        DBT_PROJECT_DIR=str(ROOT / "dbt_project"),
+        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
+    )
+    created_pg, created_source, created_bucket = False, False, False
+
+    def run(*args, expected=0):
+        print("\nSTEP:", " ".join(args), flush=True)
+        result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env)
+        if result.returncode != expected:
+            raise RuntimeError(f"{args}: exit {result.returncode}, expected {expected}")
+
+    def load_pg(path):
+        # psql is available inside the already-running postgres container.
+        subprocess.run(
+            [
+                "docker",
+                "compose",
+                "exec",
+                "-T",
+                "postgres",
+                "psql",
+                "-U",
+                params["user"],
+                "-d",
+                database,
+                "-v",
+                "ON_ERROR_STOP=1",
+            ],
+            input=(ROOT / path).read_text(),
+            text=True,
+            cwd=ROOT,
+            env=os.environ,
+            check=True,
+        )
+
+    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
+        source_admin = pymssql.connect(**sql_params, autocommit=True)
+        try:
+            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
+            created_pg = True
+            source_admin.cursor().execute(f"CREATE DATABASE [{source_db}]")
+            created_source = True
+            s3.create_bucket(Bucket=bucket)
+            created_bucket = True
+            load_pg("warehouse/init.sql")
+            load_pg("warehouse/init.sql")  # migration must be rerunnable
+            load_pg("ci/sample_raw_data.sql")
+            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
+                for path in ["sql/01_schema.sql", "sql/02_stored_procedures.sql"]:
+                    content = (ROOT / path).read_text().replace("USE LegacyRetail", f"USE [{source_db}]")
+                    for batch in re.split(r"^\s*GO\s*$", content, flags=re.MULTILINE | re.IGNORECASE):
+                        if batch.strip():
+                            source.cursor().execute(batch)
+                            source.commit()
+                from ingest_incremental import TABLES
+
+                with psycopg.connect(**dict(params, dbname=database)) as pg:
+                    for table, cfg in TABLES.items():
+                        columns = ", ".join(cfg["columns"])
+                        rows = pg.execute(f"SELECT {columns} FROM raw.{table} WHERE _deleted_at IS NULL").fetchall()
+                        cur = source.cursor()
+                        cur.execute(f"SET IDENTITY_INSERT dbo.{table} ON")
+                        cur.executemany(
+                            f"INSERT INTO dbo.{table} ({columns}) VALUES ({', '.join(['%s'] * len(cfg['columns']))})",
+                            rows,
+                        )
+                        cur.execute(f"SET IDENTITY_INSERT dbo.{table} OFF")
+                        source.commit()
+                    pg.execute("TRUNCATE raw.customers,raw.products,raw.orders,raw.order_items,etl.ingest_log")
+                    pg.execute("UPDATE etl.watermarks SET last_rowversion=0,last_run_at=NULL")
+            run("scripts/ingest_incremental.py", "all")
+            run("scripts/ingest_incremental.py", "all")  # retry: no duplicate keys, zero deltas
+            with psycopg.connect(**dict(params, dbname=database)) as pg:
+                latest = pg.execute(
+                    "SELECT run_id FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
+                ).fetchone()[0]
+                assert (
+                    pg.execute("SELECT sum(row_count) FROM etl.ingest_log WHERE run_id=%s", (latest,)).fetchone()[0]
+                    == 0
+                )
+            run("-m", "reconciliation.legacy_batch")
+            run("-m", "reconciliation.build")
+            run("-m", "reconciliation.run")
+            with psycopg.connect(**dict(params, dbname=database)) as pg:
+                assert pg.execute(
+                    "SELECT eligible_for_cutover FROM recon.runs ORDER BY finished_at DESC LIMIT 1"
+                ).fetchone()[0]
+                count = pg.execute("SELECT count(*) FROM recon.results").fetchone()[0]
+            run("-m", "reconciliation.run", "--ignore-snapshot", expected=2)
+            with psycopg.connect(**dict(params, dbname=database)) as pg:
+                assert pg.execute("SELECT count(*) FROM recon.results").fetchone()[0] == count
+            # Change a value at source: snapshot must refuse certification and CLI must fail.
+            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
+                source.cursor().execute("UPDATE dbo.customers SET city=N'Hà Nội 2' WHERE customer_id=1")
+                source.commit()
+            run("-m", "reconciliation.run", expected=1)
+            # Hard delete one of 17 items; 10% is scoped ONLY to this disposable small fixture.
+            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
+                source.cursor().execute("DELETE FROM dbo.order_items WHERE order_item_id=17")
+                source.cursor().execute("UPDATE dbo.orders SET total_amount=0 WHERE order_id=12")
+                source.commit()
+            run("scripts/ingest_incremental.py", "all")
+            run("-m", "reconciliation.legacy_batch")
+            run("-m", "reconciliation.build")
+            run("-m", "reconciliation.run")
+            with psycopg.connect(**dict(params, dbname=database)) as pg:
+                assert pg.execute(
+                    "SELECT _deleted_at IS NOT NULL FROM raw.order_items WHERE order_item_id=17"
+                ).fetchone()[0]
+                manifest = pg.execute(
+                    "SELECT manifest_key FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1"
+                ).fetchone()[0]
+            run("scripts/archive_raw.py", manifest, "--database", restored)
+            run("scripts/archive_raw.py", manifest, "--database", restored)  # replay is idempotent
+            # A later partial build must not inherit an older full PASS.
+            run("-m", "reconciliation.build", "--select", "mart_daily_revenue", expected=2)
+            run("-m", "reconciliation.run", expected=1)
+            with pymssql.connect(**dict(sql_params, database=source_db)) as source:
+                cur = source.cursor()
+                cur.execute(
+                    "DELETE FROM dbo.order_items; DELETE FROM dbo.orders; EXEC dbo.sp_refresh_category_monthly_revenue"
+                )
+                source.commit()
+                cur.execute("SELECT * FROM dbo.category_monthly_revenue")
+                assert cur.fetchall() == []
+                assert [column[0] for column in cur.description] == ["category"]
+            print(
+                "E2E PASS: retry, reconciliation, debug, stale snapshot, delete, restore twice, partial build",
+                flush=True,
+            )
+        finally:
+            if created_pg:
+                for name in [database, restored]:
+                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
+            if created_source:
+                cur = source_admin.cursor()
+                cur.execute(f"ALTER DATABASE [{source_db}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
+                cur.execute(f"DROP DATABASE [{source_db}]")
+            source_admin.close()
+            if created_bucket:
+                for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
+                    objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
+                    if objects:
+                        s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
+                s3.delete_bucket(Bucket=bucket)
+
+
+if __name__ == "__main__":
+    main()
diff --git a/scripts/schema_contract.py b/scripts/schema_contract.py
new file mode 100644
index 0000000..f60a5e1
--- /dev/null
+++ b/scripts/schema_contract.py
@@ -0,0 +1,50 @@
+"""Source schema contract: type, length, precision/scale, nullability."""
+
+CONTRACT = {
+    "customers": {
+        "customer_id": ("int", None, 10, 0, "NO"),
+        "full_name": ("nvarchar", 100, None, None, "NO"),
+        "email": ("varchar", 150, None, None, "NO"),
+        "city": ("nvarchar", 50, None, None, "YES"),
+        "created_at": ("datetime2", None, None, None, "NO"),
+    },
+    "products": {
+        "product_id": ("int", None, 10, 0, "NO"),
+        "product_name": ("nvarchar", 150, None, None, "NO"),
+        "category": ("nvarchar", 50, None, None, "NO"),
+        "unit_price": ("decimal", None, 12, 2, "NO"),
+        "is_active": ("bit", None, None, None, "NO"),
+        "created_at": ("datetime2", None, None, None, "NO"),
+    },
+    "orders": {
+        "order_id": ("int", None, 10, 0, "NO"),
+        "customer_id": ("int", None, 10, 0, "NO"),
+        "order_date": ("datetime2", None, None, None, "NO"),
+        "status": ("varchar", 20, None, None, "NO"),
+        "total_amount": ("decimal", None, 14, 2, "NO"),
+        "updated_at": ("datetime2", None, None, None, "NO"),
+    },
+    "order_items": {
+        "order_item_id": ("int", None, 10, 0, "NO"),
+        "order_id": ("int", None, 10, 0, "NO"),
+        "product_id": ("int", None, 10, 0, "NO"),
+        "quantity": ("int", None, 10, 0, "NO"),
+        "unit_price": ("decimal", None, 12, 2, "NO"),
+    },
+}
+
+
+def schema_differences(rows, table):
+    actual = {}
+    issues = []
+    for name, dtype, length, precision, scale, nullable, datetime_precision in rows:
+        if dtype not in {"int", "decimal", "numeric"}:
+            precision, scale = None, None
+        actual[name] = (dtype, length, precision, scale, nullable)
+        if dtype == "datetime2" and datetime_precision != 0:
+            issues.append(f"{name}: datetime precision {datetime_precision}, expected 0")
+    expected = dict(CONTRACT[table], row_ver=("timestamp", None, None, None, "NO"))
+    for name in sorted(set(actual) | set(expected)):
+        if actual.get(name) != expected.get(name):
+            issues.append(f"{name}: actual={actual.get(name)}, expected={expected.get(name)}")
+    return issues
diff --git a/sql/02_stored_procedures.sql b/sql/02_stored_procedures.sql
index 80ec462..9a8ec5c 100644
--- a/sql/02_stored_procedures.sql
+++ b/sql/02_stored_procedures.sql
@@ -157,7 +157,13 @@ BEGIN
     FROM (SELECT DISTINCT CONVERT(CHAR(7), order_date, 126) AS ym FROM dbo.orders) AS m;
 
     IF @cols IS NULL
+    BEGIN
+        -- Empty source must replace yesterday's pivot, not retain stale results.
+        IF OBJECT_ID(N'dbo.category_monthly_revenue', N'U') IS NOT NULL
+            DROP TABLE dbo.category_monthly_revenue;
+        CREATE TABLE dbo.category_monthly_revenue (category NVARCHAR(50));
         RETURN;
+    END;
 
     -- Số cột thay đổi theo dữ liệu nên bảng đích phải xóa đi tạo lại
     IF OBJECT_ID(N'dbo.category_monthly_revenue', N'U') IS NOT NULL
diff --git a/terraform/.terraform.lock.hcl b/terraform/.terraform.lock.hcl
new file mode 100644
index 0000000..4f69546
--- /dev/null
+++ b/terraform/.terraform.lock.hcl
@@ -0,0 +1,26 @@
+# This file is maintained automatically by "terraform init".
+# Manual edits may be lost in future updates.
+
+provider "registry.terraform.io/hashicorp/aws" {
+  version     = "6.68.0"
+  constraints = "~> 6.0"
+  hashes = [
+    "h1:79hHQtjGSCiXBZK+VDiNUdI2SLXbNaHf+CHySvKFnvA=",
+    "zh:064ed007a33a22d8367db88b18d56a4dd066f07f95b1a4d80ffa2b6ee803f6f0",
+    "zh:20ede4bb730b55023ad426ed13b1b4b295fac4bcc2baa4fb63d2932aa15d760d",
+    "zh:490cffbc315ba21f740158a6b4195e7707ec2ee7ed357a47bb90ed18466f01a2",
+    "zh:7840197f73f53d676373c9aeabccd79c61c6da6e4aa1ed840e57ca46c1894126",
+    "zh:889b15a5c2f7fb168c04c846e75932a6b2ceb7967c3bfa0a0e24be16cdee7969",
+    "zh:96ba7624b6f0e0a1fa5477b0838194be919d815d30ce7f97e04d4520cca4c00b",
+    "zh:9b12af85486a96aedd8d7984b0ff811a4b42e3d88dad1a3fb4c0b580d04fa425",
+    "zh:9b41c2afe2fec1a1880f9427b3ca611abfe6643b41942556a83cd7daae55acf1",
+    "zh:a83e9d46de040fa7bc56f7aa53bdeb8d7078bac65d9155b07022fd75723308b8",
+    "zh:aa5cfdd2faf8a2848c72c13ca88786b857fd397aa713967b8b1f9610f2c76a0b",
+    "zh:abd449fbf38cf828b8b17bc8540752733dd861160504a45b411e72e1792c758c",
+    "zh:b2511842cb6b23036c72babbaf12b4984835bb2824f938882330b51c68bdaecd",
+    "zh:c11e8860c4d611dda93da2e5be27c9bd2599da6ad320f3d12ccc714ffbe6f100",
+    "zh:e4252ceda8641bfe85ad7710b428f994c080bde6c55043ab47a08015432cebdc",
+    "zh:f292ad91c97ac7354a04a698f346c2a0c3866d9170ca45dda6a6bfab71180be0",
+    "zh:f4d293cd0e9562bfa1ba32a1fe5c3652c6a32b951e44081158737d4075696045",
+  ]
+}
diff --git a/tests/test_operational_guards.py b/tests/test_operational_guards.py
new file mode 100644
index 0000000..31cf14a
--- /dev/null
+++ b/tests/test_operational_guards.py
@@ -0,0 +1,104 @@
+import contextlib
+import io
+import sys
+import unittest
+from collections import Counter
+from datetime import date
+from pathlib import Path
+from unittest.mock import MagicMock, patch
+
+sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
+sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
+
+from archive_raw import digest, validate_manifest
+from schema_contract import CONTRACT, schema_differences
+
+from reconciliation import run
+from reconciliation.compare import Dataset, reconcile
+from reconciliation.lifecycle import classify_checks, expected_levels
+from reconciliation.readiness import evaluate
+from reconciliation.specs import REPORTS
+
+
+def full_checks():
+    return [
+        (name, level, "PASS")
+        for name, spec in REPORTS.items()
+        for level, count in expected_levels(spec).items()
+        for _ in range(count)
+    ]
+
+
+class OperationalGuardTests(unittest.TestCase):
+    def test_complete_run_is_eligible(self):
+        self.assertEqual(classify_checks(full_checks(), list(REPORTS), True), ("PASS", True))
+
+    def test_missing_report_is_incomplete(self):
+        rows = [r for r in full_checks() if r[0] != "customer_ltv"]
+        self.assertEqual(classify_checks(rows, list(REPORTS), True), ("INCOMPLETE", False))
+
+    def test_missing_check_is_incomplete(self):
+        self.assertEqual(classify_checks(full_checks()[1:], list(REPORTS), True), ("INCOMPLETE", False))
+
+    def test_changed_snapshot_is_not_eligible(self):
+        self.assertEqual(classify_checks(full_checks(), list(REPORTS), False), ("SKIP", False))
+
+    def test_partial_report_set_never_qualifies(self):
+        rows = [r for r in full_checks() if r[0] == "daily_revenue"]
+        self.assertEqual(classify_checks(rows, ["daily_revenue"], True), ("PASS", False))
+
+    def test_warn_never_qualifies(self):
+        rows = full_checks()
+        rows[0] = (*rows[0][:2], "WARN")
+        self.assertEqual(classify_checks(rows, list(REPORTS), True), ("WARN", False))
+
+    def test_expected_levels_match_actual_engine_for_each_report(self):
+        for name, spec in REPORTS.items():
+            columns = [spec.pivot_id, "2026-10"] if spec.pivot_id else spec.column_names
+            outcome = reconcile(spec, Dataset(columns, []), Dataset(columns, []))
+            actual = Counter(r.level for r in outcome.results)
+            actual["L0_snapshot"] += 1
+            self.assertEqual(actual, expected_levels(spec), name)
+
+    def test_debug_never_writes_results(self):
+        data = Dataset(REPORTS["daily_revenue"].column_names, [])
+        with (
+            patch.object(run, "get_legacy_connection", return_value=MagicMock()),
+            patch.object(run, "get_pg_connection", return_value=MagicMock()),
+            patch.object(run, "fetch_dataset", return_value=data),
+            patch.object(run, "write_outcome") as writer,
+        ):
+            result = run.run_report("daily_revenue", "debug", {"ok": False}, ignore_snapshot=True)
+        writer.assert_not_called()
+        self.assertEqual(result["status"], "SKIP")
+
+    def test_all_skip_cli_exits_nonzero(self):
+        summaries = {"report": "daily_revenue", "status": "SKIP", "diff_rows": 0, "failed_checks": []}
+        with (
+            patch.object(sys, "argv", ["reconciliation"]),
+            patch.object(run, "check_snapshot", return_value={"ok": False, "reason": "mismatch"}),
+            patch.object(run, "run_report", return_value=summaries),
+            patch("reconciliation.lifecycle.begin_run"),
+            patch(
+                "reconciliation.lifecycle.finish_run", return_value={"status": "SKIP", "eligible_for_cutover": False}
+            ),
+            contextlib.redirect_stdout(io.StringIO()),
+        ):
+            self.assertNotEqual(run.main(), 0)
+
+    def test_decimal_scale_drift_is_rejected(self):
+        rows = [(name, *fields, 0 if fields[0] == "datetime2" else None) for name, fields in CONTRACT["orders"].items()]
+        rows.append(("row_ver", "timestamp", None, None, None, "NO", None))
+        self.assertEqual(schema_differences(rows, "orders"), [])
+        changed = [(*r[:4], 3, *r[5:]) if r[0] == "total_amount" else r for r in rows]
+        self.assertTrue(schema_differences(changed, "orders"))
+
+    def test_reject_manifest_digest_mismatch(self):
+        with self.assertRaises(ValueError):
+            validate_manifest(f"manifests/{digest(b'original')}.json", b"changed")
+
+    def test_invalid_readiness_days_and_future_date(self):
+        today = date(2026, 10, 14)
+        with self.assertRaises(ValueError):
+            evaluate(5, today, today, 0)
+        self.assertTrue(evaluate(5, date(2026, 10, 15), today, 5))
diff --git a/tests/test_warehouse_guards.py b/tests/test_warehouse_guards.py
new file mode 100644
index 0000000..a9f3b14
--- /dev/null
+++ b/tests/test_warehouse_guards.py
@@ -0,0 +1,79 @@
+"""SQL integration tests; enabled only for a disposable test_* database."""
+
+import os
+import sys
+import unittest
+from datetime import datetime, timedelta
+from pathlib import Path
+from zoneinfo import ZoneInfo
+
+sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
+sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
+
+from load_to_postgres import get_pg_connection
+
+from reconciliation.specs import REPORTS
+
+
+@unittest.skipUnless(os.getenv("MIGRATION_TEST_DB"), "requires disposable test database")
+class WarehouseGuardTests(unittest.TestCase):
+    def setUp(self):
+        database = os.environ["MIGRATION_TEST_DB"]
+        if not database.startswith("test_") or database != os.environ.get("POSTGRES_DB"):
+            raise RuntimeError("Integration tests require POSTGRES_DB=MIGRATION_TEST_DB=test_...")
+        self.pg = get_pg_connection()
+        self.pg.execute("DELETE FROM recon.runs")
+        self.pg.execute("DELETE FROM recon.results")
+
+    def tearDown(self):
+        self.pg.rollback()
+        self.pg.close()
+
+    def add_run(self, run_id, day, reports=None, eligible=True):
+        reports = list(REPORTS) if reports is None else reports
+        timestamp = f"{day} 01:00:00+07"
+        self.pg.execute(
+            "INSERT INTO recon.runs(run_id,requested_reports,snapshot,started_at,"
+            "finished_at,status,eligible_for_cutover) "
+            "VALUES (%s,%s,'{}',%s,%s,'PASS',%s)",
+            (run_id, reports, timestamp, timestamp, eligible),
+        )
+        for report in reports:
+            self.pg.execute(
+                "INSERT INTO recon.results(run_id,report,check_level,check_name,status,checked_at) "
+                "VALUES (%s,%s,'L1_row_count','test','PASS',%s)",
+                (run_id, report, timestamp),
+            )
+
+    def test_partial_runs_are_not_combined(self):
+        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
+        reports = list(REPORTS)
+        self.add_run("partial-a", today, reports[:4], False)
+        self.add_run("partial-b", today, reports[4:], False)
+        self.assertEqual(self.pg.execute("SELECT count(*) FROM recon.v_daily_summary WHERE green").fetchone()[0], 0)
+
+    def test_calendar_gap_breaks_streak(self):
+        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
+        for days in [0, 1, 3, 4, 5]:
+            self.add_run(f"run-{days}", today - timedelta(days=days))
+        self.assertEqual(self.pg.execute("SELECT green_days FROM recon.v_green_streak").fetchone()[0], 2)
+
+    def test_stale_streak_counts_as_zero(self):
+        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
+        for days in range(3, 8):
+            self.add_run(f"run-{days}", today - timedelta(days=days))
+        self.assertEqual(self.pg.execute("SELECT green_days FROM recon.v_green_streak").fetchone()[0], 0)
+
+    def test_each_table_has_independent_freshness(self):
+        self.pg.execute("UPDATE etl.ingest_log SET loaded_at=now()-interval '10 days' WHERE table_name<>'customers'")
+        row = self.pg.execute(
+            "SELECT (SELECT loaded_at>now()-interval '1 day' FROM etl.freshness_customers),"
+            "(SELECT loaded_at<now()-interval '9 days' FROM etl.freshness_orders)"
+        ).fetchone()
+        self.assertEqual(row, (True, True))
+
+    def test_missing_ingest_log_is_stale(self):
+        self.pg.execute("DELETE FROM etl.ingest_log WHERE table_name='products'")
+        self.assertTrue(
+            self.pg.execute("SELECT loaded_at<now()-interval '50 hours' FROM etl.freshness_products").fetchone()[0]
+        )
diff --git a/warehouse/init.sql b/warehouse/init.sql
index 7ab198f..eaeb777 100644
--- a/warehouse/init.sql
+++ b/warehouse/init.sql
@@ -216,43 +216,86 @@ WHERE r.run_id = (SELECT run_id FROM recon.results ORDER BY checked_at DESC LIMI
 -- Tuần 6: điều kiện cutover (docs/cutover_plan.md)
 -- =====================================================================
 
--- Mỗi ngày (giờ VN) một dòng. Ngày "xanh" khi đủ 7 báo cáo (khớp REPORTS trong
--- reconciliation/specs.py), tất cả PASS và không có dòng lệch. WARN không được
--- tính là xanh: cần người duyệt chênh lệch trước khi đếm ngày.
+-- Completed ingestion snapshots and every dbt attempt are distinct records.
+CREATE TABLE IF NOT EXISTS etl.ingest_batches (
+    run_id TEXT PRIMARY KEY,
+    finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
+    fingerprint JSONB NOT NULL,
+    manifest_key TEXT NOT NULL
+);
+CREATE TABLE IF NOT EXISTS etl.dbt_builds (
+    build_id TEXT PRIMARY KEY,
+    ingest_run_id TEXT NOT NULL REFERENCES etl.ingest_batches(run_id),
+    fingerprint JSONB NOT NULL,
+    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
+    finished_at TIMESTAMPTZ,
+    status TEXT NOT NULL CHECK(status IN ('RUNNING','PASS','FAIL','PARTIAL')),
+    invocation_id TEXT,
+    artifact_path TEXT
+);
+ALTER TABLE recon.legacy_batches ADD COLUMN IF NOT EXISTS ingest_run_id TEXT;
+CREATE TABLE IF NOT EXISTS recon.runs (
+    run_id TEXT PRIMARY KEY,
+    requested_reports TEXT[] NOT NULL,
+    snapshot JSONB NOT NULL,
+    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
+    finished_at TIMESTAMPTZ,
+    status TEXT NOT NULL CHECK(status IN ('RUNNING','PASS','WARN','FAIL','SKIP','INCOMPLETE')),
+    eligible_for_cutover BOOLEAN NOT NULL DEFAULT false
+);
+
+-- Only a full-scope run can qualify. Partial invocations never get combined.
 CREATE OR REPLACE VIEW recon.v_daily_summary AS
+WITH latest AS (
+    SELECT DISTINCT ON ((coalesce(finished_at,started_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
+        *, (coalesce(finished_at,started_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS run_date
+    FROM recon.runs
+    WHERE cardinality(requested_reports)=7 AND requested_reports @> ARRAY['daily_revenue','customer_ltv','customer_segments','product_sales','cumulative_revenue','top_products_by_category','category_monthly_revenue']::text[]
+    ORDER BY (coalesce(finished_at,started_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
+        coalesce(finished_at,started_at) DESC, run_id DESC
+)
 SELECT
-    run_date,
-    count(*)                                   AS reports,
-    count(*) FILTER (WHERE status = 'PASS')    AS pass_count,
-    count(*) FILTER (WHERE status = 'WARN')    AS warn_count,
-    count(*) FILTER (WHERE status = 'SKIP')    AS skip_count,
-    count(*) FILTER (WHERE status = 'FAIL')    AS fail_count,
-    sum(diff_rows)                             AS diff_rows,
-    (count(*) = 7 AND bool_and(status = 'PASS') AND sum(diff_rows) = 0) AS green
-FROM recon.v_daily_status
-GROUP BY run_date;
+    l.run_date,
+    count(s.report) AS reports,
+    count(*) FILTER(WHERE s.status='PASS') AS pass_count,
+    count(*) FILTER(WHERE s.status='WARN') AS warn_count,
+    count(*) FILTER(WHERE s.status='SKIP') AS skip_count,
+    count(*) FILTER(WHERE s.status='FAIL') AS fail_count,
+    coalesce(sum(s.diff_rows),0) AS diff_rows,
+    (l.eligible_for_cutover AND l.status='PASS' AND l.finished_at IS NOT NULL
+        AND count(s.report)=7 AND bool_and(s.status='PASS') AND sum(s.diff_rows)=0) AS green
+FROM latest l LEFT JOIN recon.v_report_status s ON s.run_id=l.run_id
+GROUP BY l.run_date,l.eligible_for_cutover,l.status,l.finished_at;
 
--- Chuỗi ngày xanh liên tiếp (không bỏ trống ngày nào) kết thúc ở ngày chạy gần nhất.
--- Ngày gần nhất không xanh => green_days = 0.
 CREATE OR REPLACE VIEW recon.v_green_streak AS
 WITH green_days AS (
-    SELECT
-        run_date,
-        run_date - (row_number() OVER (ORDER BY run_date))::int AS island
-    FROM recon.v_daily_summary
-    WHERE green
-),
-latest AS (
+    SELECT run_date,run_date-(row_number() OVER(ORDER BY run_date))::int AS island
+    FROM recon.v_daily_summary WHERE green
+), latest AS (
     SELECT max(run_date) AS last_run_date FROM recon.v_daily_summary
 )
-SELECT
-    count(g.run_date)    AS green_days,
-    min(g.run_date)      AS since,
-    max(g.run_date)      AS until,
-    max(l.last_run_date) AS last_run_date
-FROM latest AS l
-LEFT JOIN green_days AS g
-    ON g.island = (SELECT island FROM green_days WHERE run_date = l.last_run_date);
+SELECT count(g.run_date) AS green_days, min(g.run_date) AS since,
+    max(g.run_date) AS until, max(l.last_run_date) AS last_run_date
+FROM latest l LEFT JOIN green_days g
+ON g.island=(SELECT island FROM green_days WHERE run_date=l.last_run_date)
+AND l.last_run_date BETWEEN (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date-1
+                       AND (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
+
+CREATE OR REPLACE VIEW etl.freshness_customers AS
+SELECT coalesce(max(loaded_at),TIMESTAMPTZ '1970-01-01 00:00:00+00') AS loaded_at
+FROM etl.ingest_log WHERE table_name='customers';
+
+CREATE OR REPLACE VIEW etl.freshness_products AS
+SELECT coalesce(max(loaded_at),TIMESTAMPTZ '1970-01-01 00:00:00+00') AS loaded_at
+FROM etl.ingest_log WHERE table_name='products';
+
+CREATE OR REPLACE VIEW etl.freshness_orders AS
+SELECT coalesce(max(loaded_at),TIMESTAMPTZ '1970-01-01 00:00:00+00') AS loaded_at
+FROM etl.ingest_log WHERE table_name='orders';
+
+CREATE OR REPLACE VIEW etl.freshness_order_items AS
+SELECT coalesce(max(loaded_at),TIMESTAMPTZ '1970-01-01 00:00:00+00') AS loaded_at
+FROM etl.ingest_log WHERE table_name='order_items';
 
 -- Metabase: database riêng cho metadata, và một user chỉ-đọc vào warehouse
 DO $$
diff --git a/warehouse/raw_restore.sql b/warehouse/raw_restore.sql
new file mode 100644
index 0000000..46aa162
--- /dev/null
+++ b/warehouse/raw_restore.sql
@@ -0,0 +1,124 @@
+-- Schema chứa dữ liệu thô tải từ hệ thống cũ, và schema chứa bảng điều khiển ETL
+CREATE SCHEMA IF NOT EXISTS raw;
+CREATE SCHEMA IF NOT EXISTS etl;
+
+-- Mỗi bảng nguồn một dòng: lần trước đã tải đến rowversion nào
+CREATE TABLE IF NOT EXISTS etl.watermarks (
+    table_name       TEXT        PRIMARY KEY,
+    last_rowversion  BIGINT      NOT NULL DEFAULT 0,
+    last_run_at      TIMESTAMPTZ
+);
+
+DO $$
+BEGIN
+    IF to_regclass('etl.ingest_log') IS NOT NULL THEN
+        IF EXISTS (
+            SELECT 1 FROM information_schema.columns
+            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
+              AND column_name = 'ingest_id'
+        ) THEN
+            ALTER TABLE etl.ingest_log RENAME COLUMN ingest_id TO id;
+        END IF;
+        IF EXISTS (
+            SELECT 1 FROM information_schema.columns
+            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
+              AND column_name = 'last_rowversion'
+        ) THEN
+            ALTER TABLE etl.ingest_log RENAME COLUMN last_rowversion TO from_rowversion;
+        END IF;
+        IF EXISTS (
+            SELECT 1 FROM information_schema.columns
+            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
+              AND column_name = 'upper_rowversion'
+        ) THEN
+            ALTER TABLE etl.ingest_log RENAME COLUMN upper_rowversion TO to_rowversion;
+        END IF;
+        IF EXISTS (
+            SELECT 1 FROM information_schema.columns
+            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
+              AND column_name = 'rows_loaded'
+        ) THEN
+            ALTER TABLE etl.ingest_log RENAME COLUMN rows_loaded TO row_count;
+        END IF;
+        IF EXISTS (
+            SELECT 1 FROM information_schema.columns
+            WHERE table_schema = 'etl' AND table_name = 'ingest_log'
+              AND column_name = 'logged_at'
+        ) THEN
+            ALTER TABLE etl.ingest_log RENAME COLUMN logged_at TO loaded_at;
+        END IF;
+        ALTER TABLE etl.ingest_log ADD COLUMN IF NOT EXISTS object_key TEXT;
+        ALTER TABLE etl.ingest_log ALTER COLUMN row_count TYPE INT USING row_count::INT;
+    END IF;
+END
+$$;
+
+CREATE TABLE IF NOT EXISTS etl.ingest_log (
+    id               BIGSERIAL   PRIMARY KEY,
+    run_id           TEXT        NOT NULL,
+    table_name       TEXT        NOT NULL,
+    from_rowversion  BIGINT      NOT NULL,
+    to_rowversion    BIGINT      NOT NULL,
+    row_count        INT         NOT NULL,
+    object_key       TEXT,
+    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
+);
+
+CREATE INDEX IF NOT EXISTS ix_ingest_log_run_table
+    ON etl.ingest_log (run_id, table_name);
+
+INSERT INTO etl.watermarks (table_name)
+VALUES ('customers'), ('products'), ('orders'), ('order_items')
+ON CONFLICT (table_name) DO NOTHING;
+
+-- Bảng thô: giữ nguyên dữ liệu nguồn. Giờ trong created_at là UTC (chưa gắn múi giờ)
+CREATE TABLE IF NOT EXISTS raw.customers (
+    customer_id  INT         PRIMARY KEY,
+    full_name    TEXT        NOT NULL,
+    email        TEXT        NOT NULL,
+    city         TEXT,
+    created_at   TIMESTAMP   NOT NULL,
+    row_ver      BIGINT      NOT NULL,
+    _loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
+    _deleted_at  TIMESTAMPTZ
+);
+ALTER TABLE raw.customers ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;
+
+-- Bảng thô cho sản phẩm. Giữ nguyên dữ liệu nguồn, chỉ có khóa chính (không có CHECK, không có khóa ngoại)
+CREATE TABLE IF NOT EXISTS raw.products (
+    product_id    INT           PRIMARY KEY,
+    product_name  TEXT          NOT NULL,
+    category      TEXT          NOT NULL,
+    unit_price    NUMERIC(12,2) NOT NULL,
+    is_active     BOOLEAN       NOT NULL,
+    created_at    TIMESTAMP     NOT NULL,
+    row_ver       BIGINT        NOT NULL,
+    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
+    _deleted_at   TIMESTAMPTZ
+);
+ALTER TABLE raw.products ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;
+
+CREATE TABLE IF NOT EXISTS raw.orders (
+    order_id      INT           PRIMARY KEY,
+    customer_id   INT           NOT NULL,
+    order_date    TIMESTAMP     NOT NULL,
+    status        TEXT          NOT NULL,
+    total_amount  NUMERIC(14,2) NOT NULL,
+    updated_at    TIMESTAMP     NOT NULL,
+    row_ver       BIGINT        NOT NULL,
+    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
+    _deleted_at   TIMESTAMPTZ
+);
+ALTER TABLE raw.orders ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;
+
+CREATE TABLE IF NOT EXISTS raw.order_items (
+    order_item_id INT           PRIMARY KEY,
+    order_id      INT           NOT NULL,
+    product_id    INT           NOT NULL,
+    quantity      INT           NOT NULL,
+    unit_price    NUMERIC(12,2) NOT NULL,
+    row_ver       BIGINT        NOT NULL,
+    _loaded_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
+    _deleted_at   TIMESTAMPTZ
+);
+ALTER TABLE raw.order_items ADD COLUMN IF NOT EXISTS _deleted_at TIMESTAMPTZ;
~~~~
<!-- END_PROJECT_PATCH -->
