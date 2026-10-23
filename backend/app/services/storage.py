import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("storage")
settings = get_settings()


@dataclass(frozen=True)
class ObjectStat:
    """Server-side truth about an uploaded object (ISSUE-002)."""

    exists: bool
    size_bytes: int = 0
    content_type: str = ""
    etag: str = ""
    sha256: str = ""


class StorageService:
    # In-memory vault used ONLY when no R2/S3 credentials are configured
    # (local dev + CI). Objects are keyed by storage_path. This lets the
    # upload-completion verification flow run end-to-end without cloud creds
    # instead of silently trusting a mock URL (ISSUE-002).
    _MOCK_MAX_OBJECTS = 1000

    def __init__(self):
        self.endpoint_url = settings.R2_ENDPOINT_URL or (
            f"https://{settings.CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"
            if settings.CLOUDFLARE_ACCOUNT_ID
            else None
        )
        self.bucket_name = settings.R2_BUCKET_NAME
        self.client = None
        self._mock_objects: dict[str, bytes] = {}

        if settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and self.endpoint_url:
            is_local = any(h in self.endpoint_url for h in ("localhost", "127.0.0.1", "minio"))
            addressing_style = "path" if is_local else "virtual"
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto" if not is_local else "us-east-1",
                config=Config(signature_version="s3v4", s3={"addressing_style": addressing_style}),
            )

    @property
    def is_mock(self) -> bool:
        return self.client is None

    def generate_upload_url(
        self,
        storage_path: str,
        mime_type: str,
        expires_in_seconds: int | None = None,
        expected_size_bytes: int | None = None,
    ) -> tuple[str, datetime]:
        """Presign a PUT bound to the declared ContentType (and, on S3-
        compatible endpoints, Content-Length range) so client-declared
        metadata is at least partially enforced by storage itself (ISSUE-002).
        """
        exp = expires_in_seconds or settings.R2_PRESIGNED_EXPIRATION_SECONDS
        expires_at = datetime.now(UTC) + timedelta(seconds=exp)

        if not self.client:
            # Fallback for local mock/dev if R2 credentials are not set
            logger.info("Using mock presigned upload URL", storage_path=storage_path)
            mock_url = f"https://mock-r2.local/{self.bucket_name}/{storage_path}?token=mock-token"
            return mock_url, expires_at

        params: dict = {
            "Bucket": self.bucket_name,
            "Key": storage_path,
            "ContentType": mime_type,
        }

        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params=params,
                ExpiresIn=exp,
            )
            return url, expires_at
        except Exception as e:
            logger.error(
                "Failed to generate presigned upload URL", error=str(e), storage_path=storage_path
            )
            raise

    def head_object(self, storage_path: str) -> ObjectStat:
        """Return authoritative size/type for a stored object."""
        if not self.client:
            data = self._mock_objects.get(storage_path)
            if data is None:
                return ObjectStat(exists=False)
            return ObjectStat(
                exists=True,
                size_bytes=len(data),
                content_type="",  # mock vault does not track per-object type
                etag=hashlib.md5(data).hexdigest(),
                sha256=hashlib.sha256(data).hexdigest(),
            )

        try:
            resp = self.client.head_object(Bucket=self.bucket_name, Key=storage_path)
        except self.client.exceptions.ClientError as e:
            code = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if code == 404:
                return ObjectStat(exists=False)
            logger.error("HEAD object failed", error=str(e), storage_path=storage_path)
            raise
        return ObjectStat(
            exists=True,
            size_bytes=int(resp.get("ContentLength", 0)),
            content_type=(resp.get("ContentType") or "").lower(),
            etag=str(resp.get("ETag", "")).strip('"'),
        )

    def download_file(self, storage_path: str) -> bytes:
        """Fetch full object bytes for server-side validation/checksumming."""
        if not self.client:
            data = self._mock_objects.get(storage_path)
            if data is None:
                raise FileNotFoundError(f"Mock vault object not found: {storage_path}")
            return data

        resp = self.client.get_object(Bucket=self.bucket_name, Key=storage_path)
        return resp["Body"].read()

    def store_mock_object(self, storage_path: str, data: bytes) -> None:
        """Simulate the client's presigned PUT completing, in mock mode only.

        Tests/local dev use this to place real bytes into the in-memory vault
        so the upload-complete verification path exercises genuine checks.
        """
        if self.client is not None:
            raise RuntimeError("store_mock_object is only available when R2 creds are unset")
        if len(self._mock_objects) >= self._MOCK_MAX_OBJECTS:
            # Bound memory in long-running dev servers using mock mode.
            oldest = next(iter(self._mock_objects))
            del self._mock_objects[oldest]
        self._mock_objects[storage_path] = data

    def generate_download_url(
        self,
        storage_path: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        exp = expires_in_seconds or settings.R2_PRESIGNED_EXPIRATION_SECONDS

        if not self.client:
            return f"https://mock-r2.local/{self.bucket_name}/{storage_path}?token=mock-token"

        try:
            return self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": storage_path,
                },
                ExpiresIn=exp,
            )
        except Exception as e:
            logger.error(
                "Failed to generate presigned download URL", error=str(e), storage_path=storage_path
            )
            raise

    def delete_file(self, storage_path: str) -> None:
        """Delete an object from R2.

        ISSUE-005: previously failures were swallowed (log-only), which let
        erasure endpoints claim "permanently deleted" while files survived.
        Callers must handle the raised exception; local mock mode still no-ops.
        """
        if not self.client:
            self._mock_objects.pop(storage_path, None)
            logger.info("Mock deleting storage path", storage_path=storage_path)
            return

        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            self._mock_objects.pop(storage_path, None)  # harmless no-op in real mode
            logger.info("File deleted from R2", storage_path=storage_path)
        except Exception as e:
            logger.error(
                "Failed to delete file from storage", error=str(e), storage_path=storage_path
            )
            raise


storage_service = StorageService()
