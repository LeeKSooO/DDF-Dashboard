"""
교통 특이패턴 분석 서비스
웹 대시보드에서 특정 월/구를 선택했을 때, 해당 구의 6가지 특이패턴 정류장을 제공
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.schemas.anomalyPattern import (
    AnomalyPatternResponse,
    DistrictAverageSchema,
    StationInfoSchema,
    WeekendDominantStationSchema,
    NightDemandStationSchema,
    RushHourStationSchema,
    LunchTimeStationSchema,
    AreaTypeStationSchema,
    HighVolatilityStationSchema,
    AnomalyPatternFilterSchema
)

logger = logging.getLogger(__name__)


class AnomalyPatternService:
    """교통 특이패턴 분석 서비스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def analyze_district_anomaly_patterns(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        filters: Optional[AnomalyPatternFilterSchema] = None
    ) -> AnomalyPatternResponse:
        """
        구별 교통 특이패턴 종합 분석
        
        웹 대시보드에서 특정 월/구 선택시 해당 구의 특이패턴 정류장들을 분석
        """
        
        if filters is None:
            filters = AnomalyPatternFilterSchema()
        
        self.logger.info(f"Starting anomaly pattern analysis for {district_name} in {analysis_month}")
        
        try:
            # 1. 구 전체 평균 지표 계산
            district_averages = await self.calculate_district_averages(db, district_name, analysis_month)
            
            # 2. 6가지 특이패턴 분석 (순차 실행)
            weekend_stations = await self.get_weekend_dominant_stations(db, district_name, analysis_month, filters.top_n)
            night_stations = await self.get_night_demand_stations(db, district_name, analysis_month, filters.top_n)  
            rush_stations = await self.get_rush_hour_stations(db, district_name, analysis_month, filters.top_n)
            lunch_stations = await self.get_lunch_time_stations(db, district_name, analysis_month, filters.top_n)
            area_stations = await self.get_area_type_stations(db, district_name, analysis_month, filters.top_n)
            volatility_stations = await self.get_high_volatility_stations(db, district_name, analysis_month, filters.top_n)
            
            analysis_period = analysis_month.strftime("%Y-%m")
            
            self.logger.info(f"Anomaly pattern analysis completed for {district_name}")
            
            return AnomalyPatternResponse(
                district_name=district_name,
                analysis_period=analysis_period,
                analysis_month=analysis_month.strftime("%Y-%m"),
                generated_at=datetime.now().isoformat(),
                district_averages=district_averages,
                weekend_dominant_stations=weekend_stations,
                night_demand_stations=night_stations,
                rush_hour_stations=rush_stations,
                lunch_time_stations=lunch_stations,
                area_type_stations=area_stations,
                high_volatility_stations=volatility_stations
            )
            
        except Exception as e:
            self.logger.error(f"Error in anomaly pattern analysis: {e}")
            raise

    async def calculate_district_averages(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date
    ) -> DistrictAverageSchema:
        """구 전체 평균 지표 계산 (기준값)"""
        
        query = text("""
            WITH base_stats AS (
                SELECT 
                    sph.node_id,
                    CASE WHEN EXTRACT(DOW FROM sph.record_date) IN (0, 6) THEN 'weekend' ELSE 'weekday' END as day_type,
                    sph.hour,
                    AVG(sph.ride_passenger) as avg_ride,
                    AVG(sph.alight_passenger) as avg_alight,
                    AVG(sph.ride_passenger + sph.alight_passenger) as avg_total,
                    STDDEV(sph.ride_passenger + sph.alight_passenger) as std_total
                FROM station_passenger_history sph
                JOIN spatial_mapping sm ON sph.node_id = sm.node_id
                WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
                  AND sm.sgg_name = :district_name
                  AND (sph.ride_passenger + sph.alight_passenger) > 0
                GROUP BY sph.node_id, day_type, sph.hour
            ),
            weekend_comparison AS (
                SELECT 
                    node_id,
                    AVG(CASE WHEN day_type = 'weekend' THEN avg_total END) as weekend_avg,
                    AVG(CASE WHEN day_type = 'weekday' THEN avg_total END) as weekday_avg
                FROM base_stats
                GROUP BY node_id
                HAVING AVG(CASE WHEN day_type = 'weekend' THEN avg_total END) IS NOT NULL 
                   AND AVG(CASE WHEN day_type = 'weekday' THEN avg_total END) IS NOT NULL
            ),
            night_stats AS (
                SELECT 
                    node_id,
                    AVG(CASE WHEN hour IN (23, 0, 1, 2, 3) THEN avg_total ELSE 0 END) / AVG(avg_total) * 100 as night_ratio
                FROM base_stats
                GROUP BY node_id
            )
            SELECT 
                -- 주말 증가율
                AVG((bs.weekend_avg - bs.weekday_avg) / bs.weekday_avg * 100) as avg_weekend_increase_pct,
                
                -- 심야 교통 비율  
                AVG(ns.night_ratio) as avg_night_traffic_ratio,
                
                -- 러시아워 교통량
                AVG(CASE WHEN bs2.hour IN (6,7,8,17,18,19) THEN bs2.avg_total ELSE 0 END) as avg_rush_hour_traffic,
                
                -- 점심시간 증가율
                AVG(CASE WHEN bs2.hour IN (11,12,13) THEN bs2.avg_alight ELSE 0 END) / AVG(bs2.avg_alight) * 100 as avg_lunch_spike_pct,
                
                -- 변동계수
                AVG(bs2.std_total / bs2.avg_total) as avg_cv_coefficient,
                
                -- 메타 정보
                COUNT(DISTINCT bs2.node_id) as total_stations,
                16 as analysis_period_days
                
            FROM weekend_comparison bs
            JOIN night_stats ns ON bs.node_id = ns.node_id  
            JOIN base_stats bs2 ON bs.node_id = bs2.node_id
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month
        })
        
        row = result.first()
        if not row:
            raise ValueError(f"No data found for district: {district_name}")
            
        return DistrictAverageSchema(
            avg_weekend_increase_pct=float(row.avg_weekend_increase_pct or 0.0),
            avg_night_traffic_ratio=float(row.avg_night_traffic_ratio or 0.0),
            avg_rush_hour_traffic=float(row.avg_rush_hour_traffic or 0.0),
            avg_lunch_spike_pct=float(row.avg_lunch_spike_pct or 0.0),
            avg_cv_coefficient=float(row.avg_cv_coefficient or 0.0),
            total_stations=int(row.total_stations or 0),
            analysis_period_days=int(row.analysis_period_days or 0)
        )

    async def get_weekend_dominant_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[WeekendDominantStationSchema]:
        """1. 주말 고수요 정류장 분석
        
        비즈니스 로직:
        1단계: 주말 총 교통량이 높은 정류장 TOP N 선별
        2단계: 선별된 정류장별 주말 피크 시간대 TOP 3 분석
        """
        
        # 1단계: 주말 교통량이 높은 정류장 TOP N 선별
        stations_query = text("""
            SELECT 
                sph.node_id,
                bs.node_name,
                bs.coordinates_x as longitude,
                bs.coordinates_y as latitude,
                sm.sgg_name as district_name,
                COALESCE(sm.adm_name, '정보없음') as administrative_dong,
                
                -- 주말 총 교통량
                SUM(CASE WHEN EXTRACT(DOW FROM sph.record_date) IN (0, 6) 
                    THEN sph.ride_passenger + sph.alight_passenger ELSE 0 END) as weekend_total
                        
            FROM station_passenger_history sph
            JOIN spatial_mapping sm ON sph.node_id = sm.node_id  
            JOIN bus_stops bs ON sm.node_id = bs.node_id
            WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
              AND sm.sgg_name = :district_name
              AND sm.is_seoul = TRUE
              AND (sph.ride_passenger + sph.alight_passenger) > 0
            GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y, sm.sgg_name, sm.adm_name
            HAVING SUM(CASE WHEN EXTRACT(DOW FROM sph.record_date) IN (0, 6) 
                           THEN sph.ride_passenger + sph.alight_passenger ELSE 0 END) > 0
            ORDER BY SUM(CASE WHEN EXTRACT(DOW FROM sph.record_date) IN (0, 6) 
                             THEN sph.ride_passenger + sph.alight_passenger ELSE 0 END) DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(stations_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        top_station_ids = []
        
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                district_name=row.district_name,
                administrative_dong=row.administrative_dong
            )
            
            stations.append({
                'station_info': station_info,
                'weekend_total': int(row.weekend_total or 0),
                'node_id': row.node_id
            })
            top_station_ids.append(row.node_id)
        
        # 2단계: 선별된 정류장들의 주말 시간대별 교통량으로 피크 시간대 TOP 3 추출
        if top_station_ids:
            # IN 절을 위한 동적 쿼리 생성
            placeholders = ','.join([f':station_id_{i}' for i in range(len(top_station_ids))])
            peak_query = text(f"""
                WITH hourly_traffic AS (
                    SELECT 
                        sph.node_id,
                        sph.hour,
                        SUM(sph.ride_passenger + sph.alight_passenger) as hour_total
                    FROM station_passenger_history sph
                    WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
                      AND sph.node_id IN ({placeholders})
                      AND EXTRACT(DOW FROM sph.record_date) IN (0, 6)  -- 주말만
                    GROUP BY sph.node_id, sph.hour
                ),
                ranked_hours AS (
                    SELECT 
                        node_id,
                        hour,
                        hour_total,
                        ROW_NUMBER() OVER (PARTITION BY node_id ORDER BY hour_total DESC) as rank
                    FROM hourly_traffic
                )
                SELECT 
                    node_id,
                    ARRAY_AGG(hour ORDER BY rank) as peak_hours,
                    ARRAY_AGG(hour_total ORDER BY rank) as peak_traffic
                FROM ranked_hours
                WHERE rank <= 3
                GROUP BY node_id
            """)
            
            # 파라미터 딕셔너리 생성
            params = {"analysis_month": analysis_month}
            for i, station_id in enumerate(top_station_ids):
                params[f"station_id_{i}"] = station_id
            
            peak_result = await db.execute(peak_query, params)
            
            peak_hours_map = {}
            for row in peak_result:
                peak_hours_map[row.node_id] = {
                    'hours': list(row.peak_hours or []),
                    'traffic': list(row.peak_traffic or [])
                }
        else:
            peak_hours_map = {}
        
        # 최종 결과 조합
        final_stations = []
        for idx, station_data in enumerate(stations, 1):
            node_id = station_data['node_id']
            peak_data = peak_hours_map.get(node_id, {'hours': [], 'traffic': []})
            weekend_peak_hours = peak_data['hours'][:3]  # 이미 TOP 3로 제한됨
            weekend_peak_traffic = [int(t) for t in peak_data['traffic'][:3]]  # 피크 시간대 교통량
            weekend_total = station_data['weekend_total']
            
            # 주말 일평균 계산 (분석 기간 내 주말 일수 계산)
            # 7월의 경우: 15-31일 중 주말은 토,일 약 4-5일
            weekend_days = 4  # 분석 기간 내 주말 일수 (대략값)
            weekend_daily_avg = weekend_total / weekend_days if weekend_days > 0 else 0
            
            final_stations.append(WeekendDominantStationSchema(
                station=station_data['station_info'],
                weekend_total_traffic=weekend_total,
                weekend_daily_avg=round(weekend_daily_avg, 1),
                weekend_peak_hours=weekend_peak_hours,
                weekend_peak_traffic=weekend_peak_traffic,
                rank=idx
            ))
            
        return final_stations

    async def get_night_demand_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[NightDemandStationSchema]:
        """2. 심야시간 고수요 정류장 분석 (23-03시)"""
        
        query = text("""
            SELECT 
                sph.node_id,
                bs.node_name,
                bs.coordinates_x as longitude,
                bs.coordinates_y as latitude,
                SUM(CASE WHEN sph.hour IN (23, 0, 1, 2, 3) THEN sph.ride_passenger ELSE 0 END) as total_night_rides
            FROM station_passenger_history sph
            JOIN spatial_mapping sm ON sph.node_id = sm.node_id
            JOIN bus_stops bs ON sm.node_id = bs.node_id
            WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
              AND sm.sgg_name = :district_name
              AND sph.hour IN (23, 0, 1, 2, 3)
              AND sph.ride_passenger > 0
            GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y
            ORDER BY total_night_rides DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude)
            )
            
            stations.append(NightDemandStationSchema(
                station_info=station_info,
                total_night_rides=int(row.total_night_rides)
            ))
            
        return stations

    async def get_rush_hour_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[RushHourStationSchema]:
        """3. 출퇴근 시간대 고수요 정류장 분석 (06-08, 17-19시)"""
        
        query = text("""
            SELECT 
                sph.node_id,
                bs.node_name,
                bs.coordinates_x as longitude,
                bs.coordinates_y as latitude,
                SUM(CASE WHEN sph.hour IN (6, 7, 8, 17, 18, 19) THEN sph.ride_passenger ELSE 0 END) as total_rush_rides
            FROM station_passenger_history sph
            JOIN spatial_mapping sm ON sph.node_id = sm.node_id
            JOIN bus_stops bs ON sm.node_id = bs.node_id
            WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
              AND sm.sgg_name = :district_name
              AND sph.hour IN (6, 7, 8, 17, 18, 19)
              AND sph.ride_passenger > 0
              AND EXTRACT(DOW FROM sph.record_date) BETWEEN 1 AND 5  -- 평일만
            GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y
            ORDER BY total_rush_rides DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude)
            )
            
            stations.append(RushHourStationSchema(
                station_info=station_info,
                total_rush_rides=int(row.total_rush_rides)
            ))
            
        return stations

    async def get_lunch_time_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[LunchTimeStationSchema]:
        """4. 점심시간 특화 정류장 분석 (11-13시 하차 집중)"""
        
        query = text("""
            SELECT 
                sph.node_id,
                bs.node_name,
                bs.coordinates_x as longitude,
                bs.coordinates_y as latitude,
                SUM(CASE WHEN sph.hour IN (11, 12, 13) THEN sph.alight_passenger ELSE 0 END) as total_lunch_alights
            FROM station_passenger_history sph
            JOIN spatial_mapping sm ON sph.node_id = sm.node_id
            JOIN bus_stops bs ON sm.node_id = bs.node_id
            WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
              AND sm.sgg_name = :district_name
              AND sph.hour IN (11, 12, 13)
              AND sph.alight_passenger > 0
              AND EXTRACT(DOW FROM sph.record_date) BETWEEN 1 AND 5  -- 평일만
            GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y
            ORDER BY total_lunch_alights DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude)
            )
            
            stations.append(LunchTimeStationSchema(
                station_info=station_info,
                total_lunch_alights=int(row.total_lunch_alights)
            ))
            
        return stations

    async def get_area_type_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[AreaTypeStationSchema]:
        """5. 구역 특성별 정류장 패턴 분석 (승하차 불균형)"""
        
        query = text("""
            WITH area_analysis AS (
                SELECT 
                    sph.node_id,
                    bs.node_name,
                    bs.coordinates_x as longitude,
                    bs.coordinates_y as latitude,
                    
                    -- 출근시간대 (6-8시) 승차/하차 비율
                    SUM(CASE WHEN sph.hour IN (6, 7, 8) THEN sph.ride_passenger ELSE 0 END) as morning_rides,
                    SUM(CASE WHEN sph.hour IN (6, 7, 8) THEN sph.alight_passenger ELSE 0 END) as morning_alights,
                    
                    -- 퇴근시간대 (17-19시) 승차/하차 비율  
                    SUM(CASE WHEN sph.hour IN (17, 18, 19) THEN sph.ride_passenger ELSE 0 END) as evening_rides,
                    SUM(CASE WHEN sph.hour IN (17, 18, 19) THEN sph.alight_passenger ELSE 0 END) as evening_alights,
                    
                    -- 점심/주말 피크
                    AVG(CASE WHEN sph.hour IN (11, 12, 13) THEN sph.ride_passenger + sph.alight_passenger END) as lunch_avg,
                    AVG(CASE WHEN EXTRACT(DOW FROM sph.record_date) IN (0, 6) THEN sph.ride_passenger + sph.alight_passenger END) as weekend_avg,
                    
                    -- 전체 평균 (균등성 판단용)
                    AVG(sph.ride_passenger + sph.alight_passenger) as total_avg,
                    STDDEV(sph.ride_passenger + sph.alight_passenger) as total_stddev
                    
                FROM station_passenger_history sph
                JOIN spatial_mapping sm ON sph.node_id = sm.node_id
                JOIN bus_stops bs ON sm.node_id = bs.node_id
                WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
                  AND sm.sgg_name = :district_name
                  AND (sph.ride_passenger + sph.alight_passenger) > 0
                  AND EXTRACT(DOW FROM sph.record_date) BETWEEN 1 AND 5  -- 평일 기준
                GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y
            ),
            area_classification AS (
                SELECT *,
                    CASE 
                        -- 주거지역: 출근시 승차>>하차, 퇴근시 하차>>승차
                        WHEN (morning_rides > morning_alights * 1.5) 
                         AND (evening_alights > evening_rides * 1.5) THEN 'residential'
                         
                        -- 업무지역: 출근시 하차>>승차, 퇴근시 승차>>하차  
                        WHEN (morning_alights > morning_rides * 1.5) 
                         AND (evening_rides > evening_alights * 1.5) THEN 'business'
                         
                        -- 상업지역: 점심/주말이 피크
                        WHEN (lunch_avg > total_avg * 1.2) 
                          OR (weekend_avg > total_avg * 1.2) THEN 'commercial'
                          
                        -- 교통허브: 지속적으로 균등하고 높은 승하차량
                        WHEN (total_stddev / total_avg < 0.5) 
                         AND (total_avg > 100) THEN 'transport_hub'
                         
                        ELSE 'mixed'
                    END as area_type,
                    
                    -- 불균형 지수 계산
                    ABS(morning_rides - morning_alights) + ABS(evening_rides - evening_alights) as imbalance_score
                    
                FROM area_analysis
                WHERE (morning_rides + morning_alights + evening_rides + evening_alights) > 0
            )
            SELECT 
                node_id,
                node_name, 
                longitude,
                latitude,
                area_type,
                imbalance_score
            FROM area_classification
            WHERE area_type != 'mixed'
            ORDER BY imbalance_score DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude)
            )
            
            stations.append(AreaTypeStationSchema(
                station_info=station_info,
                area_type=row.area_type,
                imbalance_score=float(row.imbalance_score)
            ))
            
        return stations

    async def get_high_volatility_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[HighVolatilityStationSchema]:
        """6. 시계열 변동지수가 높은 정류장 분석"""
        
        query = text("""
            WITH volatility_analysis AS (
                SELECT 
                    sph.node_id,
                    bs.node_name,
                    bs.coordinates_x as longitude,
                    bs.coordinates_y as latitude,
                    sph.hour,
                    
                    -- 시간대별 변동계수 계산
                    STDDEV(sph.ride_passenger + sph.alight_passenger) / 
                    AVG(sph.ride_passenger + sph.alight_passenger) as cv_by_hour,
                    
                    AVG(sph.ride_passenger + sph.alight_passenger) as avg_traffic_by_hour
                    
                FROM station_passenger_history sph
                JOIN spatial_mapping sm ON sph.node_id = sm.node_id
                JOIN bus_stops bs ON sm.node_id = bs.node_id
                WHERE DATE_TRUNC('month', sph.record_date)::date = :analysis_month
                  AND sm.sgg_name = :district_name
                  AND (sph.ride_passenger + sph.alight_passenger) > 0
                GROUP BY sph.node_id, bs.node_name, bs.coordinates_x, bs.coordinates_y, sph.hour
                HAVING AVG(sph.ride_passenger + sph.alight_passenger) > 0
            ),
            station_volatility AS (
                SELECT 
                    node_id,
                    node_name,
                    longitude,
                    latitude,
                    AVG(cv_by_hour) as avg_cv_coefficient,
                    
                    -- 가장 변동성이 큰 시간대
                    (ARRAY_AGG(hour ORDER BY cv_by_hour DESC))[1] as peak_volatility_hour
                    
                FROM volatility_analysis
                WHERE cv_by_hour IS NOT NULL AND cv_by_hour > 0
                GROUP BY node_id, node_name, longitude, latitude
            )
            SELECT 
                node_id,
                node_name,
                longitude, 
                latitude,
                ROUND(avg_cv_coefficient::numeric, 3) as avg_cv_coefficient,
                peak_volatility_hour
            FROM station_volatility
            ORDER BY avg_cv_coefficient DESC
            LIMIT :top_n
        """)
        
        result = await db.execute(query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        stations = []
        for row in result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude)
            )
            
            stations.append(HighVolatilityStationSchema(
                station_info=station_info,
                cv_coefficient=float(row.avg_cv_coefficient),
                peak_volatility_hour=int(row.peak_volatility_hour) if row.peak_volatility_hour else 0
            ))
            
        return stations