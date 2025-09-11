import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import json
from typing import Tuple, Optional
from .config import get_settings

settings = get_settings()

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4")
        )
        self.bucket_name = settings.s3_bucket_name
        self.public_read = settings.s3_public_read
        self.presign_expire_secs = settings.presign_expire_secs

    def upload_json(self, key: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Upload JSON data to S3. Returns (success, error_message)"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data).encode("utf-8"),
                ContentType="application/json",
                **({"ACL": "public-read"} if self.public_read else {})
            )
            return True, None
        except ClientError as e:
            return False, str(e)

    def upload_png(self, key: str, png_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """Upload PNG data to S3. Returns (success, error_message)"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=png_bytes,
                ContentType="image/png",
                **({"ACL": "public-read"} if self.public_read else {})
            )
            return True, None
        except ClientError as e:
            return False, str(e)

    def get_url(self, key: str) -> str:
        """Get URL for accessing the object"""
        if self.public_read:
            # Public URL
            return f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
        else:
            # Presigned URL
            try:
                return self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=self.presign_expire_secs,
                )
            except ClientError:
                return ""

    def delete_object(self, key: str) -> Tuple[bool, Optional[str]]:
        """Delete object from S3. Returns (success, error_message)"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True, None
        except ClientError as e:
            return False, str(e)

# Global instance
s3_service = S3Service()