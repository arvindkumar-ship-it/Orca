"""
Module 3 — Data Ingestion : Raw payload storage (step 6)

Every raw payload is stored verbatim in object storage before/alongside the
normalized DB write, so a bad normalization run can always be replayed
against the untouched source data. Swappable backend: local filesystem for
dev, S3-compatible for prod (matches Module 30's "object storage" infra line).
"""
from __future__ import annotations

import abc
import json
import logging
import os
from datetime import datetime

from .config import settings
from .schemas import RawIngestRecord

logger = logging.getLogger("ingestion.raw_storage")


class RawStorageBackend(abc.ABC):
    @abc.abstractmethod
    def put(self, key: str, payload: dict) -> str:
        """Store payload, return a locator string (path or S3 URI)."""
        raise NotImplementedError


class LocalRawStorage(RawStorageBackend):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def put(self, key: str, payload: dict) -> str:
        path = os.path.join(self.base_path, f"{key}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, default=str)
        return path


class S3RawStorage(RawStorageBackend):
    def __init__(self, bucket: str, prefix: str):
        import boto3  # local import so boto3 isn't a hard dependency in dev
        self._client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix

    def put(self, key: str, payload: dict) -> str:
        s3_key = f"{self.prefix}/{key}.json"
        self._client.put_object(
            Bucket=self.bucket,
            Key=s3_key,
            Body=json.dumps(payload, default=str).encode("utf-8"),
            ContentType="application/json",
        )
        return f"s3://{self.bucket}/{s3_key}"


def get_raw_storage() -> RawStorageBackend:
    if settings.raw_storage_backend == "s3":
        return S3RawStorage(settings.raw_storage_s3_bucket, settings.raw_storage_s3_prefix)
    return LocalRawStorage(settings.raw_storage_local_path)


def store_raw_payload(record: RawIngestRecord) -> str:
    backend = get_raw_storage()
    day = record.ingest_time.strftime("%Y/%m/%d")
    key = f"{record.source.value}/{day}/{record.source_id.replace(':', '_')}"
    locator = backend.put(key, record.raw_json)
    logger.debug("raw_storage.stored source=%s key=%s locator=%s", record.source.value, key, locator)
    return locator
