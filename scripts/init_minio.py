"""Tạo bucket trên MinIO (tương thích S3). Chạy lại nhiều lần vẫn an toàn."""
import os
import sys
import time

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError
from dotenv import load_dotenv

load_dotenv()


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def wait_until_ready(s3, attempts: int = 30) -> None:
    for i in range(1, attempts + 1):
        try:
            s3.list_buckets()
            return
        except (EndpointConnectionError, ConnectionClosedError):
            print(f"Chờ MinIO sẵn sàng ({i}/{attempts})...")
            time.sleep(2)
    raise RuntimeError("MinIO chưa sẵn sàng sau thời gian chờ")


def ensure_bucket(s3, bucket: str) -> None:
    existing = {b["Name"] for b in s3.list_buckets()["Buckets"]}
    if bucket in existing:
        print(f"Bucket '{bucket}' đã tồn tại")
        return
    s3.create_bucket(Bucket=bucket)
    print(f"Đã tạo bucket '{bucket}'")


def main() -> int:
    try:
        bucket = os.environ["MINIO_BUCKET"]
        s3 = get_s3_client()
    except KeyError as exc:
        print(f"Thiếu biến môi trường {exc}, hãy kiểm tra file .env")
        return 1

    try:
        wait_until_ready(s3)
        ensure_bucket(s3, bucket)
    except (ClientError, RuntimeError) as exc:
        print(f"Lỗi MinIO: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())