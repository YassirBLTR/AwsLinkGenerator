import redis
import json
import time
from typing import Dict, Any, Optional
from functools import wraps

class CacheService:
    def __init__(self, host='localhost', port=6379, db=0):
        try:
            self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self.enabled = True
            print("Redis cache connected successfully")
        except Exception as e:
            print(f"Redis not available, caching disabled: {e}")
            self.redis_client = None
            self.enabled = False
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data"""
        if not self.enabled:
            return None
        
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"Cache get error: {e}")
        
        return None
    
    def set(self, key: str, data: Dict[str, Any], ttl: int = 300) -> bool:
        """Set cached data with TTL (default 5 minutes)"""
        if not self.enabled:
            return False
        
        try:
            self.redis_client.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cached data"""
        if not self.enabled:
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    def get_bucket_stats(self, access_key: str, region: str) -> Optional[Dict[str, Any]]:
        """Get cached bucket statistics"""
        cache_key = f"bucket_stats:{access_key}:{region}"
        return self.get(cache_key)
    
    def set_bucket_stats(self, access_key: str, region: str, stats: Dict[str, Any], ttl: int = 300) -> bool:
        """Cache bucket statistics for 5 minutes"""
        cache_key = f"bucket_stats:{access_key}:{region}"
        return self.set(cache_key, stats, ttl)
    
    def invalidate_bucket_stats(self, access_key: str, region: str = None) -> bool:
        """Invalidate bucket statistics cache"""
        if region:
            cache_key = f"bucket_stats:{access_key}:{region}"
            return self.delete(cache_key)
        else:
            # Invalidate all regions for this access key
            try:
                if self.enabled:
                    pattern = f"bucket_stats:{access_key}:*"
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                return True
            except Exception as e:
                print(f"Cache invalidation error: {e}")
                return False

# Global cache instance
cache = CacheService()

def cached_bucket_stats(ttl: int = 300):
    """Decorator for caching bucket statistics"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, aws_key, region=None):
            # Try to get from cache first
            cached_stats = cache.get_bucket_stats(aws_key.access_key, region or 'default')
            if cached_stats:
                print(f"Cache hit for bucket stats: {aws_key.name}")
                return cached_stats
            
            # Not in cache, get fresh data
            print(f"Cache miss for bucket stats: {aws_key.name}")
            stats = func(self, aws_key, region)
            
            # Cache the result
            cache.set_bucket_stats(aws_key.access_key, region or 'default', stats, ttl)
            
            return stats
        return wrapper
    return decorator
