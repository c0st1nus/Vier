"""S3/MinIO storage service for video file management."""

import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing video storage in S3/MinIO."""

    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = settings.S3_ENDPOINT if settings.S3_ENABLED else None
        self.bucket_name = settings.S3_BUCKET
        self.region = settings.S3_REGION
        self.use_ssl = settings.S3_USE_SSL
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.public_url = settings.S3_PUBLIC_URL
        self.signed_url_expiry = settings.S3_SIGNED_URL_EXPIRY

    async def initialize(self):
        """Initialize S3 bucket if it doesn't exist."""
        if not settings.S3_ENABLED:
            logger.info("S3 storage is disabled, using local storage")
            return

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                # Check if bucket exists
                try:
                    await s3.head_bucket(Bucket=self.bucket_name)
                    logger.info(f"S3 bucket '{self.bucket_name}' already exists")
                except ClientError as e:
                    error_code = e.response["Error"]["Code"]
                    if error_code == "404":
                        # Create bucket
                        await s3.create_bucket(Bucket=self.bucket_name)
                        logger.info(f"Created S3 bucket: {self.bucket_name}")

                        # Set bucket policy for public read on shared videos (optional)
                        # For now, we'll use signed URLs for all access
                    else:
                        raise

        except Exception as e:
            logger.error(f"Failed to initialize S3 storage: {e}")
            raise

    async def upload_file(
        self,
        file_path: Path,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_path: Path to local file
            object_key: S3 object key (path in bucket)
            content_type: MIME type of file
            metadata: Optional metadata dictionary

        Returns:
            S3 object key
        """
        if not settings.S3_ENABLED:
            logger.warning("S3 disabled, file remains local")
            return str(file_path)

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                if metadata:
                    extra_args["Metadata"] = metadata

                # Upload file
                with open(file_path, "rb") as f:
                    await s3.upload_fileobj(
                        f,
                        self.bucket_name,
                        object_key,
                        ExtraArgs=extra_args,
                    )

                logger.info(f"Uploaded file to S3: {object_key}")
                return object_key

        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    async def download_file(self, object_key: str, destination_path: Path) -> Path:
        """
        Download a file from S3.

        Args:
            object_key: S3 object key
            destination_path: Local destination path

        Returns:
            Path to downloaded file
        """
        if not settings.S3_ENABLED:
            logger.warning("S3 disabled, returning local path")
            return Path(object_key)

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                # Ensure parent directory exists
                destination_path.parent.mkdir(parents=True, exist_ok=True)

                # Download file
                with open(destination_path, "wb") as f:
                    await s3.download_fileobj(
                        self.bucket_name,
                        object_key,
                        f,
                    )

                logger.info(f"Downloaded file from S3: {object_key}")
                return destination_path

        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise

    async def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            object_key: S3 object key

        Returns:
            True if deleted successfully
        """
        if not settings.S3_ENABLED:
            logger.warning("S3 disabled, cannot delete")
            return False

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                await s3.delete_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                )

                logger.info(f"Deleted file from S3: {object_key}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False

    async def get_signed_url(
        self,
        object_key: str,
        expiry_seconds: Optional[int] = None,
        response_content_type: Optional[str] = None,
    ) -> str:
        """
        Generate a signed URL for temporary access to a file.

        Args:
            object_key: S3 object key
            expiry_seconds: URL expiry time in seconds (default: from config)
            response_content_type: Force content type in response

        Returns:
            Signed URL string
        """
        if not settings.S3_ENABLED:
            # Return local API endpoint
            return f"http://16.171.11.38:2135/api/video/file/{object_key}"

        try:
            expiry = expiry_seconds or self.signed_url_expiry

            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                params = {
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                }

                if response_content_type:
                    params["ResponseContentType"] = response_content_type

                url = await s3.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=expiry,
                )

                # If public URL is configured, replace endpoint
                if self.public_url:
                    parsed = urlparse(url)
                    public_parsed = urlparse(self.public_url)
                    url = url.replace(
                        f"{parsed.scheme}://{parsed.netloc}",
                        self.public_url.rstrip("/"),
                    )

                logger.debug(f"Generated signed URL for: {object_key}")
                return url

        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            raise

    async def get_public_url(self, object_key: str) -> str:
        """
        Get public URL for an object (if bucket has public access).

        Args:
            object_key: S3 object key

        Returns:
            Public URL string
        """
        if not settings.S3_ENABLED:
            return f"http://16.171.11.38:2135/api/video/file/{object_key}"

        if self.public_url:
            return f"{self.public_url.rstrip('/')}/{self.bucket_name}/{object_key}"

        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket_name}/{object_key}"

        # AWS S3 standard URL
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}"

    async def file_exists(self, object_key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            object_key: S3 object key

        Returns:
            True if file exists
        """
        if not settings.S3_ENABLED:
            return Path(object_key).exists()

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                await s3.head_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                )
                return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                return False
            logger.error(f"Error checking file existence: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    async def get_file_metadata(self, object_key: str) -> Optional[dict]:
        """
        Get metadata for a file in S3.

        Args:
            object_key: S3 object key

        Returns:
            Metadata dictionary or None
        """
        if not settings.S3_ENABLED:
            local_path = Path(object_key)
            if local_path.exists():
                return {
                    "size": local_path.stat().st_size,
                    "last_modified": local_path.stat().st_mtime,
                }
            return None

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                use_ssl=self.use_ssl,
            ) as s3:
                response = await s3.head_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                )

                return {
                    "size": response.get("ContentLength"),
                    "content_type": response.get("ContentType"),
                    "last_modified": response.get("LastModified"),
                    "etag": response.get("ETag"),
                    "metadata": response.get("Metadata", {}),
                }

        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None

    def get_object_key_for_task(self, task_id: str, filename: str) -> str:
        """
        Generate S3 object key for a task video.

        Args:
            task_id: Task identifier
            filename: Original filename

        Returns:
            S3 object key
        """
        # Organize by date for easier management
        from datetime import datetime

        date_prefix = datetime.utcnow().strftime("%Y/%m/%d")

        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")

        return f"videos/{date_prefix}/{task_id}_{safe_filename}"


# Global storage service instance
storage_service = StorageService()
