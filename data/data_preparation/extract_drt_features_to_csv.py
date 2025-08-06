#!/usr/bin/env python3
"""
DRT Features 데이터베이스에서 CSV 파일 추출 스크립트
대용량 데이터를 배치 처리로 안전하게 추출
"""

import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys
from typing import List, Optional
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('drt_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DRTDataExtractor:
    def __init__(self, db_config: dict, output_dir: str = "data/processed"):
        self.db_config = db_config
        self.output_dir = output_dir
        self.essential_columns = [
            'stop_id', 'stop_name', 'recorded_at', 'latitude', 'longitude',
            'normalized_log_boarding_count', 'service_availability', 
            'is_rest_day', 'normalized_interval', 'drt_probability'
        ]
        
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
    
    def get_data_info(self) -> dict:
        """데이터 크기 및 기본 정보 조회 (2024-11-01 ~ 2025-06-25)"""
        query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT df.stop_id) as unique_stops,
            MIN(df.recorded_at) as min_date,
            MAX(df.recorded_at) as max_date,
            AVG(LENGTH(bs.stop_name)) as avg_name_length
        FROM drt_features_mstgcn df
        JOIN bus_stops bs ON df.stop_id = bs.stop_id
        WHERE bs.latitude IS NOT NULL 
        AND bs.longitude IS NOT NULL
        AND df.recorded_at >= '2024-11-01 00:00:00'
        AND df.recorded_at <= '2025-06-25 23:59:59'
        """
        
        try:
            with psycopg2.connect(**self.db_config) as conn:
                df = pd.read_sql(query, conn)
                info = df.iloc[0].to_dict()
                
                # 메모리 사용량 추정 (MB)
                estimated_memory = (info['total_records'] * len(self.essential_columns) * 20) / (1024**2)
                info['estimated_memory_mb'] = estimated_memory
                
                return info
        except Exception as e:
            logger.error(f"데이터 정보 조회 실패: {e}")
            raise
    
    def extract_batch(self, offset: int, batch_size: int) -> pd.DataFrame:
        """배치 단위로 데이터 추출 (2024-11-01 ~ 2025-06-25)"""
        query = """
        SELECT 
            df.stop_id,
            bs.stop_name,
            df.recorded_at,
            bs.latitude,
            bs.longitude,
            df.normalized_log_boarding_count,
            df.service_availability,
            df.is_rest_day,
            df.normalized_interval,
            df.drt_probability
        FROM drt_features_mstgcn df
        JOIN bus_stops bs ON df.stop_id = bs.stop_id
        WHERE bs.latitude IS NOT NULL 
        AND bs.longitude IS NOT NULL
        AND df.recorded_at >= '2024-11-01 00:00:00'
        AND df.recorded_at <= '2025-06-25 23:59:59'
        ORDER BY df.recorded_at, df.stop_id
        LIMIT %s OFFSET %s
        """
        
        try:
            with psycopg2.connect(**self.db_config) as conn:
                df = pd.read_sql(query, conn, params=[batch_size, offset])
                return df
        except Exception as e:
            logger.error(f"배치 추출 실패 (offset: {offset}, batch_size: {batch_size}): {e}")
            raise
    
    def extract_to_csv(self, batch_size: int = 50000, max_memory_mb: int = 500) -> str:
        """대용량 데이터를 배치 처리로 CSV 파일 생성"""
        
        logger.info("=== DRT Features CSV 추출 시작 ===")
        
        # 1. 데이터 정보 확인
        info = self.get_data_info()
        total_records = info['total_records']
        unique_stops = info['unique_stops']
        estimated_memory = info['estimated_memory_mb']
        
        logger.info(f"총 레코드 수: {total_records:,}")
        logger.info(f"유니크 정류장: {unique_stops:,}")
        logger.info(f"데이터 기간: {info['min_date']} ~ {info['max_date']}")
        logger.info(f"예상 메모리 사용량: {estimated_memory:.1f} MB")
        
        # 2. 배치 크기 조정
        if estimated_memory > max_memory_mb:
            adjusted_batch_size = min(batch_size, int(batch_size * max_memory_mb / estimated_memory))
            logger.warning(f"메모리 제한으로 배치 크기 조정: {batch_size} → {adjusted_batch_size}")
            batch_size = adjusted_batch_size
        
        # 3. 출력 파일 경로
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_dir, f"drt_features_{timestamp}.csv")
        
        # 4. 배치별 처리
        total_batches = (total_records + batch_size - 1) // batch_size
        processed_records = 0
        
        logger.info(f"배치 크기: {batch_size:,}")
        logger.info(f"총 배치 수: {total_batches}")
        logger.info(f"출력 파일: {output_file}")
        
        # 첫 번째 배치로 헤더 생성
        first_batch = True
        
        for batch_num in range(total_batches):
            offset = batch_num * batch_size
            
            logger.info(f"배치 {batch_num + 1}/{total_batches} 처리 중... (offset: {offset:,})")
            
            try:
                # 배치 데이터 추출
                batch_df = self.extract_batch(offset, batch_size)
                
                if batch_df.empty:
                    logger.warning(f"배치 {batch_num + 1}이 비어있음")
                    break
                
                # 🔄 시간순 정렬 추가 (recorded_at, stop_id 기준)
                batch_df = batch_df.sort_values(by=['recorded_at', 'stop_id'])
                logger.info(f"  → 배치 정렬 완료: {len(batch_df):,}개 레코드")
                
                # CSV 파일에 추가
                mode = 'w' if first_batch else 'a'
                header = first_batch
                
                batch_df.to_csv(output_file, mode=mode, header=header, index=False)
                
                processed_records += len(batch_df)
                first_batch = False
                
                logger.info(f"  → {len(batch_df):,}개 레코드 처리 완료 (누적: {processed_records:,})")
                
                # 메모리 정리
                del batch_df
                
            except Exception as e:
                logger.error(f"배치 {batch_num + 1} 처리 실패: {e}")
                raise
        
        # 5. 최종 검증
        logger.info("=== 추출 완료 ===")
        logger.info(f"총 처리된 레코드: {processed_records:,}")
        logger.info(f"출력 파일: {output_file}")
        
        # 파일 크기 확인
        file_size_mb = os.path.getsize(output_file) / (1024**2)
        logger.info(f"파일 크기: {file_size_mb:.1f} MB")
        
        return output_file
    
    def extract_sample(self, sample_size: int = 10000) -> str:
        """샘플 데이터 추출 (테스트용)"""
        logger.info(f"=== 샘플 데이터 추출 (크기: {sample_size:,}) ===")
        
        query = """
        SELECT 
            df.stop_id,
            bs.stop_name,
            df.recorded_at,
            bs.latitude,
            bs.longitude,
            df.normalized_log_boarding_count,
            df.service_availability,
            df.is_rest_day,
            df.normalized_interval,
            df.drt_probability
        FROM drt_features_mstgcn df
        JOIN bus_stops bs ON df.stop_id = bs.stop_id
        WHERE bs.latitude IS NOT NULL 
        AND bs.longitude IS NOT NULL
        ORDER BY RANDOM()
        LIMIT %s
        """
        
        try:
            with psycopg2.connect(**self.db_config) as conn:
                df = pd.read_sql(query, conn, params=[sample_size])
            
            # 출력 파일
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.output_dir, f"drt_features_sample_{timestamp}.csv")
            
            df.to_csv(output_file, index=False)
            
            logger.info(f"샘플 파일 생성: {output_file}")
            logger.info(f"레코드 수: {len(df):,}")
            logger.info(f"파일 크기: {os.path.getsize(output_file) / 1024:.1f} KB")
            
            return output_file
            
        except Exception as e:
            logger.error(f"샘플 추출 실패: {e}")
            raise

def main():
    """메인 실행 함수"""
    
    # DB 연결 설정
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ddf_db',
        'user': 'ddf_user',
        'password': 'ddf_password'
    }
    
    # 추출기 생성
    extractor = DRTDataExtractor(db_config)
    
    try:
        # 명령행 인자 확인
        if len(sys.argv) > 1 and sys.argv[1] == 'sample':
            # 샘플 추출
            sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
            output_file = extractor.extract_sample(sample_size)
        else:
            # 전체 데이터 추출
            batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
            output_file = extractor.extract_to_csv(batch_size)
        
        print(f"\n✅ 추출 완료!")
        print(f"출력 파일: {output_file}")
        
        # 간단한 통계 출력
        df_sample = pd.read_csv(output_file, nrows=1000)
        print(f"\n📊 데이터 미리보기:")
        print(df_sample.head())
        print(f"\n📋 데이터 정보:")
        print(df_sample.info())
        
    except Exception as e:
        logger.error(f"실행 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()