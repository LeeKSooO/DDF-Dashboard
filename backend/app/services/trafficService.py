"""
시간대별 교통량 컴포넌트 전용 서비스
월별 기준 서울시/구별 평일/주말 시간대별 승하차 패턴 분석
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.schemas.traffic import (
    HourlyTrafficSchema,
    HourlyPatternSchema,
    PeakHoursSchema,
    PeakHourInfoSchema
)
from app.utils.response import (
    bad_request_response,
    validate_district_name,
    handle_database_error
)

logger = logging.getLogger(__name__)


# 스키마는 schemas/traffic.py에서 import하여 사용


class HourlyTrafficService:
    """시간대별 교통량 서비스"""
    
    def __init__(self):
        pass
    
    async def get_hourly_traffic(
        self,
        db: AsyncSession,
        analysis_month: str,
        region_type: str,
        district_name: Optional[str] = None
    ) -> HourlyTrafficSchema:
        """시간대별 교통량 조회 (서울시/구별, 평일/주말)"""
        try:
            # 입력 유효성 검사
            self._validate_inputs(analysis_month, region_type, district_name)
            
            print(f"[DEBUG] Getting hourly traffic for {analysis_month}, {region_type}, {district_name}")
            
            # 평일 패턴 조회
            print("[DEBUG] Fetching weekday patterns...")
            weekday_patterns = await self._get_hourly_patterns(
                db, analysis_month, "weekday", district_name
            )
            print(f"[DEBUG] Got {len(weekday_patterns)} weekday patterns")
            
            # 주말 패턴 조회
            logger.info("Fetching weekend patterns...")
            weekend_patterns = await self._get_hourly_patterns(
                db, analysis_month, "weekend", district_name
            )
            logger.info(f"Got {len(weekend_patterns)} weekend patterns")
            
            # 피크 시간 분석
            peak_hours = self._analyze_peak_hours(weekday_patterns, weekend_patterns)
            
            # 총 승객수 계산 (이미 시간대별 평균이므로 * 24 불필요)
            total_weekday = sum(p.avg_total_passengers for p in weekday_patterns)
            total_weekend = sum(p.avg_total_passengers for p in weekend_patterns)
            
            # 평일/주말 비율
            ratio = total_weekday / total_weekend if total_weekend > 0 else 0
            
            # 지역명 결정
            region_name = district_name if district_name else "서울시 전체"
            
            return HourlyTrafficSchema(
                analysis_month=analysis_month,
                region_type=region_type,
                region_name=region_name,
                district_name=district_name,
                weekday_patterns=weekday_patterns,
                weekend_patterns=weekend_patterns,
                peak_hours=peak_hours,
                total_weekday_passengers=int(total_weekday),
                total_weekend_passengers=int(total_weekend),
                weekday_weekend_ratio=round(ratio, 2)
            )
            
        except Exception as e:
            logger.error(f"Error in get_hourly_traffic: {e}")
            raise handle_database_error(e)
    
    def _validate_inputs(self, analysis_month: str, region_type: str, district_name: Optional[str]):
        """입력 파라미터 유효성 검사"""
        # 월 형식 검증
        try:
            datetime.strptime(f"{analysis_month}-01", "%Y-%m-%d")
        except ValueError:
            raise bad_request_response("Invalid month format. Use YYYY-MM (e.g., 2025-07)")
        
        # 지역 타입 검증
        if region_type not in ["seoul", "district"]:
            raise bad_request_response("region_type must be 'seoul' or 'district'")
        
        # 구명 검증
        if region_type == "district":
            if not district_name:
                raise bad_request_response("district_name is required when region_type is 'district'")
            validate_district_name(district_name)
    
    async def _get_hourly_patterns(
        self,
        db: AsyncSession,
        analysis_month: str,
        day_type: str,
        district_name: Optional[str] = None
    ) -> List[HourlyPatternSchema]:
        """시간대별 승하차 패턴 조회 (station_passenger_history 기반)"""
        try:
            # 요일 필터 생성
            weekday_filter = ""
            if day_type == "weekday":
                weekday_filter = "AND EXTRACT(DOW FROM sph.record_date) BETWEEN 1 AND 5"
            elif day_type == "weekend":
                weekday_filter = "AND EXTRACT(DOW FROM sph.record_date) IN (0, 6)"
            
            # 최적화된 쿼리 생성 (매핑 테이블 활용)
            if district_name:
                # 구별 쿼리: spatial_mapping을 서브쿼리로 활용 (최적화)
                query = text(f"""
                    SELECT 
                        sph.hour,
                        AVG(sph.ride_passenger) as avg_ride_passengers,
                        AVG(sph.alight_passenger) as avg_alight_passengers,
                        AVG(sph.ride_passenger + sph.alight_passenger) as avg_total_passengers
                    FROM station_passenger_history sph
                    WHERE DATE_TRUNC('month', sph.record_date) = '{analysis_month}-01'::date
                        {weekday_filter}
                        AND sph.node_id IN (
                            SELECT node_id 
                            FROM spatial_mapping
                            WHERE sgg_name = :district_name
                        )
                    GROUP BY sph.hour
                    ORDER BY sph.hour
                """)
            else:
                # 서울시 전체 쿼리 (spatial_mapping JOIN으로 최적화)
                query = text(f"""
                    SELECT 
                        sph.hour,
                        AVG(sph.ride_passenger) as avg_ride_passengers,
                        AVG(sph.alight_passenger) as avg_alight_passengers,
                        AVG(sph.ride_passenger + sph.alight_passenger) as avg_total_passengers
                    FROM station_passenger_history sph
                    INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
                    WHERE DATE_TRUNC('month', sph.record_date) = '{analysis_month}-01'::date
                        {weekday_filter}
                        AND sm.is_seoul = TRUE
                    GROUP BY sph.hour
                    ORDER BY sph.hour
                """)
            
            # 파라미터 설정
            params = {}
            if district_name:
                params["district_name"] = district_name
            
            # 쿼리 실행
            result = await db.execute(query, params)
            rows = result.fetchall()
            
            # 디버깅: 쿼리 결과 로깅
            print(f"[DEBUG] Query returned {len(rows)} rows for {day_type}")
            if len(rows) > 0:
                # SQLAlchemy Row 객체의 속성 확인
                first_row = rows[0]
                print(f"[DEBUG] Row type: {type(first_row)}")
                print(f"[DEBUG] Row keys: {first_row.keys() if hasattr(first_row, 'keys') else 'No keys method'}")
                try:
                    print(f"[DEBUG] First row sample: hour={first_row[0]}, ride={first_row[1]}, total={first_row[3]}")
                except Exception as e:
                    print(f"[DEBUG] Error accessing row: {e}")
            else:
                print(f"[DEBUG] No rows returned! Query: {query}")
                print(f"[DEBUG] Params: {params}")
            
            # 결과 처리 - 24시간 모든 시간대 보장
            patterns = []
            # SQLAlchemy Row 객체는 인덱스로 접근해야 함
            row_dict = {row[0]: row for row in rows}
            
            for hour in range(24):
                if hour in row_dict:
                    row = row_dict[hour]
                    patterns.append(HourlyPatternSchema(
                        hour=hour,
                        avg_ride_passengers=float(row[1] or 0),
                        avg_alight_passengers=float(row[2] or 0),
                        avg_total_passengers=float(row[3] or 0)
                    ))
                else:
                    # 데이터가 없는 시간대는 0으로 채움
                    patterns.append(HourlyPatternSchema(
                        hour=hour,
                        avg_ride_passengers=0.0,
                        avg_alight_passengers=0.0,
                        avg_total_passengers=0.0
                    ))
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error in _get_hourly_patterns: {e}")
            raise
    
    def _analyze_peak_hours(
        self, 
        weekday_patterns: List[HourlyPatternSchema],
        weekend_patterns: List[HourlyPatternSchema]
    ) -> PeakHoursSchema:
        """피크 시간 분석"""
        try:
            # 평일 아침 피크 (6-10시)
            morning_peak = max(
                [(p.hour, p.avg_total_passengers) for p in weekday_patterns if 6 <= p.hour <= 10],
                key=lambda x: x[1],
                default=(8, 0)
            )
            
            # 평일 저녁 피크 (17-20시)
            evening_peak = max(
                [(p.hour, p.avg_total_passengers) for p in weekday_patterns if 17 <= p.hour <= 20],
                key=lambda x: x[1],
                default=(18, 0)
            )
            
            # 주말 피크 (전체 시간)
            weekend_peak = max(
                [(p.hour, p.avg_total_passengers) for p in weekend_patterns],
                key=lambda x: x[1],
                default=(14, 0)
            )
            
            return PeakHoursSchema(
                weekday_morning_peak=PeakHourInfoSchema(
                    hour=morning_peak[0], 
                    avg_total_passengers=round(morning_peak[1], 1)
                ),
                weekday_evening_peak=PeakHourInfoSchema(
                    hour=evening_peak[0], 
                    avg_total_passengers=round(evening_peak[1], 1)
                ),
                weekend_peak=PeakHourInfoSchema(
                    hour=weekend_peak[0], 
                    avg_total_passengers=round(weekend_peak[1], 1)
                )
            )
            
        except Exception as e:
            logger.error(f"Error in _analyze_peak_hours: {e}")
            # 기본값 반환
            return PeakHoursSchema(
                weekday_morning_peak=PeakHourInfoSchema(hour=8, avg_total_passengers=0.0),
                weekday_evening_peak=PeakHourInfoSchema(hour=18, avg_total_passengers=0.0),
                weekend_peak=PeakHourInfoSchema(hour=14, avg_total_passengers=0.0)
            )