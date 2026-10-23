from datetime import datetime, timedelta

import boto3
from botocore.config import Config

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("storage")
settings = get_settings()


class StorageService:
    def __init__(self):
        self.endpoint_url = settings.R2_ENDPOINT_URL or (
            f"https://{settings.CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"
            if settings.CLOUDFLARE_ACCOUNT_ID
            else None
        )
        self.bucket_name = settings.R2_BUCKET_NAME
        self.client = None

        if settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and self.endpoint_url:
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
                config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
            )

    def generate_upload_url(
        self,
        storage_path: str,
        mime_type: str,
        expires_in_seconds: int | None = None,
    ) -> tuple[str, datetime]:
        exp = expires_in_seconds or settings.R2_PRESIGNED_EXPIRATION_SECONDS
        expires_at = datetime.utcnow() + timedelta(seconds=exp)

        if not self.client:
            # Fallback for local mock/dev if R2 credentials are not set
            logger.info("Using mock presigned upload URL", storage_path=storage_path)
            mock_url = f"https://mock-r2.local/{self.bucket_name}/{storage_path}?token=mock-token"
            return mock_url, expires_at

        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": storage_path,
                    "ContentType": mime_type,
                },
                ExpiresIn=exp,
            )
            return url, expires_at
        except Exception as e:
            logger.error(
                "Failed to generate presigned upload URL", error=str(e), storage_path=storage_path
            )
            raise

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
        if not self.client:
            logger.info("Mock deleting storage path", storage_path=storage_path)
            return

        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_path)
            logger.info("File deleted from R2", storage_path=storage_path)
        except Exception as e:
            logger.error(
                "Failed to delete file from storage", error=str(e), storage_path=storage_path
            )


storage_service = StorageService()
