import asyncio
import aiofiles
import concurrent.futures
from typing import List, Dict, Any
import time
from functools import lru_cache
import redis
from PIL import Image
import io

class PerformanceOptimizedAWSService:
    def __init__(self):
        self.bucket_limit = 100
        # Connection pooling for better performance
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        # Redis cache for bucket limits (optional)
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        except:
            self.redis_client = None
    
    @lru_cache(maxsize=100)
    def get_cached_bucket_info(self, access_key: str, region: str) -> Dict[str, Any]:
        """Cache bucket information for 5 minutes to avoid repeated API calls"""
        cache_key = f"bucket_info:{access_key}:{region}"
        
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            if cached:
                return eval(cached)  # In production, use json.loads
        
        # If not cached, get fresh data
        bucket_info = self._get_fresh_bucket_info(access_key, region)
        
        if self.redis_client:
            # Cache for 5 minutes
            self.redis_client.setex(cache_key, 300, str(bucket_info))
        
        return bucket_info
    
    def optimize_image(self, image_bytes: bytes, max_size: tuple = (1920, 1080), quality: int = 85) -> bytes:
        """Optimize image size and quality for faster uploads"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            # Resize if too large
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Save with optimization
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
        except Exception as e:
            print(f"Image optimization failed: {e}")
            return image_bytes
    
    async def create_buckets_parallel(self, user_keys: List, region: str, num_buckets: int, 
                                    image_bytes: bytes) -> Dict[str, Any]:
        """Create buckets in parallel for much faster processing"""
        start_time = time.time()
        
        # Optimize image once
        optimized_image = self.optimize_image(image_bytes)
        print(f"Image optimized: {len(image_bytes)} -> {len(optimized_image)} bytes")
        
        # Create tasks for parallel processing
        tasks = []
        for aws_key in user_keys:
            task = self.process_key_parallel(aws_key, region, num_buckets, optimized_image)
            tasks.append(task)
        
        # Execute all keys in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        total_buckets = 0
        total_urls = 0
        keys_results = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                keys_results.append({
                    "key_name": user_keys[i].name,
                    "buckets_created": 0,
                    "urls": [],
                    "errors": [f"Processing failed: {str(result)}"]
                })
            else:
                keys_results.append(result)
                total_buckets += result["buckets_created"]
                total_urls += len(result["urls"])
        
        processing_time = time.time() - start_time
        print(f"Parallel processing completed in {processing_time:.2f} seconds")
        
        return {
            "region": region,
            "num_buckets_requested": num_buckets,
            "keys_results": keys_results,
            "total_buckets_created": total_buckets,
            "total_urls_generated": total_urls,
            "processing_time": f"{processing_time:.2f}s",
            "creation_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    async def process_key_parallel(self, aws_key, region: str, num_buckets: int, 
                                 image_bytes: bytes) -> Dict[str, Any]:
        """Process a single key with parallel bucket creation"""
        key_result = {
            "key_name": aws_key.name,
            "buckets_created": 0,
            "urls": [],
            "errors": []
        }
        
        try:
            # Check bucket limits (cached)
            bucket_info = self.get_cached_bucket_info(aws_key.access_key, region)
            if not bucket_info["success"]:
                key_result["errors"].append(f"Failed to check bucket limits: {bucket_info.get('error')}")
                return key_result
            
            if bucket_info["remaining"] < num_buckets:
                key_result["errors"].append(f"Cannot create {num_buckets} buckets, only {bucket_info['remaining']} remaining")
                return key_result
            
            # Create buckets in parallel batches (AWS has rate limits)
            batch_size = 5  # Create 5 buckets at a time
            for i in range(0, num_buckets, batch_size):
                batch_end = min(i + batch_size, num_buckets)
                batch_tasks = []
                
                for j in range(i, batch_end):
                    task = self.create_single_bucket_async(aws_key, region, image_bytes)
                    batch_tasks.append(task)
                
                # Process batch
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        key_result["errors"].append(f"Bucket creation failed: {str(result)}")
                    else:
                        key_result["buckets_created"] += 1
                        key_result["urls"].extend(result["urls"])
                
                # Small delay between batches to respect rate limits
                if batch_end < num_buckets:
                    await asyncio.sleep(0.5)
        
        except Exception as e:
            key_result["errors"].append(f"Key processing failed: {str(e)}")
        
        return key_result
    
    async def create_single_bucket_async(self, aws_key, region: str, image_bytes: bytes) -> Dict[str, Any]:
        """Create a single bucket asynchronously"""
        loop = asyncio.get_event_loop()
        
        # Run AWS operations in thread pool to avoid blocking
        result = await loop.run_in_executor(
            self.executor,
            self._create_bucket_sync,
            aws_key, region, image_bytes
        )
        
        return result
    
    def _create_bucket_sync(self, aws_key, region: str, image_bytes: bytes) -> Dict[str, Any]:
        """Synchronous bucket creation (runs in thread pool)"""
        urls = []
        
        try:
            # Generate bucket name
            bucket_name = self._generate_random_name(prefix='bucket')
            
            # Create S3 client
            s3 = self._create_s3_client(aws_key, region)
            
            # Create and configure bucket
            self._create_and_configure_bucket(s3, bucket_name, region)
            
            # Upload image and HTML in parallel
            if image_bytes:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as upload_executor:
                    # Submit both uploads simultaneously
                    image_future = upload_executor.submit(
                        self._upload_image_to_bucket, s3, bucket_name, region, image_bytes, 'jpg', 'image/jpeg'
                    )
                    html_future = upload_executor.submit(
                        self._upload_html_file, s3, bucket_name, region
                    )
                    
                    # Get results
                    image_url = image_future.result()
                    html_url = html_future.result()
                    
                    if image_url:
                        urls.append({"type": "image", "url": image_url})
                    if html_url:
                        urls.append({"type": "html", "url": html_url})
            
            return {"urls": urls}
            
        except Exception as e:
            raise Exception(f"Failed to create bucket: {str(e)}")

# Additional optimizations for main.py
class DatabaseOptimizations:
    @staticmethod
    def get_user_keys_optimized(user_id: int, db):
        """Optimized query to get user keys with eager loading"""
        from sqlalchemy.orm import joinedload
        
        # Use joinedload to avoid N+1 queries
        user = db.query(User).options(
            joinedload(User.aws_keys)
        ).filter(User.id == user_id).first()
        
        return user.aws_keys if user else []
    
    @staticmethod
    def batch_update_key_status(key_updates: List[Dict], db):
        """Batch update key statuses instead of individual updates"""
        from sqlalchemy import update
        
        for update_data in key_updates:
            db.execute(
                update(AWSKey)
                .where(AWSKey.id == update_data['id'])
                .values(
                    status=update_data['status'],
                    last_checked=update_data['last_checked']
                )
            )
        db.commit()

# Frontend optimizations
class FrontendOptimizations:
    @staticmethod
    def add_loading_indicators():
        """JavaScript to show loading indicators during long operations"""
        return """
        function showLoadingSpinner(buttonId, message = 'Processing...') {
            const button = document.getElementById(buttonId);
            const originalText = button.innerHTML;
            button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
            button.disabled = true;
            
            return () => {
                button.innerHTML = originalText;
                button.disabled = false;
            };
        }
        
        function optimizeFormSubmission() {
            // Compress images before upload
            const imageInput = document.getElementById('image');
            if (imageInput) {
                imageInput.addEventListener('change', function(e) {
                    const file = e.target.files[0];
                    if (file && file.size > 1024 * 1024) { // > 1MB
                        compressImage(file, 0.8).then(compressedFile => {
                            // Replace with compressed version
                            const dt = new DataTransfer();
                            dt.items.add(compressedFile);
                            imageInput.files = dt.files;
                        });
                    }
                });
            }
        }
        
        async function compressImage(file, quality = 0.8) {
            return new Promise((resolve) => {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = () => {
                    // Resize if too large
                    const maxWidth = 1920;
                    const maxHeight = 1080;
                    let { width, height } = img;
                    
                    if (width > maxWidth || height > maxHeight) {
                        const ratio = Math.min(maxWidth / width, maxHeight / height);
                        width *= ratio;
                        height *= ratio;
                    }
                    
                    canvas.width = width;
                    canvas.height = height;
                    
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    canvas.toBlob(resolve, 'image/jpeg', quality);
                };
                
                img.src = URL.createObjectURL(file);
            });
        }
        """
