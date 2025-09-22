import boto3
import random
import string
import os
import datetime
import json
import asyncio
import concurrent.futures
import time
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from typing import List, Dict, Any, Tuple, Optional
from models import AWSKey
from fastapi import UploadFile
from io import BytesIO
from PIL import Image
import io

class OptimizedAWSService:
    def __init__(self):
        self.bucket_limit = 100  # AWS default bucket limit per account
        # Thread pool for parallel AWS operations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
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

    def optimize_image(self, image_bytes: bytes, max_size: tuple = (1920, 1080), quality: int = 85) -> bytes:
        """Optimize image size and quality for faster uploads"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            # Resize if too large
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                print(f"Image resized from {img.size} to max {max_size}")
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                print(f"Image converted from {img.mode} to RGB")
            
            # Save with optimization
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            optimized_bytes = output.getvalue()
            
            print(f"Image optimized: {len(image_bytes)} -> {len(optimized_bytes)} bytes ({((len(image_bytes) - len(optimized_bytes)) / len(image_bytes) * 100):.1f}% reduction)")
            return optimized_bytes
            
        except Exception as e:
            print(f"Image optimization failed: {e}")
            return image_bytes

    def _prepare_image_data(self, image_file: Optional[UploadFile], image_content: Optional[bytes] = None) -> Tuple[Optional[bytes], str, str]:
        """Prepare uploaded image for S3 upload with optimization"""
        if image_file is None and image_content is None:
            print("DEBUG: No image file provided")
            return None, '', 'application/octet-stream'
        
        try:
            # Use provided content or read from file
            if image_content is not None:
                image_bytes = image_content
                filename = getattr(image_file, 'filename', 'image.jpg') if image_file else 'image.jpg'
            else:
                image_bytes = image_file.file.read()
                filename = image_file.filename
            
            print(f"DEBUG: Original image size: {len(image_bytes)} bytes")
            
            # Optimize the image
            optimized_bytes = self.optimize_image(image_bytes)
            
            # Determine file extension and content type
            file_ext = 'jpg'  # Always save as JPEG after optimization
            content_type = 'image/jpeg'
            
            print(f"DEBUG: Prepared optimized image: {len(optimized_bytes)} bytes, ext: {file_ext}, content_type: {content_type}")
            return optimized_bytes, file_ext, content_type
            
        except Exception as e:
            print(f"ERROR: Failed to prepare image data: {str(e)}")
            return None, '', 'application/octet-stream'

    async def create_buckets_for_user_parallel(self, user_keys: List[AWSKey], region: str, num_buckets: int, 
                                             image_file: Optional[UploadFile] = None, image_content: Optional[bytes] = None) -> Dict[str, Any]:
        """Create buckets for a user using parallel processing"""
        start_time = time.time()
        
        results = {
            "region": region,
            "num_buckets_requested": num_buckets,
            "keys_results": [],
            "total_buckets_created": 0,
            "total_urls_generated": 0,
            "creation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "processing_time": "0.00s"
        }

        # Prepare uploaded image once for reuse across all buckets
        image_bytes, file_ext, content_type = self._prepare_image_data(image_file, image_content)
        
        if image_bytes is None:
            print("WARNING: No valid image provided - no URLs will be generated")
        else:
            print(f"DEBUG: Successfully prepared image data: {len(image_bytes)} bytes, ext: {file_ext}, content_type: {content_type}")

        # Process all keys in parallel
        tasks = []
        for aws_key in user_keys:
            task = self._process_key_buckets_async(aws_key, region, num_buckets, image_bytes, file_ext, content_type)
            tasks.append(task)
        
        # Execute all key processing in parallel
        print(f"DEBUG: Starting parallel processing of {len(user_keys)} keys")
        key_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(key_results):
            if isinstance(result, Exception):
                error_result = {
                    "key_name": user_keys[i].name,
                    "buckets_created": 0,
                    "urls": [],
                    "errors": [f"Key processing failed: {str(result)}"]
                }
                results["keys_results"].append(error_result)
            else:
                results["keys_results"].append(result)
                results["total_buckets_created"] += result["buckets_created"]
                results["total_urls_generated"] += len(result["urls"])

        processing_time = time.time() - start_time
        results["processing_time"] = f"{processing_time:.2f}s"
        print(f"DEBUG: Parallel processing completed in {processing_time:.2f} seconds")
        
        return results

    async def _process_key_buckets_async(self, aws_key: AWSKey, region: str, num_buckets: int, 
                                       image_bytes: Optional[bytes], file_ext: str, content_type: str) -> Dict[str, Any]:
        """Process bucket creation for a single AWS key asynchronously"""
        key_result = {
            "key_name": aws_key.name,
            "buckets_created": 0,
            "urls": [],
            "errors": []
        }

        try:
            print(f"DEBUG: Processing key {aws_key.name} for {num_buckets} buckets")
            
            # Check bucket limits first (run in thread pool)
            loop = asyncio.get_event_loop()
            bucket_info = await loop.run_in_executor(
                self.executor, 
                self._get_bucket_count_sync, 
                aws_key, region
            )
            
            if not bucket_info["success"]:
                key_result["errors"].append(f"Failed to check bucket limits: {bucket_info.get('error', 'Unknown error')}")
                return key_result

            if bucket_info["remaining"] < num_buckets:
                key_result["errors"].append(f"Cannot create {num_buckets} buckets, only {bucket_info['remaining']} remaining")
                return key_result

            # Create buckets in parallel batches (AWS rate limiting consideration)
            batch_size = 3  # Create 3 buckets at a time to respect rate limits
            for i in range(0, num_buckets, batch_size):
                batch_end = min(i + batch_size, num_buckets)
                batch_tasks = []
                
                for j in range(i, batch_end):
                    task = self._create_single_bucket_async(aws_key, region, image_bytes, file_ext, content_type)
                    batch_tasks.append(task)
                
                # Process batch in parallel
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        key_result["errors"].append(f"Bucket creation failed: {str(result)}")
                    else:
                        key_result["buckets_created"] += 1
                        key_result["urls"].extend(result.get("urls", []))
                
                # Small delay between batches to respect AWS rate limits
                if batch_end < num_buckets:
                    await asyncio.sleep(0.5)

        except Exception as key_error:
            key_result["errors"].append(f"Failed to process key: {str(key_error)}")

        print(f"DEBUG: Key {aws_key.name} completed: {key_result['buckets_created']} buckets, {len(key_result['urls'])} URLs")
        return key_result

    async def _create_single_bucket_async(self, aws_key: AWSKey, region: str, image_bytes: Optional[bytes], 
                                        file_ext: str, content_type: str) -> Dict[str, Any]:
        """Create a single bucket asynchronously"""
        loop = asyncio.get_event_loop()
        
        # Run bucket creation in thread pool to avoid blocking
        result = await loop.run_in_executor(
            self.executor,
            self._create_bucket_sync,
            aws_key, region, image_bytes, file_ext, content_type
        )
        
        return result

    def _create_bucket_sync(self, aws_key: AWSKey, region: str, image_bytes: Optional[bytes], 
                          file_ext: str, content_type: str) -> Dict[str, Any]:
        """Synchronous bucket creation (runs in thread pool)"""
        urls = []
        
        try:
            # Generate bucket name
            bucket_name = self._generate_random_name(prefix='bucket')
            print(f"DEBUG: Creating bucket {bucket_name} for key {aws_key.name}")
            
            # Create S3 client
            s3 = self._create_s3_client(aws_key, region)
            
            # Create and configure bucket
            self._create_and_configure_bucket(s3, bucket_name, region)
            
            # Upload image and HTML in parallel if image provided
            if image_bytes:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as upload_executor:
                    # Submit both uploads simultaneously
                    image_future = upload_executor.submit(
                        self._upload_image_to_bucket, s3, bucket_name, region, image_bytes, file_ext, content_type
                    )
                    html_future = upload_executor.submit(
                        self._upload_html_file, s3, bucket_name, region
                    )
                    
                    # Get results
                    image_url = image_future.result(timeout=30)  # 30 second timeout
                    html_url = html_future.result(timeout=30)
                    
                    if image_url:
                        urls.append({"type": "image", "url": image_url})
                        print(f"DEBUG: Image uploaded successfully to {bucket_name}")
                    
                    if html_url:
                        urls.append({"type": "html", "url": html_url})
                        print(f"DEBUG: HTML uploaded successfully to {bucket_name}")
            
            return {"urls": urls}
            
        except Exception as e:
            print(f"ERROR: Failed to create bucket: {str(e)}")
            raise Exception(f"Failed to create bucket: {str(e)}")

    def _get_bucket_count_sync(self, aws_key: AWSKey, region: str) -> Dict[str, Any]:
        """Synchronous bucket count check (for thread pool execution)"""
        try:
            s3 = self._create_s3_client(aws_key, region)
            response = s3.list_buckets()
            bucket_count = len(response['Buckets'])
            
            return {
                "success": True,
                "count": bucket_count,
                "limit": self.bucket_limit,
                "remaining": self.bucket_limit - bucket_count
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "limit": self.bucket_limit,
                "remaining": 0
            }

    def _create_and_configure_bucket(self, s3, bucket_name: str, region: str):
        """Create bucket and configure public access settings"""
        try:
            print(f"DEBUG: Creating bucket {bucket_name} in region {region}")
            
            # Create bucket with proper region handling
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            # Configure public access settings
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': False,
                    'IgnorePublicAcls': False,
                    'BlockPublicPolicy': False,
                    'RestrictPublicBuckets': False
                }
            )
            
            # Set bucket policy for public read access
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
            
            print(f"DEBUG: Successfully configured bucket {bucket_name}")
            
        except Exception as e:
            print(f"ERROR: Failed to create/configure bucket {bucket_name}: {str(e)}")
            raise

    def _upload_image_to_bucket(self, s3, bucket_name: str, region: str, image_bytes: bytes, file_ext: str, content_type: str) -> Optional[str]:
        """Upload image to S3 bucket"""
        try:
            object_key = f"image.{file_ext}"
            
            s3.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=image_bytes,
                ContentType=content_type,
                ACL='public-read'
            )
            
            image_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"
            print(f"DEBUG: Image uploaded to {image_url}")
            return image_url
            
        except Exception as e:
            print(f"ERROR: Failed to upload image to {bucket_name}: {str(e)}")
            return None

    def _upload_html_file(self, s3, bucket_name: str, region: str) -> Optional[str]:
        """Upload HTML display file to S3 bucket"""
        try:
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Display - {bucket_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 800px;
            width: 100%;
        }}
        h1 {{
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
        }}
        .image-container {{
            margin: 30px 0;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
        }}
        .info {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }}
        .bucket-name {{
            font-family: monospace;
            background: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            font-size: 1.1em;
            color: #495057;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖼️ Image Display</h1>
        <div class="image-container">
            <img src="image.jpg" alt="Uploaded Image" />
        </div>
        <div class="info">
            <h3>S3 Bucket Information</h3>
            <div class="bucket-name">{bucket_name}</div>
            <p>Region: {region}</p>
            <p>Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>"""
            
            s3.put_object(
                Bucket=bucket_name,
                Key='index.html',
                Body=html_content.encode('utf-8'),
                ContentType='text/html',
                ACL='public-read'
            )
            
            html_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/index.html"
            print(f"DEBUG: HTML file uploaded to {html_url}")
            return html_url
            
        except Exception as e:
            print(f"ERROR: Failed to upload HTML file to {bucket_name}: {str(e)}")
            return None
