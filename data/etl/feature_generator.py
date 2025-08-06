# etl/feature_generator.py
# MST-GCN용 Feature Generator (Log+Z-score 정규화 적용)

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import numpy as np
import logging
from datetime import datetime, timedelta
import os
import gc
from typing import Dict, List, Tuple, Optional

# psutil을 선택적으로 import (없어도 동작하도록)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MST_GCN_FeatureGenerator:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        
        # 실제 데이터 기반 정규화 상수 (Log+Z-score)
        self.LOG_MEAN = 0.153  # 전체 데이터 LN(boarding_count+1) 평균
        self.LOG_STDDEV = 0.456  # 전체 데이터 LN(boarding_count+1) 표준편차
        
        # 배차간격 정규화 상수 (Log+Z-score)
        self.INTERVAL_LOG_MEAN = 4.9986   # LN(interval) 평균
        self.INTERVAL_LOG_STDDEV = 0.7142  # LN(interval) 표준편차
        
    def connect_db(self):
        """DB 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def close_db(self):
        """DB 연결 종료"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def _normalize_log_boarding_count(self, boarding_count) -> float:
        """Log+Z-score 정규화: (LN(count+1) - μ) / σ
        
        Args:
            boarding_count: 승차 승객 수 (int, float, Decimal 모두 지원)
            
        Returns:
            정규화된 로그 승차 수 (Z-score)
        """
        # Decimal 타입을 float로 변환
        boarding_count = float(boarding_count) if boarding_count is not None else 0
        log_boarding = np.log(boarding_count + 1)
        normalized = (log_boarding - self.LOG_MEAN) / self.LOG_STDDEV
        return round(float(normalized), 4)
    
    def _normalize_interval(self, interval) -> float:
        """Log+Z-score 정규화: (LN(interval) - μ_log) / σ_log
        
        Args:
            interval: 배차간격 (분, int/float/Decimal 모두 지원)
            
        Returns:
            정규화된 배차간격 (Z-score)
        """
        # Decimal 타입을 float로 변환, 0 이하 값 방지
        interval = float(interval) if interval is not None else 1440
        interval = max(1, interval)  # 최소 1분으로 설정 (log(0) 방지)
        log_interval = np.log(interval)
        normalized = (log_interval - self.INTERVAL_LOG_MEAN) / self.INTERVAL_LOG_STDDEV
        return round(float(normalized), 4)
    
    def _correct_interval(self, interval: Optional[int]) -> int:
        """배차간격 보정 함수
        
        Args:
            interval: 원본 배차간격 (분 단위)
            
        Returns:
            보정된 배차간격
        """
        if interval is None or interval == 0:
            return 1440  # 하루 1회 운행으로 가정
        elif interval < 0:
            return abs(interval)
        else:
            return interval
    
    def _get_applicable_interval(self, weekday_interval: int, saturday_interval: int, 
                                sunday_interval: int, day_of_week: int) -> int:
        """해당 요일에 적용될 배차간격 결정
        
        Args:
            weekday_interval: 평일 배차간격
            saturday_interval: 토요일 배차간격
            sunday_interval: 일요일 배차간격
            day_of_week: 요일 (0=월요일, 6=일요일)
            
        Returns:
            적용될 배차간격
        """
        if day_of_week == 6:  # 일요일
            return self._correct_interval(sunday_interval)
        elif day_of_week == 5:  # 토요일
            return self._correct_interval(saturday_interval)
        else:  # 평일 (월-금)
            return self._correct_interval(weekday_interval)
    
    def _get_service_availability(self, is_operational: bool, is_in_service_hours: bool) -> int:
        """서비스 가용성 상태 계산
        
        Args:
            is_operational: 운행 여부
            is_in_service_hours: 서비스 시간 내 여부
            
        Returns:
            0=비운행, 1=운행날+시간외, 2=운행날+시간내
        """
        if not is_operational:
            return 0  # 비운행
        elif is_operational and not is_in_service_hours:
            return 1  # 운행날+시간외
        else:
            return 2  # 운행날+시간내
    
    def _is_rest_day(self, is_weekend: bool, is_holiday: bool) -> bool:
        """휴식일 판정 (주말 + 공휴일 통합)
        
        Args:
            is_weekend: 주말 여부
            is_holiday: 공휴일 여부
            
        Returns:
            휴식일 여부
        """
        return is_weekend or is_holiday
    
    def _calculate_drt_probability(self, boarding_count, applicable_interval,
                                  hour_of_day, is_weekend, is_holiday,
                                  service_availability) -> float:
        """DRT 확률 계산 (Log+Z-score 기반)
        
        Args:
            boarding_count: 승차 승객 수 (Decimal 지원)
            applicable_interval: 적용 배차간격 (Decimal 지원)
            hour_of_day: 시간 (0-23)
            is_weekend: 주말 여부
            is_holiday: 공휴일 여부
            service_availability: 서비스 가용성
            
        Returns:
            DRT 확률 [0, 1]
        """
        # Decimal 타입을 float로 안전하게 변환
        boarding_count = float(boarding_count) if boarding_count is not None else 0
        applicable_interval = float(applicable_interval) if applicable_interval is not None else 1440
        applicable_interval = max(1, applicable_interval)  # log(0) 방지
        
        # 1. Log+Z-score 정규화된 수요 팩터
        log_boarding = np.log(boarding_count + 1)
        norm_log_boarding = (log_boarding - self.LOG_MEAN) / self.LOG_STDDEV
        
        # 수요가 많을수록 DRT 필요도 감소 (역함수)
        demand_factor = max(0.05, 1.0 - (norm_log_boarding + 0.3355) / 10.691)
        
        # 2. Log+Z-score 정규화된 배차간격 팩터
        log_interval = np.log(applicable_interval)
        norm_interval = (log_interval - self.INTERVAL_LOG_MEAN) / self.INTERVAL_LOG_STDDEV
        interval_factor = 0.05 + (1 / (1 + np.exp(-norm_interval))) * 0.90
        
        # 3. 서비스 가용성별 보정
        if service_availability == 0:  # 비운행날
            interval_factor *= 1.5
        elif service_availability == 1:  # 운행날+시간외
            interval_factor *= 1.2
        
        # 4. 시간대 보정
        if (7 <= hour_of_day <= 9) or (17 <= hour_of_day <= 19):
            time_factor = 1.0  # 피크시간
        elif 10 <= hour_of_day <= 16:
            time_factor = 0.8  # 주간
        elif 20 <= hour_of_day <= 22:
            time_factor = 0.6  # 저녁
        else:
            time_factor = 0.4  # 야간/새벽
        
        # 5. 휴일 보정
        rest_day_factor = 1.2 if (is_weekend or is_holiday) else 1.0
        
        # 최종 확률 계산
        base_prob = interval_factor * 0.5 + demand_factor * 0.3 + time_factor * 0.2
        final_prob = base_prob * rest_day_factor
        
        return round(float(max(0.0, min(1.0, final_prob))), 4)
    
    def _monitor_memory(self, stage: str) -> None:
        """메모리 사용량 모니터링 (psutil 없이도 동작)"""
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory usage at {stage}: {memory_mb:.2f} MB")
                
                if memory_mb > 1500:  # 1.5GB 초과시 경고
                    logger.warning(f"High memory usage detected: {memory_mb:.2f} MB")
                    gc.collect()
            except Exception:
                pass  # 메모리 모니터링 실패해도 메인 프로세스는 계속
        else:
            logger.info(f"Processing stage: {stage} (memory monitoring disabled - psutil not available)")
            # psutil 없이도 가비지 컬렉션은 수행
            gc.collect()
    
    def _precompute_route_stats(self, date_filter: str) -> None:
        """노선 통계 사전 계산으로 JOIN 성능 최적화"""
        logger.info("Pre-computing route statistics for performance optimization...")
        
        precompute_query = f"""
        DROP TABLE IF EXISTS temp_stop_route_stats;
        CREATE TEMP TABLE temp_stop_route_stats AS
        SELECT 
            rs.stop_id,
            COALESCE(ROUND(AVG(br.weekday_interval)), 1440) as avg_weekday_interval,
            COALESCE(ROUND(AVG(br.saturday_interval)), 1440) as avg_saturday_interval,
            COALESCE(ROUND(AVG(br.sunday_interval)), 1440) as avg_sunday_interval,
            COUNT(DISTINCT br.route_id) as route_count
        FROM route_stops rs
        LEFT JOIN bus_routes br ON rs.route_id = br.route_id
        GROUP BY rs.stop_id;
        
        CREATE INDEX idx_temp_stop_route_stats ON temp_stop_route_stats(stop_id);
        """
        
        self.cur.execute(precompute_query)
        logger.info("Route statistics pre-computation completed")
    
    def _process_data_chunk(self, chunk_data: List[Tuple], chunk_num: int, total_chunks: int) -> int:
        """데이터 청크 처리 및 배치 삽입"""
        if not chunk_data:
            return 0
            
        logger.info(f"Processing chunk {chunk_num}/{total_chunks} with {len(chunk_data)} records...")
        self._monitor_memory(f"chunk {chunk_num} start")
        
        # Feature 계산 및 배치 처리용 데이터 준비
        feature_batch = []
        
        for row in chunk_data:
            (stop_id, recorded_at, boarding_count, alighting_count, is_operational, 
             is_in_service_hours, is_weekend, is_holiday, hour_of_day, day_of_week,
             weekday_interval, saturday_interval, sunday_interval, route_count) = row
            
            # 1. 적용 배차간격 계산
            applicable_interval = self._get_applicable_interval(
                weekday_interval, saturday_interval, sunday_interval, int(day_of_week)
            )
            
            # 2. MST-GCN 입력 피처 계산
            normalized_log_boarding_count = self._normalize_log_boarding_count(boarding_count)
            service_availability = self._get_service_availability(is_operational, is_in_service_hours)
            is_rest_day = self._is_rest_day(is_weekend, is_holiday)
            normalized_interval = self._normalize_interval(applicable_interval)
            
            # 3. DRT 확률 계산
            drt_probability = self._calculate_drt_probability(
                boarding_count, applicable_interval, int(hour_of_day),
                is_weekend, is_holiday, service_availability
            )
            
            # 4. Feature 레코드 구성
            feature_record = (
                stop_id,
                recorded_at,
                normalized_log_boarding_count,
                service_availability,
                is_rest_day,
                normalized_interval,
                int(hour_of_day),
                int(day_of_week),
                is_weekend,
                is_holiday,
                is_in_service_hours,
                applicable_interval,
                route_count,
                drt_probability
            )
            
            feature_batch.append(feature_record)
        
        # 배치 삽입
        insert_query = """
        INSERT INTO drt_features_mstgcn (
            stop_id, recorded_at, normalized_log_boarding_count, service_availability,
            is_rest_day, normalized_interval, hour_of_day, day_of_week,
            is_weekend, is_holiday, is_in_service_hours, applicable_interval,
            route_count, drt_probability
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (stop_id, recorded_at) DO UPDATE SET
            normalized_log_boarding_count = EXCLUDED.normalized_log_boarding_count,
            service_availability = EXCLUDED.service_availability,
            is_rest_day = EXCLUDED.is_rest_day,
            normalized_interval = EXCLUDED.normalized_interval,
            drt_probability = EXCLUDED.drt_probability;
        """
        
        execute_batch(self.cur, insert_query, feature_batch, page_size=1000)
        self.conn.commit()
        
        # 메모리 정리
        processed_count = len(feature_batch)
        del feature_batch, chunk_data
        gc.collect()
        
        self._monitor_memory(f"chunk {chunk_num} completed")
        return processed_count
    
    def generate_features(self, start_date: Optional[str] = None, end_date: Optional[str] = None, 
                         chunk_size: int = 50000) -> None:
        """MST-GCN용 Feature 생성 및 DB 저장 (메모리 효율적 청크 처리)
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD 형식, 선택사항)
            end_date: 종료 날짜 (YYYY-MM-DD 형식, 선택사항)
            chunk_size: 청크 사이즈 (기본값: 50000)
        """
        logger.info("Starting MST-GCN feature generation process with chunked processing...")
        self._monitor_memory("process start")
        
        try:
            # 데이터 조회 쿼리 (정류장별 평균 배차간격 적용)
            date_filter = ""
            if start_date and end_date:
                date_filter = f"AND su.recorded_at >= '{start_date}' AND su.recorded_at <= '{end_date}'"
            
            # 노선 통계 사전 계산으로 성능 최적화
            self._precompute_route_stats(date_filter)
            
            # 최적화된 쿼리 (사전 계산된 통계 사용)
            base_query = f"""
            SELECT 
                su.stop_id,
                su.recorded_at,
                su.boarding_count,
                su.alighting_count,
                su.is_operational,
                su.is_in_service_hours,
                su.is_weekend,
                su.is_holiday,
                EXTRACT(hour FROM su.recorded_at) as hour_of_day,
                EXTRACT(dow FROM su.recorded_at) as day_of_week,
                
                -- 사전 계산된 노선 통계 사용
                COALESCE(srs.avg_weekday_interval, 1440) as weekday_interval,
                COALESCE(srs.avg_saturday_interval, 1440) as saturday_interval,
                COALESCE(srs.avg_sunday_interval, 1440) as sunday_interval,
                COALESCE(srs.route_count, 1) as route_count
                
            FROM stop_usage su
            LEFT JOIN temp_stop_route_stats srs ON su.stop_id = srs.stop_id
            WHERE 1=1 {date_filter}
            ORDER BY su.recorded_at DESC, su.stop_id
            """
            
            # 전체 레코드 수 확인
            count_query = f"""
            SELECT COUNT(*) 
            FROM stop_usage su
            LEFT JOIN temp_stop_route_stats srs ON su.stop_id = srs.stop_id
            WHERE 1=1 {date_filter}
            """
            
            logger.info("Counting total records...")
            self.cur.execute(count_query)
            total_records = self.cur.fetchone()[0]
            
            if total_records == 0:
                logger.warning("No data found for the specified criteria")
                return
                
            logger.info(f"Total records to process: {total_records:,}")
            total_chunks = (total_records + chunk_size - 1) // chunk_size
            logger.info(f"Processing in {total_chunks} chunks of {chunk_size:,} records each")
            
            # 청크별 처리
            offset = 0
            total_processed = 0
            
            for chunk_num in range(1, total_chunks + 1):
                chunk_query = f"{base_query} LIMIT {chunk_size} OFFSET {offset}"
                
                logger.info(f"Fetching chunk {chunk_num}/{total_chunks}...")
                self.cur.execute(chunk_query)
                chunk_data = self.cur.fetchall()
                
                if not chunk_data:
                    logger.info("No more data to process")
                    break
                
                # 청크 처리
                processed_count = self._process_data_chunk(chunk_data, chunk_num, total_chunks)
                total_processed += processed_count
                offset += chunk_size
                
                # 진행 상황 로깅
                progress = (total_processed / total_records) * 100
                logger.info(f"Progress: {total_processed:,}/{total_records:,} ({progress:.1f}%) completed")
            
            logger.info(f"Successfully generated and inserted {total_processed:,} MST-GCN features")
            
            # 샘플 데이터 출력
            self._print_sample_features()
            self._monitor_memory("process completed")
            
        except Exception as e:
            logger.error(f"Feature generation failed: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    
    def _print_sample_features(self, limit: int = 5) -> None:
        """생성된 피처 샘플 출력"""
        try:
            sample_query = """
            SELECT 
                stop_id,
                recorded_at,
                normalized_log_boarding_count,
                service_availability,
                is_rest_day,
                normalized_interval,
                drt_probability,
                hour_of_day,
                applicable_interval
            FROM drt_features_mstgcn 
            ORDER BY recorded_at DESC 
            LIMIT %s;
            """
            
            self.cur.execute(sample_query, (limit,))
            samples = self.cur.fetchall()
            
            logger.info("=== Generated Feature Samples ===")
            for i, sample in enumerate(samples, 1):
                (stop_id, recorded_at, norm_log_boarding, service_avail, is_rest_day,
                 norm_interval, drt_prob, hour_of_day, applicable_interval) = sample
                
                logger.info(f"Sample {i}:")
                logger.info(f"  Stop ID: {stop_id}")
                logger.info(f"  Time: {recorded_at}")
                logger.info(f"  Features: [norm_log_boarding={norm_log_boarding}, service_avail={service_avail}, is_rest_day={is_rest_day}, norm_interval={norm_interval}]")
                logger.info(f"  DRT Probability: {drt_prob}")
                logger.info(f"  Meta: hour={hour_of_day}, interval={applicable_interval}min")
                logger.info("---")
                
        except Exception as e:
            logger.error(f"Failed to print sample features: {e}")

def main():
    """메인 실행 함수"""
    # DB 설정 (환경변수 우선, 기본값은 localhost)
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # Feature Generator 실행
    generator = MST_GCN_FeatureGenerator(db_config)
    
    try:
        generator.connect_db()
        
        # 전체 데이터 기간 처리 (청크 사이즈: 50K)
        start_date = "2024-11-01"
        end_date = "2025-06-25"
        chunk_size = 50000  # 메모리 효율성을 위한 청크 사이즈
        
        generator.generate_features(start_date=start_date, end_date=end_date, chunk_size=chunk_size)
        
    except Exception as e:
        logger.error(f"Feature generation process failed: {e}")
    finally:
        generator.close_db()

if __name__ == "__main__":
    main()