"""Đọc một file Parquet trên MinIO và in vài dòng để kiểm tra."""
import io
import os
import sys

import pyarrow.parquet as pq

from init_minio import get_s3_client


def main() -> int:
    if len(sys.argv) != 2:
        print("Cách dùng: python scripts/peek_parquet.py <đường-dẫn-trong-bucket>")
        return 1

    key = sys.argv[1]
    body = get_s3_client().get_object(Bucket=os.environ["MINIO_BUCKET"], Key=key)["Body"].read()
    table = pq.read_table(io.BytesIO(body))

    print(f"{table.num_rows} dòng")
    print(table.schema)
    for row in table.slice(0, 3).to_pylist():
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())