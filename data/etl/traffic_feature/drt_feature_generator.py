#!/usr/bin/env python3
"""
DRT Feature Generator
3가지 DRT 모델 (출퇴근형, 관광특화형, 교통취약지형)의 feature를 생성합니다.

Author: Claude Code
Date: 2025-08-26
"""

import os
import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Tuple, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DRTFeatureGenerator:
    """DRT 모델별 feature 생성기"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Args:
            db_config: 데이터베이스 연결 설정
        """
        self.db_config = db_config
        self.conn = None
        
        # POI 카테고리 가중치 정의
        self.commute_poi_weights = {
            '인구밀집지역': 1.0,
            '발달상권': 0.8, 
            '관광특구': 0.6,
            '고궁·문화유산': 0.4,
            '공원': 0.2
        }
        
        self.tourism_poi_weights = {
            '관광특구': 1.0,
            '고궁·문화유산': 0.9,
            '발달상권': 0.8,
            '공원': 0.7
        }
        
        self.vulnerable_poi_weights = {
            '인구밀집지역': 0.9,
            '공원': 0.8,
            '고궁·문화유산': 0.7,
            '발달상권': 0.6,
            '관광특구': 0.5
        }
        
        # 취약 시간대 정의
        self.vulnerable_hours = {
            'medical': list(range(9, 12)),    # 09-11시 의료시간
            'welfare': list(range(14, 17)),   # 14-16시 복지시간  
            'evening': list(range(18, 21))    # 18-20시 저녁시간
        }
    
    def connect_db(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("데이터베이스 연결 성공")
        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise
    
    def disconnect_db(self):
        """데이터베이스 연결 해제"""
        if self.conn:
            self.conn.close()
            logger.info("데이터베이스 연결 해제")
    
    def get_station_hourly_data(self, date: str) -> pd.DataFrame:
        """시간별 정류장 데이터 조회"""
        query = """
        SELECT 
            record_date,
            route_id,
            node_id,
            hour,
            dispatch_count as a05Num,
            ride_passenger as ridePnsgerCnt,
            alight_passenger as alghPnsgerCnt,
            (ride_passenger + alight_passenger) as total_passengers
        FROM station_passenger_history
        WHERE record_date = %s
        ORDER BY route_id, node_id, hour
        """
        
        return pd.read_sql(query, self.conn, params=[date])
    
    def get_section_hourly_data(self, date: str) -> pd.DataFrame:
        """시간별 구간 데이터 조회"""
        query = """
        SELECT 
            record_date,
            route_id,
            from_node_id,
            to_node_id,
            hour,
            avg_passengers as a18Num,
            operation_count
        FROM section_passenger_history
        WHERE record_date = %s
        ORDER BY route_id, from_node_id, to_node_id, hour
        """
        
        return pd.read_sql(query, self.conn, params=[date])
    
    def load_poi_data(self, poi_csv_path: str) -> Dict[str, float]:
        """POI 데이터 로드 및 가중치 매핑"""
        try:
            poi_df = pd.read_csv(poi_csv_path)
            poi_weights = {}
            
            for _, row in poi_df.iterrows():
                category = row['CATEGORY']
                area_name = row['AREA_NM']
                
                # 각 모델별 가중치 할당
                commute_weight = self.commute_poi_weights.get(category, 0.1)
                tourism_weight = self.tourism_poi_weights.get(category, 0.1)  
                vulnerable_weight = self.vulnerable_poi_weights.get(category, 0.1)
                
                poi_weights[area_name] = {
                    'commute': commute_weight,
                    'tourism': tourism_weight,
                    'vulnerable': vulnerable_weight,
                    'category': category
                }
            
            logger.info(f"POI 데이터 로드 완료: {len(poi_weights)}개 지역")
            return poi_weights
            
        except Exception as e:
            logger.error(f"POI 데이터 로드 실패: {e}")
            return {}
    
    def calculate_commute_features(self, station_df: pd.DataFrame, section_df: pd.DataFrame, 
                                 poi_weights: Dict) -> pd.DataFrame:
        """출퇴근형 DRT features 계산"""
        logger.info("출퇴근형 features 계산 시작")
        
        features = []
        
        # 정류장별 그룹화
        for (route_id, node_id), group in station_df.groupby(['route_id', 'node_id']):
            daily_data = group.sort_values('hour')
            
            # 1. 시간 집중도 지수 (TC_t) 계산
            max_dispatch = daily_data['a05Num'].max()
            if max_dispatch > 0:
                daily_data['TC_t'] = daily_data['a05Num'] / max_dispatch
            else:
                daily_data['TC_t'] = 0
            
            # 2. 피크 수요 비율 (PDR_t) 계산  
            max_passengers = daily_data['total_passengers'].max()
            if max_passengers > 0:
                daily_data['PDR_t'] = daily_data['total_passengers'] / max_passengers
            else:
                daily_data['PDR_t'] = 0
            
            # 3. 노선 활용도 (RU_t) - 구간 데이터에서 계산
            section_data = section_df[section_df['route_id'] == route_id]
            if not section_data.empty:
                avg_section_passengers = section_data.groupby('hour')['a18Num'].mean()
                daily_data['RU_t'] = daily_data['hour'].map(avg_section_passengers).fillna(0) / 1000.0
            else:
                daily_data['RU_t'] = 0
            
            # 4. POI 카테고리 가중치 (PCW) - 임시로 기본값 설정 (실제로는 공간 조인 필요)
            daily_data['PCW'] = 0.5  # 기본 가중치
            
            # DRT 점수 계산 (출퇴근형)
            daily_data['commute_drt_score'] = (
                daily_data['TC_t'] * 0.3 +
                daily_data['PDR_t'] * 0.4 + 
                daily_data['RU_t'] * 0.2 +
                daily_data['PCW'] * 0.1
            )
            
            features.append(daily_data)
        
        result_df = pd.concat(features, ignore_index=True)
        logger.info(f"출퇴근형 features 계산 완료: {len(result_df)} 레코드")
        return result_df
    
    def calculate_tourism_features(self, station_df: pd.DataFrame, section_df: pd.DataFrame,
                                 poi_weights: Dict) -> pd.DataFrame:
        """관광특화형 DRT features 계산"""
        logger.info("관광특화형 features 계산 시작")
        
        features = []
        
        for (route_id, node_id), group in station_df.groupby(['route_id', 'node_id']):
            daily_data = group.sort_values('hour')
            
            # 1. 관광 집중도 (TC_t) - 관광시간 가중치 적용
            max_dispatch = daily_data['a05Num'].max()
            if max_dispatch > 0:
                daily_data['TC_t'] = daily_data['a05Num'] / max_dispatch
                # 10-16시 관광시간 가중치 1.2 적용
                tourism_hours_mask = daily_data['hour'].between(10, 16)
                daily_data.loc[tourism_hours_mask, 'TC_t'] *= 1.2
            else:
                daily_data['TC_t'] = 0
            
            # 2. 관광 수요 비율 (TDR_t)
            max_passengers = daily_data['total_passengers'].max()
            if max_passengers > 0:
                daily_data['TDR_t'] = daily_data['total_passengers'] / max_passengers
                # 10-16시 관광시간 가중치 1.1 적용
                daily_data.loc[tourism_hours_mask, 'TDR_t'] *= 1.1
            else:
                daily_data['TDR_t'] = 0
            
            # 3. 구간 이용률 (RU_t) - 관광시간 60%, 비관광시간 40% 분배
            section_data = section_df[section_df['route_id'] == route_id]
            if not section_data.empty:
                avg_section_passengers = section_data.groupby('hour')['a18Num'].mean()
                daily_data['RU_t'] = daily_data['hour'].map(avg_section_passengers).fillna(0) / 1000.0
                
                # 관광시간/비관광시간 분배
                daily_data.loc[tourism_hours_mask, 'RU_t'] *= 0.6
                daily_data.loc[~tourism_hours_mask, 'RU_t'] *= 0.4
            else:
                daily_data['RU_t'] = 0
            
            # 4. POI 관광 가중치 (PCW) 
            daily_data['PCW'] = 0.7  # 관광 지역 기본 가중치
            
            # DRT 점수 계산 (관광특화형)
            daily_data['tourism_drt_score'] = (
                daily_data['TC_t'] * 0.25 +
                daily_data['TDR_t'] * 0.35 +
                daily_data['RU_t'] * 0.25 +
                daily_data['PCW'] * 0.15
            )
            
            features.append(daily_data)
        
        result_df = pd.concat(features, ignore_index=True)
        logger.info(f"관광특화형 features 계산 완료: {len(result_df)} 레코드")
        return result_df
    
    def calculate_vulnerable_features(self, station_df: pd.DataFrame, section_df: pd.DataFrame,
                                    poi_weights: Dict) -> pd.DataFrame:
        """교통취약지형 DRT features 계산"""
        logger.info("교통취약지형 features 계산 시작")
        
        features = []
        vulnerable_all_hours = set(
            self.vulnerable_hours['medical'] + 
            self.vulnerable_hours['welfare'] + 
            self.vulnerable_hours['evening']
        )
        
        for (route_id, node_id), group in station_df.groupby(['route_id', 'node_id']):
            daily_data = group.sort_values('hour')
            
            # 1. 취약 접근성 비율 (VAR_t)
            vulnerable_dispatch_sum = daily_data[
                daily_data['hour'].isin(vulnerable_all_hours)
            ]['a05Num'].sum()
            
            if vulnerable_dispatch_sum > 0:
                daily_data['VAR_t'] = daily_data['a05Num'] / vulnerable_dispatch_sum
            else:
                daily_data['VAR_t'] = 0
            
            # 취약 시간별 가중치 적용
            medical_mask = daily_data['hour'].isin(self.vulnerable_hours['medical'])
            welfare_mask = daily_data['hour'].isin(self.vulnerable_hours['welfare']) 
            evening_mask = daily_data['hour'].isin(self.vulnerable_hours['evening'])
            
            daily_data.loc[medical_mask, 'VAR_t'] *= 1.5
            daily_data.loc[welfare_mask, 'VAR_t'] *= 1.3
            daily_data.loc[evening_mask, 'VAR_t'] *= 1.2
            
            # 2. 사회 형평성 수요 (SED_t)
            vulnerable_passengers_sum = daily_data[
                daily_data['hour'].isin(vulnerable_all_hours)
            ]['total_passengers'].sum()
            
            if vulnerable_passengers_sum > 0:
                daily_data['SED_t'] = daily_data['total_passengers'] / vulnerable_passengers_sum
            else:
                daily_data['SED_t'] = 0
            
            # 저이용 구간 가중치 (100명 미만)
            low_usage_mask = daily_data['total_passengers'] < 100
            daily_data.loc[low_usage_mask, 'SED_t'] *= 1.4
            
            # 핵심 취약 시간 가중치
            core_vulnerable_mask = daily_data['hour'].isin([9, 14, 18])
            daily_data.loc[core_vulnerable_mask, 'SED_t'] *= 1.2
            
            # 3. 이동성 불리 지수 (MDI_t) - 역전 지수
            section_data = section_df[section_df['route_id'] == route_id]
            if not section_data.empty:
                avg_section_passengers = section_data.groupby('hour')['a18Num'].mean()
                daily_data['a18_mapped'] = daily_data['hour'].map(avg_section_passengers).fillna(0)
                daily_data['MDI_t'] = (1000 - daily_data['a18_mapped']) / 1000
                daily_data['MDI_t'] = daily_data['MDI_t'].clip(0, 1)  # 0-1 범위로 제한
            else:
                daily_data['MDI_t'] = 0.5  # 기본값
            
            # 취약/일반 시간대 분배
            vulnerable_mask = daily_data['hour'].isin(vulnerable_all_hours)
            daily_data.loc[vulnerable_mask, 'MDI_t'] *= 0.3
            daily_data.loc[~vulnerable_mask, 'MDI_t'] *= 0.7
            
            # 4. 지역 취약성 점수 (AVS)
            daily_data['AVS'] = 0.7  # 취약지역 기본 점수
            
            # DRT 점수 계산 (교통취약지형)
            daily_data['vulnerable_drt_score'] = (
                daily_data['VAR_t'] * 0.3 +
                daily_data['SED_t'] * 0.25 +
                daily_data['MDI_t'] * 0.25 +
                daily_data['AVS'] * 0.2
            )
            
            features.append(daily_data)
        
        result_df = pd.concat(features, ignore_index=True)
        logger.info(f"교통취약지형 features 계산 완료: {len(result_df)} 레코드")
        return result_df
    
    def generate_features_for_date(self, date: str, poi_csv_path: str, 
                                 output_dir: str) -> Dict[str, str]:
        """지정 날짜의 모든 DRT features 생성"""
        logger.info(f"DRT Features 생성 시작: {date}")
        
        try:
            self.connect_db()
            
            # 기본 데이터 로드
            station_df = self.get_station_hourly_data(date)
            section_df = self.get_section_hourly_data(date)
            poi_weights = self.load_poi_data(poi_csv_path)
            
            logger.info(f"Station 데이터: {len(station_df)} 레코드")
            logger.info(f"Section 데이터: {len(section_df)} 레코드")
            
            if station_df.empty:
                logger.warning(f"날짜 {date}의 station 데이터가 없습니다.")
                return {}
            
            # 각 모델별 features 계산
            results = {}
            
            # 1. 출퇴근형 DRT features
            commute_features = self.calculate_commute_features(station_df, section_df, poi_weights)
            commute_file = os.path.join(output_dir, f"commute_drt_features_{date.replace('-', '')}.csv")
            commute_features.to_csv(commute_file, index=False, encoding='utf-8')
            results['commute'] = commute_file
            
            # 2. 관광특화형 DRT features
            tourism_features = self.calculate_tourism_features(station_df, section_df, poi_weights)
            tourism_file = os.path.join(output_dir, f"tourism_drt_features_{date.replace('-', '')}.csv")
            tourism_features.to_csv(tourism_file, index=False, encoding='utf-8')
            results['tourism'] = tourism_file
            
            # 3. 교통취약지형 DRT features
            vulnerable_features = self.calculate_vulnerable_features(station_df, section_df, poi_weights)
            vulnerable_file = os.path.join(output_dir, f"vulnerable_drt_features_{date.replace('-', '')}.csv")
            vulnerable_features.to_csv(vulnerable_file, index=False, encoding='utf-8')
            results['vulnerable'] = vulnerable_file
            
            logger.info(f"DRT Features 생성 완료: {date}")
            return results
            
        except Exception as e:
            logger.error(f"Feature 생성 실패: {e}")
            raise
        finally:
            self.disconnect_db()

def main():
    """메인 실행 함수"""
    # 환경변수에서 DB 설정 로드
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'ddf_db'),
        'user': os.getenv('DB_USER', 'ddf_user'),
        'password': os.getenv('DB_PASSWORD', 'ddf_password')
    }
    
    # 파일 경로 설정
    poi_csv_path = "/data/raw/POI/seoul_poi_info.csv"
    output_dir = "/data/processed/drt_features"
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # Feature Generator 초기화
    generator = DRTFeatureGenerator(db_config)
    
    # 테스트 날짜로 실행 (2025-07-16)
    test_date = "2025-07-16"
    
    try:
        results = generator.generate_features_for_date(test_date, poi_csv_path, output_dir)
        
        print("=" * 60)
        print("DRT Feature 생성 완료!")
        print("=" * 60)
        for model_type, file_path in results.items():
            print(f"{model_type.upper()} 모델: {file_path}")
        
    except Exception as e:
        logger.error(f"실행 실패: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())