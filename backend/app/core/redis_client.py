"""
Redis 클라이언트 및 캐싱 유틸리티
월별 업데이트 데이터 특성에 최적화된 캐싱 전략
"""

import redis.asyncio as redis
from typing import Optional, Any, Dict, Union
import json
import logging
import hashlib
from datetime import datetime, timedelta, date
from functools import wraps
import inspect
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 클라이언트 (월별 데이터 특성 최적화)"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
    
    async def get_redis(self) -> redis.Redis:
        """Redis 연결 가져오기 (lazy loading)"""
        if self._redis is None:
            try:
                logger.info(f"Attempting to connect to Redis at: {self.redis_url}")
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1
                )
                # 연결 테스트
                await self._redis.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis = None
                raise
        return self._redis
    
    async def is_connected(self) -> bool:
        """Redis 연결 상태 확인"""
        try:
            if self._redis is None:
                # Redis 인스턴스가 없으면 연결 시도
                await self.get_redis()
            if self._redis:
                await self._redis.ping()
                return True
        except Exception as e:
            logger.debug(f"Redis connection check failed: {e}")
            pass
        return False
    
    async def get_cached(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        try:
            redis_client = await self.get_redis()
            data = await redis_client.get(key)
            
            if data:
                logger.info(f"Cache HIT: {key}")
                return json.loads(data)
            else:
                logger.info(f"Cache MISS: {key}")
                return None
                
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None
    
    async def set_cache(
        self, 
        key: str, 
        data: Any, 
        ttl: int = 3600,
        serialize: bool = True
    ) -> bool:
        """데이터를 캐시에 저장"""
        try:
            redis_client = await self.get_redis()
            
            # 데이터 직렬화
            if serialize:
                if hasattr(data, 'dict'):  # Pydantic model
                    serialized_data = json.dumps(data.dict())
                elif isinstance(data, dict):
                    serialized_data = json.dumps(data)
                else:
                    serialized_data = json.dumps(data, default=str)
            else:
                serialized_data = data
            
            # TTL과 함께 저장
            success = await redis_client.setex(key, ttl, serialized_data)
            
            if success:
                logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
                return True
            else:
                logger.warning(f"Cache SET failed: {key}")
                return False
                
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete_cache(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        try:
            redis_client = await self.get_redis()
            deleted = await redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key} (deleted: {deleted})")
            return deleted > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """패턴과 일치하는 모든 키 삭제"""
        try:
            redis_client = await self.get_redis()
            keys = await redis_client.keys(pattern)
            if keys:
                deleted = await redis_client.delete(*keys)
                logger.info(f"Cache INVALIDATE: {pattern} ({deleted} keys deleted)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate error for pattern {pattern}: {e}")
            return 0
    
    def calculate_ttl(self, analysis_month) -> int:
        """월별 데이터 특성에 따른 TTL 계산"""
        try:
            # date 객체 또는 문자열 처리
            if isinstance(analysis_month, date):
                analysis_date = datetime(analysis_month.year, analysis_month.month, 1)
            else:
                year, month = map(int, analysis_month.split('-'))
                analysis_date = datetime(year, month, 1)
            current_date = datetime.now()
            
            # 현재 월이면 24시간, 과거 월이면 30일
            if analysis_date.year == current_date.year and analysis_date.month == current_date.month:
                ttl = 24 * 60 * 60  # 24시간 (현재 진행 중인 월)
                logger.debug(f"Current month {analysis_month}: TTL = 24 hours")
            else:
                ttl = 30 * 24 * 60 * 60  # 30일 (완료된 과거 월)
                logger.debug(f"Past month {analysis_month}: TTL = 30 days")
                
            return ttl
            
        except Exception as e:
            logger.error(f"Error calculating TTL for {analysis_month}: {e}")
            return 3600  # 기본값: 1시간
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 조회"""
        try:
            redis_client = await self.get_redis()
            info = await redis_client.info()
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "expired_keys": info.get("expired_keys", 0),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# 전역 Redis 클라이언트 인스턴스
redis_client = RedisClient()


def generate_cache_key(
    service_name: str, 
    method_name: str, 
    args: tuple, 
    kwargs: dict
) -> str:
    """캐시 키 생성"""
    # 파라미터를 문자열로 변환
    params = []
    
    # args 처리
    for arg in args[1:]:  # self 제외
        if hasattr(arg, '__dict__'):  # 객체인 경우
            continue
        params.append(str(arg))
    
    # kwargs 처리  
    for key, value in sorted(kwargs.items()):
        if key in ['db']:  # DB 세션은 키에서 제외
            continue
        params.append(f"{key}={value}")
    
    # 파라미터 해시 생성
    param_str = "|".join(params)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
    
    return f"cache:{service_name}:{method_name}:{param_hash}"


def cache_result(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    use_month_ttl: bool = True
):
    """
    메서드 결과를 캐시하는 데코레이터
    
    Args:
        ttl: 캐시 TTL (초). None이면 자동 계산
        key_prefix: 캐시 키 접두사
        use_month_ttl: analysis_month 파라미터 기반 TTL 자동 계산 여부
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 서비스명과 메서드명 추출
            service_name = args[0].__class__.__name__.lower().replace('service', '')
            method_name = func.__name__
            
            # 캐시 키 생성
            if key_prefix:
                cache_key = f"{key_prefix}:{generate_cache_key(service_name, method_name, args, kwargs)}"
            else:
                cache_key = generate_cache_key(service_name, method_name, args, kwargs)
            
            # Redis 연결 확인
            try:
                is_connected = await redis_client.is_connected()
                if not is_connected:
                    logger.warning("Redis not available, executing without cache")
                    return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Redis connection check failed: {e}, executing without cache")
                return await func(*args, **kwargs)
            
            # 캐시에서 조회
            cached_result = await redis_client.get_cached(cache_key)
            if cached_result is not None:
                logger.info(f"Cache HIT for {method_name}: {cache_key}")
                
                # Pydantic 모델로 변환 (함수 return type annotation 확인)
                return_annotation = inspect.signature(func).return_annotation
                if return_annotation != inspect.Signature.empty:
                    try:
                        if hasattr(return_annotation, '__origin__'):  # Generic type인 경우 스킵
                            return cached_result
                        return return_annotation(**cached_result)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize cached data: {e}")
                        return cached_result
                
                return cached_result
            
            # 캐시 미스: 실제 함수 실행
            logger.info(f"Cache MISS for {method_name}: {cache_key}")
            result = await func(*args, **kwargs)
            
            # TTL 계산
            calculated_ttl = ttl
            if calculated_ttl is None and use_month_ttl:
                # analysis_month 파라미터에서 TTL 계산
                analysis_month = kwargs.get('analysis_month')
                if not analysis_month and len(args) > 2:
                    # 위치 인수에서 찾기 (보통 두 번째 파라미터)
                    try:
                        analysis_month = args[2]
                    except IndexError:
                        pass
                
                if analysis_month:
                    calculated_ttl = redis_client.calculate_ttl(analysis_month)
                else:
                    calculated_ttl = 3600  # 기본값
            
            if calculated_ttl is None:
                calculated_ttl = 3600  # 기본값
            
            # 결과 캐싱
            await redis_client.set_cache(cache_key, result, ttl=calculated_ttl)
            logger.info(f"Cache SET for {method_name}: {cache_key} (TTL: {calculated_ttl}s)")
            
            return result
        
        return wrapper
    return decorator


# ETL 프로세스에서 사용할 캐시 무효화 함수
async def invalidate_month_cache(analysis_month: str):
    """특정 월의 모든 캐시 무효화"""
    patterns = [
        f"cache:heatmap:*{analysis_month}*",
        f"cache:traffic:*{analysis_month}*"
    ]
    
    total_deleted = 0
    for pattern in patterns:
        deleted = await redis_client.invalidate_pattern(pattern)
        total_deleted += deleted
    
    logger.info(f"Invalidated {total_deleted} cache entries for month {analysis_month}")
    return total_deleted