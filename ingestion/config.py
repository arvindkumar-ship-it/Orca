"""ORCA — GENERALIZE of ingestion/config.py. Adds incois_pfz_base_url,
mosdac_base_url/api_key + two SourceConfig entries per ORCA_SCHEMA_PATCH.md.
Rest copied verbatim (dotenv load, default_factory rationale comment)."""
import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceConfig:
    name: str
    poll_interval_seconds: int
    timeout_seconds: int
    max_retries: int
    backoff_base_seconds: float
    enabled: bool = True


@dataclass(frozen=True)
class IngestionSettings:
    # default_factory (not a bare os.getenv default) so .env values loaded
    # above are actually picked up at instantiation time, not import time.
    incois_base_url: str = field(default_factory=lambda: os.getenv("INCOIS_BASE_URL", ""))
    incois_api_key: str = field(default_factory=lambda: os.getenv("INCOIS_API_KEY", ""))
    incois_pfz_base_url: str = field(default_factory=lambda: os.getenv("INCOIS_PFZ_BASE_URL", ""))

    sachet_cap_feed_url: str = field(default_factory=lambda: os.getenv("SACHET_CAP_FEED_URL", ""))
    sachet_api_key: str = field(default_factory=lambda: os.getenv("SACHET_API_KEY", ""))

    mosdac_base_url: str = field(default_factory=lambda: os.getenv("MOSDAC_BASE_URL", ""))
    mosdac_api_key: str = field(default_factory=lambda: os.getenv("MOSDAC_API_KEY", ""))

    raw_storage_backend: str = field(default_factory=lambda: os.getenv("RAW_STORAGE_BACKEND", "local"))
    raw_storage_local_path: str = field(default_factory=lambda: os.getenv("RAW_STORAGE_LOCAL_PATH", "/var/data/raw_ingest"))
    raw_storage_s3_bucket: str = field(default_factory=lambda: os.getenv("RAW_STORAGE_S3_BUCKET", ""))
    raw_storage_s3_prefix: str = field(default_factory=lambda: os.getenv("RAW_STORAGE_S3_PREFIX", "raw-ingest"))

    ops_alert_webhook_url: str = field(default_factory=lambda: os.getenv("OPS_ALERT_WEBHOOK_URL", ""))
    ops_alert_min_consecutive_failures: int = field(default_factory=lambda: int(os.getenv("OPS_ALERT_MIN_FAILURES", "3")))

    sources: dict = field(default_factory=lambda: {
        "incois": SourceConfig(name="incois", poll_interval_seconds=int(os.getenv("INCOIS_POLL_SECONDS", "900")),
                                timeout_seconds=20, max_retries=4, backoff_base_seconds=2.0),
        "sachet": SourceConfig(name="sachet", poll_interval_seconds=int(os.getenv("SACHET_POLL_SECONDS", "120")),
                                timeout_seconds=15, max_retries=5, backoff_base_seconds=1.5),
        "manual_admin": SourceConfig(name="manual_admin", poll_interval_seconds=0,
                                      timeout_seconds=5, max_retries=1, backoff_base_seconds=0.0),
        "incois_pfz": SourceConfig(name="incois_pfz", poll_interval_seconds=int(os.getenv("INCOIS_PFZ_POLL_SECONDS", "21600")),
                                    timeout_seconds=20, max_retries=4, backoff_base_seconds=2.0),
        "mosdac_bhuvan": SourceConfig(name="mosdac_bhuvan", poll_interval_seconds=int(os.getenv("MOSDAC_POLL_SECONDS", "10800")),
                                       timeout_seconds=30, max_retries=3, backoff_base_seconds=2.5),
    })


settings = IngestionSettings()
