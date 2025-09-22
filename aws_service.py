import boto3
import random
import string
import os
import datetime
import json
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

    def _prepare_image_data(self, image_file: Optional[UploadFile], image_content: Optional[bytes] = None) -> Tuple[Optional[bytes], str, str]:
        """Prepare uploaded image for S3 upload"""
        if image_file is None:
            print("DEBUG: No image file provided")
            return None, '', 'application/octet-stream'
        
        # Use provided image content if available, otherwise read from file
        image_bytes = None
        if image_content is not None:
            image_bytes = image_content
            print(f"DEBUG: Using provided image content: {len(image_bytes)} bytes")
        else:
            # Read image into memory
            try:
                # Ensure we're at the beginning of the file
                image_file.file.seek(0)
                image_bytes = image_file.file.read()
                print(f"DEBUG: Read {len(image_bytes)} bytes from uploaded file")
            except Exception as e:
                print(f"DEBUG: Error reading image file: {str(e)}")
                return None, '', 'application/octet-stream'
        
        if not image_bytes:
            print("DEBUG: Image file is empty after reading")
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

    def get_comprehensive_key_stats(self, aws_key: AWSKey, region: str = 'us-east-1') -> Dict[str, Any]:
        """Get comprehensive statistics for an AWS key including bucket info and permissions"""
        stats = {
            "key_id": aws_key.id,
            "key_name": aws_key.name,
            "access_key": aws_key.access_key,
            "status": aws_key.status,
            "last_checked": aws_key.last_checked,
            "bucket_limit": self.bucket_limit,
            "bucket_count": None,
            "buckets_remaining": None,
            "can_create_buckets": False,
            "can_list_buckets": False,
            "permissions_error": None,
            "connection_error": None,
            "last_stats_check": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            s3 = self._create_s3_client(aws_key, region)
            
            # Test 1: Can list buckets?
            try:
                response = s3.list_buckets()
                stats["can_list_buckets"] = True
                bucket_count = len(response.get('Buckets', []))
                stats["bucket_count"] = bucket_count
                stats["buckets_remaining"] = self.bucket_limit - bucket_count
                
                # Get bucket names for additional info
                bucket_names = [bucket['Name'] for bucket in response.get('Buckets', [])]
                stats["bucket_names"] = bucket_names[:5]  # Show first 5 bucket names
                if len(bucket_names) > 5:
                    stats["more_buckets"] = len(bucket_names) - 5
                    
            except Exception as list_error:
                stats["can_list_buckets"] = False
                stats["permissions_error"] = f"Cannot list buckets: {str(list_error)}"
            
            # Test 2: Can create buckets? (only if we can list them)
            if stats["can_list_buckets"] and stats["buckets_remaining"] > 0:
                test_bucket_name = f"test-validation-{random.randint(100000, 999999)}"
                try:
                    s3.create_bucket(Bucket=test_bucket_name)
                    s3.delete_bucket(Bucket=test_bucket_name)
                    stats["can_create_buckets"] = True
                except Exception as create_error:
                    stats["can_create_buckets"] = False
                    stats["permissions_error"] = f"Cannot create buckets: {str(create_error)}"
            elif stats["buckets_remaining"] == 0:
                stats["can_create_buckets"] = False
                stats["permissions_error"] = "Bucket limit reached"
                
        except Exception as connection_error:
            stats["connection_error"] = str(connection_error)
            stats["can_list_buckets"] = False
            stats["can_create_buckets"] = False
            
        return stats

    def create_buckets_for_user(self, user_keys: List[AWSKey], region: str, num_buckets: int, image_file: Optional[UploadFile] = None, image_content: Optional[bytes] = None) -> Dict[str, Any]:
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
        image_bytes, file_ext, content_type = self._prepare_image_data(image_file, image_content)
        
        if image_bytes is None:
            print("WARNING: No valid image provided - no URLs will be generated")
        else:
            print(f"DEBUG: Successfully prepared image data: {len(image_bytes)} bytes, ext: {file_ext}, content_type: {content_type}")

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
                        print(f"DEBUG: Uploading image to bucket {bucket_name}")
                        print(f"DEBUG: Image bytes length: {len(image_bytes)}")
                        print(f"DEBUG: File extension: {file_ext}")
                        print(f"DEBUG: Content type: {content_type}")
                        
                        image_url = self._upload_image_to_bucket(s3, bucket_name, region, image_bytes, file_ext, content_type)
                        if image_url:
                            print(f"DEBUG: Successfully uploaded image, URL: {image_url}")
                            key_result["urls"].append({"type": "image", "url": image_url})
                            
                            # Also upload the index.html file from directory
                            html_url = self._upload_html_file(s3, bucket_name, region)
                            if html_url:
                                print(f"DEBUG: Successfully uploaded HTML file, URL: {html_url}")
                                key_result["urls"].append({"type": "html", "url": html_url})
                            else:
                                print(f"WARNING: Failed to upload HTML file for bucket {bucket_name}")
                        else:
                            print(f"ERROR: Failed to upload image to bucket {bucket_name}")
                            key_result["errors"].append(f"Failed to upload image to bucket {bucket_name}")
                    else:
                        print(f"WARNING: No image bytes available for bucket {bucket_name}")
                        key_result["errors"].append("No image data provided for upload")
                    
                    key_result["buckets_created"] += 1
                    
                except Exception as bucket_error:
                    key_result["errors"].append(f"Failed to create bucket {i+1}: {str(bucket_error)}")

        except Exception as key_error:
            key_result["errors"].append(f"Failed to initialize AWS client: {str(key_error)}")

        return key_result

    def _create_and_configure_bucket(self, s3, bucket_name: str, region: str):
        """Create bucket and configure public access settings"""
        try:
            print(f"DEBUG: Creating bucket {bucket_name} in region {region}")
            
            # Create bucket
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            print(f"DEBUG: Bucket {bucket_name} created successfully")

            # Configure public access - Allow public read access for objects
            try:
                s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False,  # Allow public policies
                        'RestrictPublicBuckets': False  # Allow public bucket access
                    }
                )
                print(f"DEBUG: Public access block configured for {bucket_name}")
            except Exception as e:
                print(f"WARNING: Failed to configure public access block for {bucket_name}: {str(e)}")

            # Configure bucket ownership
            try:
                s3.put_bucket_ownership_controls(
                    Bucket=bucket_name,
                    OwnershipControls={
                        'Rules': [{'ObjectOwnership': 'BucketOwnerPreferred'}]
                    }
                )
                print(f"DEBUG: Bucket ownership configured for {bucket_name}")
            except Exception as e:
                print(f"WARNING: Failed to configure bucket ownership for {bucket_name}: {str(e)}")
            
            # Add bucket policy to allow public read access
            try:
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicReadGetObject",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{bucket_name}/*"
                        }
                    ]
                }
                
                s3.put_bucket_policy(
                    Bucket=bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                print(f"DEBUG: Bucket policy configured for {bucket_name}")
            except Exception as e:
                print(f"WARNING: Failed to configure bucket policy for {bucket_name}: {str(e)}")
                print(f"WARNING: URLs may not be publicly accessible")
                
        except Exception as e:
            print(f"ERROR: Failed to create/configure bucket {bucket_name}: {str(e)}")
            raise

    def _upload_image_to_bucket(self, s3, bucket_name: str, region: str, 
                              image_bytes: bytes, file_ext: str, content_type: str) -> Optional[str]:
        """Upload image to S3 bucket and return public URL"""
        try:
            object_key = self._generate_random_name(length=30) + file_ext
            print(f"DEBUG: Attempting to upload image to bucket {bucket_name}")
            print(f"DEBUG: Object key: {object_key}")
            print(f"DEBUG: Content type: {content_type}")
            print(f"DEBUG: Image size: {len(image_bytes)} bytes")
            
            # Try uploading with public-read ACL
            try:
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
                print(f"DEBUG: Successfully uploaded with public-read ACL")
            except Exception as acl_error:
                print(f"DEBUG: Failed with public-read ACL: {str(acl_error)}")
                # Try without ACL (bucket policy should handle public access)
                s3.upload_fileobj(
                    BytesIO(image_bytes),
                    bucket_name,
                    object_key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'CacheControl': 'no-cache, no-store, must-revalidate'
                    }
                )
                print(f"DEBUG: Successfully uploaded without ACL")
            
            url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"
            print(f"DEBUG: Generated URL: {url}")
            return url
            
        except Exception as e:
            print(f"ERROR: Failed to upload image to {bucket_name}: {str(e)}")
            print(f"ERROR: Exception type: {type(e).__name__}")
            import traceback
            print(f"ERROR: Full traceback: {traceback.format_exc()}")
            return None

    def _upload_html_file(self, s3, bucket_name: str, region: str) -> Optional[str]:
        """Upload the index.html file from the project directory"""
        try:
            html_key = self._generate_random_name(length=30) + ".html"
            html_file_path = "index.html"
            
            print(f"DEBUG: Uploading HTML file {html_file_path} as {html_key} to bucket {bucket_name}")
            
            # Check if index.html exists
            if not os.path.exists(html_file_path):
                print(f"ERROR: HTML file {html_file_path} not found in project directory")
                return None
            
            # Read the HTML file content
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            print(f"DEBUG: Read {len(html_content)} characters from {html_file_path}")
            
            # Upload HTML file
            try:
                s3.upload_fileobj(
                    BytesIO(html_content.encode('utf-8')),
                    bucket_name,
                    html_key,
                    ExtraArgs={
                        'ACL': 'public-read',
                        'ContentType': 'text/html',
                        'CacheControl': 'no-cache, no-store, must-revalidate'
                    }
                )
                print(f"DEBUG: Successfully uploaded HTML with public-read ACL")
            except Exception as acl_error:
                print(f"DEBUG: Failed with public-read ACL: {str(acl_error)}")
                # Try without ACL (bucket policy should handle public access)
                s3.upload_fileobj(
                    BytesIO(html_content.encode('utf-8')),
                    bucket_name,
                    html_key,
                    ExtraArgs={
                        'ContentType': 'text/html',
                        'CacheControl': 'no-cache, no-store, must-revalidate'
                    }
                )
                print(f"DEBUG: Successfully uploaded HTML without ACL")
            
            html_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{html_key}"
            print(f"DEBUG: Generated HTML URL: {html_url}")
            return html_url
            
        except Exception as e:
            print(f"ERROR: Failed to upload HTML file to {bucket_name}: {str(e)}")
            import traceback
            print(f"ERROR: Full traceback: {traceback.format_exc()}")
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
