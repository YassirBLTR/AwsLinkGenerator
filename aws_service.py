import boto3
import random
import string
import os
import datetime
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from typing import List, Dict, Any, Tuple, Optional
from models import AWSKey
from fastapi import UploadFile
from io import BytesIO

class AWSService:
    def __init__(self):
        self.bucket_limit = 100  # AWS default bucket limit per account

    def _sanitize_credentials(self, access_key: str, secret_key: str) -> Tuple[str, str]:
        """Clean AWS credentials to prevent InvalidAccessKeyId errors"""
        clean_access = access_key.strip().upper() if access_key else access_key
        clean_secret = secret_key.strip() if secret_key else secret_key
        return clean_access, clean_secret

    def _create_s3_client(self, aws_key: AWSKey, region: str):
        """Create S3 client with sanitized credentials"""
        access_key, secret_key = self._sanitize_credentials(aws_key.access_key, aws_key.secret_key)
        return boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

    def _generate_random_name(self, length: int = 30, prefix: str = '') -> str:
        """Generate random name for buckets/objects"""
        if prefix:
            # For bucket names: format like 'prefix-random-random'
            parts = [prefix]
            for _ in range(2):
                parts.append(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
            return '-'.join(parts)
        else:
            # For object names: simple random string
            return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _prepare_image_data(self, image_file: Optional[UploadFile]) -> Tuple[Optional[bytes], str, str]:
        """Prepare uploaded image for S3 upload"""
        if image_file is None:
            return None, '', 'application/octet-stream'
        
        # Read image into memory
        try:
            image_file.file.seek(0)
        except Exception:
            pass
        
        image_bytes = image_file.file.read()
        if not image_bytes:
            return None, '', 'application/octet-stream'
        
        # Determine file extension and content type
        file_ext = ''
        content_type = image_file.content_type or 'application/octet-stream'
        
        if hasattr(image_file, 'filename') and image_file.filename:
            _, ext = os.path.splitext(image_file.filename.lower())
            file_ext = ext
            
            # Override content type based on extension for reliability
            if ext == '.png':
                content_type = 'image/png'
            elif ext in ('.jpg', '.jpeg', '.jpe'):
                content_type = 'image/jpeg'
            elif ext == '.gif':
                content_type = 'image/gif'
            elif ext == '.webp':
                content_type = 'image/webp'
        
        return image_bytes, file_ext, content_type

    def get_bucket_count(self, aws_key: AWSKey, region: str) -> Dict[str, Any]:
        """Get current bucket count for an AWS account"""
        try:
            s3 = self._create_s3_client(aws_key, region)
            response = s3.list_buckets()
            existing_count = len(response.get('Buckets', []))
            
            return {
                "key_name": aws_key.name,
                "existing": existing_count,
                "remaining": self.bucket_limit - existing_count,
                "limit": self.bucket_limit,
                "success": True
            }
        except Exception as e:
            return {
                "key_name": aws_key.name,
                "existing": None,
                "remaining": None,
                "limit": self.bucket_limit,
                "success": False,
                "error": str(e)
            }

    def create_buckets_for_user(self, user_keys: List[AWSKey], region: str, num_buckets: int, image_file: Optional[UploadFile] = None) -> Dict[str, Any]:
        """Create buckets for a user using their assigned AWS keys"""
        results = {
            "region": region,
            "num_buckets_requested": num_buckets,
            "keys_results": [],
            "total_buckets_created": 0,
            "total_urls_generated": 0,
            "creation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Prepare uploaded image once for reuse across all buckets
        image_bytes, file_ext, content_type = self._prepare_image_data(image_file)
        
        if image_bytes is None:
            print("WARNING: No valid image provided - no URLs will be generated")

        for aws_key in user_keys:
            key_result = self._process_key_buckets(aws_key, region, num_buckets, image_bytes, file_ext, content_type)
            results["keys_results"].append(key_result)
            results["total_buckets_created"] += key_result["buckets_created"]
            results["total_urls_generated"] += len(key_result["urls"])

        return results

    def _process_key_buckets(self, aws_key: AWSKey, region: str, num_buckets: int, 
                           image_bytes: Optional[bytes], file_ext: str, content_type: str) -> Dict[str, Any]:
        """Process bucket creation for a single AWS key"""
        key_result = {
            "key_name": aws_key.name,
            "buckets_created": 0,
            "urls": [],
            "errors": []
        }

        try:
            # Create S3 client
            s3 = self._create_s3_client(aws_key, region)

            # Check bucket limits
            bucket_info = self.get_bucket_count(aws_key, region)
            if not bucket_info["success"]:
                key_result["errors"].append(f"Failed to check bucket limits: {bucket_info.get('error', 'Unknown error')}")
                return key_result

            if bucket_info["remaining"] < num_buckets:
                key_result["errors"].append(f"Cannot create {num_buckets} buckets, only {bucket_info['remaining']} remaining")
                return key_result

            # Create buckets
            for i in range(num_buckets):
                try:
                    bucket_name = self._generate_random_name(prefix='bucket')
                    
                    # Create and configure bucket
                    self._create_and_configure_bucket(s3, bucket_name, region)
                    
                    # Upload image if provided
                    if image_bytes:
                        image_url = self._upload_image_to_bucket(s3, bucket_name, region, image_bytes, file_ext, content_type)
                        if image_url:
                            key_result["urls"].append({"type": "image", "url": image_url})
                    
                    key_result["buckets_created"] += 1
                    
                except Exception as bucket_error:
                    key_result["errors"].append(f"Failed to create bucket {i+1}: {str(bucket_error)}")

        except Exception as key_error:
            key_result["errors"].append(f"Failed to initialize AWS client: {str(key_error)}")

        return key_result

    def _create_and_configure_bucket(self, s3, bucket_name: str, region: str):
        """Create bucket and configure public access settings"""
        # Create bucket
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

        # Configure public access
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )

        s3.put_bucket_ownership_controls(
            Bucket=bucket_name,
            OwnershipControls={
                'Rules': [{'ObjectOwnership': 'BucketOwnerPreferred'}]
            }
        )

    def _upload_image_to_bucket(self, s3, bucket_name: str, region: str, 
                              image_bytes: bytes, file_ext: str, content_type: str) -> Optional[str]:
        """Upload image to S3 bucket and return public URL"""
        try:
            object_key = self._generate_random_name(length=30) + file_ext
            
            s3.upload_fileobj(
                BytesIO(image_bytes),
                bucket_name,
                object_key,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': content_type,
                    'CacheControl': 'no-cache, no-store, must-revalidate'
                }
            )
            
            return f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"
            
        except Exception as e:
            print(f"ERROR: Failed to upload image to {bucket_name}: {str(e)}")
            return None


    def validate_aws_key(self, access_key: str, secret_key: str) -> Tuple[str, str]:
        """Validate AWS credentials by testing S3 operations
        Returns: (status, message)
        Status can be: 'active', 'invalid', 'expired', 'no_permissions'
        """
        try:
            # Create S3 client with sanitized credentials
            clean_access, clean_secret = self._sanitize_credentials(access_key, secret_key)
            s3_client = boto3.client(
                's3',
                aws_access_key_id=clean_access,
                aws_secret_access_key=clean_secret,
                region_name='us-east-1'
            )
            
            # Test 1: List buckets (basic permission check)
            try:
                s3_client.list_buckets()
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_messages = {
                    'InvalidAccessKeyId': 'Invalid Access Key ID',
                    'SignatureDoesNotMatch': 'Invalid Secret Access Key',
                    'TokenRefreshRequired': 'Credentials have expired',
                    'AccessDenied': 'Access denied - insufficient permissions'
                }
                return 'invalid' if error_code != 'AccessDenied' else 'no_permissions', \
                       error_messages.get(error_code, f'AWS Error: {error_code}')
            
            # Test 2: Try to create and delete a test bucket
            test_bucket_name = f"test-validation-{random.randint(100000, 999999)}"
            try:
                s3_client.create_bucket(Bucket=test_bucket_name)
                s3_client.delete_bucket(Bucket=test_bucket_name)
                return 'active', 'Key is valid and has bucket creation permissions'
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'AccessDenied':
                    return 'no_permissions', 'Key valid but lacks bucket creation permissions'
                elif error_code == 'BucketAlreadyExists':
                    return 'active', 'Key is valid (bucket name collision during test)'
                else:
                    return 'no_permissions', f'Limited permissions: {error_code}'
                    
        except (NoCredentialsError, EndpointConnectionError) as e:
            return 'invalid', f'Connection error: {str(e)}'
        except Exception as e:
            return 'invalid', f'Validation error: {str(e)}'
