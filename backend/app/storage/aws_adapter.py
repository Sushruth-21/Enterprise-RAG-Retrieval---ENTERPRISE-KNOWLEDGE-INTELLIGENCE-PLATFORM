"""
AWS Storage & Architecture Adapter for Enterprise Knowledge Intelligence Platform.
Adheres to the AWS Well-Architected Framework (Reliability, Security, Performance).

Features:
- Amazon S3 storage integration for raw and processed documents.
- Automatic SSE-S3 encryption for data at rest.
- Presigned URL generation for secure zero-egress document access.
- Support for IAM Roles (ECS task roles, EKS IRSA, EC2 instance profiles).
- Transparent offline/local fallback when AWS credentials or S3 bucket are unconfigured.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("aws_adapter")


class AWSStorageAdapter:
    _instance: Optional[AWSStorageAdapter] = None

    def __init__(self) -> None:
        self.bucket_name: Optional[str] = (
            os.getenv("S3_BUCKET_NAME")
            or os.getenv("AWS_S3_BUCKET")
            or os.getenv("AWS_BUCKET")
        )
        self.region: str = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.kms_key_id: Optional[str] = os.getenv("AWS_KMS_KEY_ID")
        self._s3_client = None

        if self.bucket_name:
            try:
                import boto3
                from botocore.config import Config

                config = Config(
                    region_name=self.region,
                    retries={"max_attempts": 3, "mode": "adaptive"},
                )
                self._s3_client = boto3.client("s3", config=config)
                logger.info(f"AWS S3 storage adapter initialized for bucket '{self.bucket_name}' in '{self.region}'.")
            except Exception as exc:
                logger.warning(f"AWS S3 client initialization failed ({exc}); operating in local fallback mode.")
                self._s3_client = None
        else:
            logger.info("No AWS S3 bucket configured (S3_BUCKET_NAME env var not set); using local storage.")

    @classmethod
    def get_instance(cls) -> AWSStorageAdapter:
        if cls._instance is None:
            cls._instance = AWSStorageAdapter()
        return cls._instance

    @property
    def is_s3_enabled(self) -> bool:
        return bool(self.bucket_name and self._s3_client)

    def upload_document(
        self,
        file_bytes: bytes,
        s3_key: str,
        content_type: str = "application/pdf",
        metadata: Optional[dict] = None,
    ) -> Tuple[bool, str]:
        """
        Upload file to Amazon S3 with Server-Side Encryption.
        Returns (success: bool, location_uri_or_key: str).
        """
        if not self.is_s3_enabled:
            return False, ""

        try:
            extra_args = {
                "ContentType": content_type,
                "ServerSideEncryption": "aws:kms" if self.kms_key_id else "AES256",
            }
            if self.kms_key_id:
                extra_args["SSEKMSKeyId"] = self.kms_key_id
            if metadata:
                extra_args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}

            self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_bytes,
                **extra_args,
            )
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Successfully archived document to {s3_uri}")
            return True, s3_uri
        except Exception as exc:
            logger.error(f"Failed to upload to S3 ({exc}); preserving local copy.", exc_info=True)
            return False, ""

    def generate_presigned_url(self, s3_key: str, expiry_seconds: int = 3600) -> Optional[str]:
        """Generate a secure, time-limited presigned URL for document inspection."""
        if not self.is_s3_enabled:
            return None
        try:
            url = self._s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiry_seconds,
            )
            return url
        except Exception as exc:
            logger.error(f"Error generating S3 presigned URL: {exc}")
            return None

    def delete_document(self, s3_key: str) -> bool:
        if not self.is_s3_enabled:
            return False
        try:
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as exc:
            logger.warning(f"Error deleting object from S3: {exc}")
            return False

