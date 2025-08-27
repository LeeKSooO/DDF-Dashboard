"""
캐시 유틸리티 (현재는 메모리 캐시, 나중에 Redis로 확장 가능)
"""

from typing import Any, Optional, Dict
import hashlib
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# 메모리 기반 간단한 캐시 (개발용)
_memory_cache: Dict[str, Dict[str, Any]] = {}


def generate_cache_key(prefix: str, **kwargs) -> str:
    """캐시 키 생성"""
    # 파라미터들을 정렬하여 일관된 키 생성
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, sort_keys=True, default=str)
    hash_str = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"{prefix}:{hash_str}"


def set_cache(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """캐시 설정"""
    try:
        expire_time = datetime.now() + timedelta(seconds=ttl_seconds)
        _memory_cache[key] = {
            "value": value,
            "expire_time": expire_time
        }
        logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
    except Exception as e:
        logger.error(f"Cache set error: {e}")


def get_cache(key: str) -> Optional[Any]:
    """캐시 조회"""
    try:
        if key in _memory_cache:
            cache_data = _memory_cache[key]
            
            # 만료 시간 체크
            if datetime.now() > cache_data["expire_time"]:
                del _memory_cache[key]
                logger.debug(f"Cache expired: {key}")
                return None
            
            logger.debug(f"Cache hit: {key}")
            return cache_data["value"]
        
        logger.debug(f"Cache miss: {key}")
        return None
    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None


def delete_cache(key: str) -> None:
    """캐시 삭제"""
    try:
        if key in _memory_cache:
            del _memory_cache[key]
            logger.debug(f"Cache deleted: {key}")
    except Exception as e:
        logger.error(f"Cache delete error: {e}")


def clear_cache(prefix: Optional[str] = None) -> None:
    """캐시 전체 또는 특정 prefix 삭제"""
    try:
        if prefix:
            keys_to_delete = [k for k in _memory_cache.keys() if k.startswith(f"{prefix}:")]
            for key in keys_to_delete:
                del _memory_cache[key]
            logger.info(f"Cache cleared for prefix: {prefix}")
        else:
            _memory_cache.clear()
            logger.info("All cache cleared")
    except Exception as e:
        logger.error(f"Cache clear error: {e}")


def cache_stats() -> Dict[str, Any]:
    """캐시 통계"""
    try:
        active_keys = 0
        expired_keys = 0
        now = datetime.now()
        
        for cache_data in _memory_cache.values():
            if now > cache_data["expire_time"]:
                expired_keys += 1
            else:
                active_keys += 1
        
        return {
            "total_keys": len(_memory_cache),
            "active_keys": active_keys, 
            "expired_keys": expired_keys,
            "memory_usage_mb": len(str(_memory_cache)) / 1024 / 1024
        }
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return {"error": str(e)}


def cleanup_expired_cache() -> int:
    """만료된 캐시 정리"""
    try:
        now = datetime.now()
        expired_keys = []
        
        for key, cache_data in _memory_cache.items():
            if now > cache_data["expire_time"]:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _memory_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")
        return 0


# 데코레이터 방식 캐싱 (나중에 사용)
def cached(ttl_seconds: int = 300, prefix: str = "default"):
    """캐싱 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 함수명과 파라미터로 캐시 키 생성
            cache_key = generate_cache_key(
                f"{prefix}:{func.__name__}",
                args=args,
                kwargs=kwargs
            )
            
            # 캐시 조회
            cached_result = get_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행 및 캐싱
            result = func(*args, **kwargs)
            set_cache(cache_key, result, ttl_seconds)
            
            return result
        return wrapper
    return decorator