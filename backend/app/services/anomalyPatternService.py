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
    IntegratedAnomalyPatternResponse,
    DistrictAverageSchema,
    StationInfoSchema,
    WeekendDominantStationSchema,
    NightDemandStationSchema,
    RushHourStationSchema,
    MorningRushStationSchema,
    EveningRushStationSchema,
    LunchTimeStationSchema,
    AreaTypeAnalysisSchema,
    ResidentialAreaStationSchema,
    BusinessAreaStationSchema,
    UnderutilizedStationSchema,
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
        
        MV 활용한 최적화된 비즈니스 로직:
        1단계: mv_station_hourly_patterns에서 주말 교통량 TOP N + 피크 시간대
        2단계: 구 전체 주말 통계
        3단계: vs_district_avg 계산
        """
        
        # 1단계: MV에서 주말 교통량 TOP N 정류장 조회
        stations_query = text("""
            WITH weekend_traffic AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    hour,
                    SUM(total_traffic) as hour_traffic
                FROM mv_station_hourly_patterns
                WHERE month_date = :analysis_month
                  AND district_name = :district_name
                  AND day_type = 'weekend'
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong, hour
            ),
            station_totals AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    SUM(hour_traffic) as weekend_total
                FROM weekend_traffic
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong
                ORDER BY weekend_total DESC
                LIMIT :top_n
            )
            SELECT 
                st.station_id as node_id,
                st.station_name as node_name,
                st.longitude,
                st.latitude,
                st.district_name,
                st.administrative_dong,
                st.weekend_total
            FROM station_totals st
        """)
        
        result = await db.execute(stations_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        # 2단계: 구 전체 주말 통계 조회 (vs_district_avg용)
        district_stats_query = text("""
            SELECT 
                SUM(total_traffic) as district_weekend_total,
                COUNT(DISTINCT station_id) as total_stations
            FROM mv_station_hourly_patterns
            WHERE month_date = :analysis_month
              AND district_name = :district_name
              AND day_type = 'weekend'
        """)
        
        district_stats_result = await db.execute(district_stats_query, {
            "district_name": district_name,
            "analysis_month": analysis_month
        })
        
        district_stats = district_stats_result.fetchone()
        district_weekend_total = district_stats.district_weekend_total or 1
        total_stations = district_stats.total_stations or 1
        district_avg_per_station = district_weekend_total / total_stations
        
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
        
        # 3단계: 선별된 정류장들의 주말 시간대별 피크 TOP 3 (MV 활용)
        if top_station_ids:
            placeholders = ','.join([f':station_id_{i}' for i in range(len(top_station_ids))])
            peak_query = text(f"""
                WITH hourly_traffic AS (
                    SELECT 
                        station_id as node_id,
                        hour,
                        SUM(total_traffic) as hour_total
                    FROM mv_station_hourly_patterns
                    WHERE month_date = :analysis_month
                      AND station_id IN ({placeholders})
                      AND day_type = 'weekend'
                    GROUP BY station_id, hour
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
            
            # vs_district_avg 계산 (구 평균 정류장 대비 배수)
            vs_district_avg = weekend_total / district_avg_per_station if district_avg_per_station > 0 else 0.0
            
            final_stations.append(WeekendDominantStationSchema(
                station=station_data['station_info'],
                weekend_total_traffic=weekend_total,
                weekend_peak_hours=weekend_peak_hours,
                weekend_peak_traffic=weekend_peak_traffic,
                rank=idx,
                vs_district_avg=round(vs_district_avg, 1)
            ))
            
        return final_stations

    async def get_night_demand_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[NightDemandStationSchema]:
        """2. 심야시간 고수요 정류장 분석 (23-03시)
        
        MV 활용한 최적화된 비즈니스 로직:
        1단계: mv_station_hourly_patterns에서 심야시간 TOP N 선별 + 시간대별 분석
        2단계: 구 전체 심야시간 통계 (동일 MV 활용)
        3단계: vs_district_avg 계산
        """
        
        # 1단계: MV에서 심야시간 TOP N 정류장 + 시간대별 데이터 한번에 조회
        stations_query = text("""
            WITH night_stations AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    -- 심야시간 총 승차인원
                    SUM(CASE WHEN hour IN (23, 0, 1, 2, 3) THEN total_ride ELSE 0 END) as total_night_ride,
                    -- 시간대별 승차량 (피벗)
                    SUM(CASE WHEN hour = 23 THEN total_ride ELSE 0 END) as hour_23,
                    SUM(CASE WHEN hour = 0 THEN total_ride ELSE 0 END) as hour_0,
                    SUM(CASE WHEN hour = 1 THEN total_ride ELSE 0 END) as hour_1,
                    SUM(CASE WHEN hour = 2 THEN total_ride ELSE 0 END) as hour_2,
                    SUM(CASE WHEN hour = 3 THEN total_ride ELSE 0 END) as hour_3
                FROM mv_station_hourly_patterns
                WHERE month_date = :analysis_month
                  AND district_name = :district_name
                  AND hour IN (23, 0, 1, 2, 3)
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong
                HAVING SUM(CASE WHEN hour IN (23, 0, 1, 2, 3) THEN total_ride ELSE 0 END) > 0
                ORDER BY total_night_ride DESC
                LIMIT :top_n
            )
            SELECT 
                station_id as node_id,
                station_name as node_name,
                longitude,
                latitude,
                district_name,
                administrative_dong,
                total_night_ride,
                hour_23, hour_0, hour_1, hour_2, hour_3
            FROM night_stations
        """)
        
        stations_result = await db.execute(stations_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        # 2단계: MV에서 구 전체 심야시간 통계 조회 (훨씬 빠름)
        district_stats_query = text("""
            SELECT 
                SUM(total_ride) as district_night_total,
                COUNT(DISTINCT station_id) as total_stations
            FROM mv_station_hourly_patterns
            WHERE month_date = :analysis_month
              AND district_name = :district_name
              AND hour IN (23, 0, 1, 2, 3)
        """)
        
        district_stats_result = await db.execute(district_stats_query, {
            "district_name": district_name,
            "analysis_month": analysis_month
        })
        
        district_stats = district_stats_result.fetchone()
        district_night_total = district_stats.district_night_total or 1
        total_stations = district_stats.total_stations or 1
        
        # 구 평균 정류장당 심야 교통량
        district_avg_per_station = district_night_total / total_stations
        
        # 시간대별 데이터는 이미 1단계에서 조회 완료 (3개 쿼리 → 2개로 최적화!)
        
        # 3단계: 최종 결과 조합
        final_stations = []
        for row in stations_result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                district_name=row.district_name,
                administrative_dong=row.administrative_dong
            )
            
            total_night_ride = int(row.total_night_ride or 0)
            
            # vs_district_avg 계산 (구 평균 정류장 대비 배수)
            vs_district_avg = total_night_ride / district_avg_per_station if district_avg_per_station > 0 else 0.0
            
            # 시간대별 승차량 (이미 1단계에서 조회됨)
            night_hours_traffic = [
                int(row.hour_23 or 0),  # 23시
                int(row.hour_0 or 0),    # 0시  
                int(row.hour_1 or 0),    # 1시
                int(row.hour_2 or 0),    # 2시
                int(row.hour_3 or 0)     # 3시
            ]
            
            final_stations.append(NightDemandStationSchema(
                station=station_info,
                total_night_ride=total_night_ride,
                night_hours_traffic=night_hours_traffic,
                vs_district_avg=round(vs_district_avg, 1)
            ))
            
        return final_stations

    async def get_rush_hour_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> RushHourStationSchema:
        """3. 출퇴근 시간대 고수요 정류장 분석 (06-08, 17-19시)
        
        MV 활용한 최적화된 비즈니스 로직:
        1단계: 오전 러시아워 TOP N (06-08시)
        2단계: 오후 러시아워 TOP N (17-19시)
        3단계: 구 전체 러시아워 통계
        4단계: vs_district_avg 계산
        """
        
        # 1단계: 오전 러시아워 TOP N 정류장 (MV 활용)
        morning_query = text("""
            WITH morning_rush AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    -- 오전 러시아워 총 승차인원
                    SUM(CASE WHEN hour IN (6, 7, 8) THEN total_ride ELSE 0 END) as total_morning_rush,
                    -- 시간대별 승차량
                    SUM(CASE WHEN hour = 6 THEN total_ride ELSE 0 END) as hour_6,
                    SUM(CASE WHEN hour = 7 THEN total_ride ELSE 0 END) as hour_7,
                    SUM(CASE WHEN hour = 8 THEN total_ride ELSE 0 END) as hour_8
                FROM mv_station_hourly_patterns
                WHERE month_date = :analysis_month
                  AND district_name = :district_name
                  AND day_type = 'weekday'  -- 평일만
                  AND hour IN (6, 7, 8)
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong
                HAVING SUM(CASE WHEN hour IN (6, 7, 8) THEN total_ride ELSE 0 END) > 0
                ORDER BY total_morning_rush DESC
                LIMIT :top_n
            )
            SELECT 
                station_id as node_id,
                station_name as node_name,
                longitude,
                latitude,
                district_name,
                administrative_dong,
                total_morning_rush,
                hour_6, hour_7, hour_8
            FROM morning_rush
        """)
        
        morning_result = await db.execute(morning_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        # 2단계: 오후 러시아워 TOP N 정류장 (MV 활용)
        evening_query = text("""
            WITH evening_rush AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    -- 오후 러시아워 총 승차인원
                    SUM(CASE WHEN hour IN (17, 18, 19) THEN total_ride ELSE 0 END) as total_evening_rush,
                    -- 시간대별 승차량
                    SUM(CASE WHEN hour = 17 THEN total_ride ELSE 0 END) as hour_17,
                    SUM(CASE WHEN hour = 18 THEN total_ride ELSE 0 END) as hour_18,
                    SUM(CASE WHEN hour = 19 THEN total_ride ELSE 0 END) as hour_19
                FROM mv_station_hourly_patterns
                WHERE month_date = :analysis_month
                  AND district_name = :district_name
                  AND day_type = 'weekday'  -- 평일만
                  AND hour IN (17, 18, 19)
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong
                HAVING SUM(CASE WHEN hour IN (17, 18, 19) THEN total_ride ELSE 0 END) > 0
                ORDER BY total_evening_rush DESC
                LIMIT :top_n
            )
            SELECT 
                station_id as node_id,
                station_name as node_name,
                longitude,
                latitude,
                district_name,
                administrative_dong,
                total_evening_rush,
                hour_17, hour_18, hour_19
            FROM evening_rush
        """)
        
        evening_result = await db.execute(evening_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        # 3단계: 구 전체 러시아워 통계 (vs_district_avg 계산용)
        district_stats_query = text("""
            SELECT 
                -- 오전 러시아워
                SUM(CASE WHEN hour IN (6, 7, 8) THEN total_ride ELSE 0 END) as district_morning_total,
                COUNT(DISTINCT CASE WHEN hour IN (6, 7, 8) THEN station_id END) as morning_stations,
                -- 오후 러시아워
                SUM(CASE WHEN hour IN (17, 18, 19) THEN total_ride ELSE 0 END) as district_evening_total,
                COUNT(DISTINCT CASE WHEN hour IN (17, 18, 19) THEN station_id END) as evening_stations
            FROM mv_station_hourly_patterns
            WHERE month_date = :analysis_month
              AND district_name = :district_name
              AND day_type = 'weekday'
              AND hour IN (6, 7, 8, 17, 18, 19)
        """)
        
        district_stats_result = await db.execute(district_stats_query, {
            "district_name": district_name,
            "analysis_month": analysis_month
        })
        
        district_stats = district_stats_result.fetchone()
        
        # 구 평균 정류장당 러시아워 교통량
        district_morning_avg = (district_stats.district_morning_total or 1) / (district_stats.morning_stations or 1)
        district_evening_avg = (district_stats.district_evening_total or 1) / (district_stats.evening_stations or 1)
        
        # 4단계: 오전 러시아워 정류장 처리
        morning_stations = []
        for row in morning_result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                district_name=row.district_name,
                administrative_dong=row.administrative_dong
            )
            
            total_morning = int(row.total_morning_rush or 0)
            morning_hours_traffic = [
                int(row.hour_6 or 0),
                int(row.hour_7 or 0),
                int(row.hour_8 or 0)
            ]
            
            # vs_district_avg 계산
            vs_district_avg = total_morning / district_morning_avg if district_morning_avg > 0 else 0.0
            
            morning_stations.append(MorningRushStationSchema(
                station=station_info,
                total_morning_rush=total_morning,
                morning_hours_traffic=morning_hours_traffic,
                vs_district_avg=round(vs_district_avg, 1)
            ))
        
        # 5단계: 오후 러시아워 정류장 처리
        evening_stations = []
        for row in evening_result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                district_name=row.district_name,
                administrative_dong=row.administrative_dong
            )
            
            total_evening = int(row.total_evening_rush or 0)
            evening_hours_traffic = [
                int(row.hour_17 or 0),
                int(row.hour_18 or 0),
                int(row.hour_19 or 0)
            ]
            
            # vs_district_avg 계산
            vs_district_avg = total_evening / district_evening_avg if district_evening_avg > 0 else 0.0
            
            evening_stations.append(EveningRushStationSchema(
                station=station_info,
                total_evening_rush=total_evening,
                evening_hours_traffic=evening_hours_traffic,
                vs_district_avg=round(vs_district_avg, 1)
            ))
        
        # 최종 반환
        return RushHourStationSchema(
            morning_rush=morning_stations,
            evening_rush=evening_stations
        )

    async def get_lunch_time_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> List[LunchTimeStationSchema]:
        """4. 점심시간 특화 정류장 분석 (11-13시 하차 집중)
        
        MV 활용한 최적화된 비즈니스 로직:
        1단계: mv_station_hourly_patterns에서 점심시간 TOP N 선별 + 시간대별 분석
        2단계: 구 전체 점심시간 통계
        3단계: vs_district_avg 계산
        """
        
        # 1단계: MV에서 점심시간 TOP N 정류장 + 시간대별 데이터 한번에 조회
        stations_query = text("""
            WITH lunch_stations AS (
                SELECT 
                    station_id,
                    station_name,
                    longitude,
                    latitude,
                    district_name,
                    administrative_dong,
                    -- 점심시간 총 하차인원
                    SUM(CASE WHEN hour IN (11, 12, 13) THEN total_alight ELSE 0 END) as total_lunch_alight,
                    -- 시간대별 하차량 (피벗)
                    SUM(CASE WHEN hour = 11 THEN total_alight ELSE 0 END) as hour_11,
                    SUM(CASE WHEN hour = 12 THEN total_alight ELSE 0 END) as hour_12,
                    SUM(CASE WHEN hour = 13 THEN total_alight ELSE 0 END) as hour_13
                FROM mv_station_hourly_patterns
                WHERE month_date = :analysis_month
                  AND district_name = :district_name
                  AND day_type = 'weekday'  -- 평일만
                  AND hour IN (11, 12, 13)
                GROUP BY station_id, station_name, longitude, latitude, district_name, administrative_dong
                HAVING SUM(CASE WHEN hour IN (11, 12, 13) THEN total_alight ELSE 0 END) > 0
                ORDER BY total_lunch_alight DESC
                LIMIT :top_n
            )
            SELECT 
                station_id as node_id,
                station_name as node_name,
                longitude,
                latitude,
                district_name,
                administrative_dong,
                total_lunch_alight,
                hour_11, hour_12, hour_13
            FROM lunch_stations
        """)
        
        stations_result = await db.execute(stations_query, {
            "district_name": district_name,
            "analysis_month": analysis_month,
            "top_n": top_n
        })
        
        # 2단계: MV에서 구 전체 점심시간 통계 조회 (vs_district_avg 계산용)
        district_stats_query = text("""
            SELECT 
                SUM(total_alight) as district_lunch_total,
                COUNT(DISTINCT station_id) as total_stations
            FROM mv_station_hourly_patterns
            WHERE month_date = :analysis_month
              AND district_name = :district_name
              AND day_type = 'weekday'
              AND hour IN (11, 12, 13)
        """)
        
        district_stats_result = await db.execute(district_stats_query, {
            "district_name": district_name,
            "analysis_month": analysis_month
        })
        
        district_stats = district_stats_result.fetchone()
        district_lunch_total = district_stats.district_lunch_total or 1
        total_stations = district_stats.total_stations or 1
        
        # 구 평균 정류장당 점심시간 하차량
        district_avg_per_station = district_lunch_total / total_stations
        
        # 3단계: 최종 결과 조합
        final_stations = []
        for row in stations_result:
            station_info = StationInfoSchema(
                station_id=row.node_id,
                station_name=row.node_name,
                latitude=float(row.latitude),
                longitude=float(row.longitude),
                district_name=row.district_name,
                administrative_dong=row.administrative_dong
            )
            
            total_lunch_alight = int(row.total_lunch_alight or 0)
            
            # vs_district_avg 계산 (구 평균 정류장 대비 배수)
            vs_district_avg = total_lunch_alight / district_avg_per_station if district_avg_per_station > 0 else 0.0
            
            # 시간대별 하차량 (이미 1단계에서 조회됨)
            lunch_hours_alight = [
                int(row.hour_11 or 0),  # 11시
                int(row.hour_12 or 0),  # 12시
                int(row.hour_13 or 0)   # 13시
            ]
            
            final_stations.append(LunchTimeStationSchema(
                station=station_info,
                total_lunch_alight=total_lunch_alight,
                lunch_hours_alight=lunch_hours_alight,
                vs_district_avg=round(vs_district_avg, 1)
            ))
            
        return final_stations




    async def get_area_type_analysis(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> AreaTypeAnalysisSchema:
        """5. 지역 특성별 정류장 분석 (주거지역/업무지역 불균형 분석)"""
        
        # MV를 활용한 통합 쿼리로 주거지역/업무지역 동시 분석 (서브쿼리로 ORDER BY + LIMIT 적용)
        combined_query = text("""
            WITH rush_hour_stats AS (
                SELECT 
                    shp.station_id,
                    shp.station_name,
                    shp.latitude,
                    shp.longitude,
                    shp.district_name,
                    shp.administrative_dong,
                    -- 출근시간대 (6-9시) 승차/하차 (평일만)
                    SUM(CASE WHEN shp.hour IN (6,7,8,9) AND shp.day_type = 'weekday' THEN shp.total_ride ELSE 0 END) as morning_ride,
                    SUM(CASE WHEN shp.hour IN (6,7,8,9) AND shp.day_type = 'weekday' THEN shp.total_alight ELSE 0 END) as morning_alight,
                    -- 퇴근시간대 (17-19시) 승차/하차 (평일만)
                    SUM(CASE WHEN shp.hour IN (17,18,19) AND shp.day_type = 'weekday' THEN shp.total_ride ELSE 0 END) as evening_ride,
                    SUM(CASE WHEN shp.hour IN (17,18,19) AND shp.day_type = 'weekday' THEN shp.total_alight ELSE 0 END) as evening_alight,
                    -- 총 교통량 (러시아워 평일만)
                    SUM(CASE WHEN shp.hour IN (6,7,8,9,17,18,19) AND shp.day_type = 'weekday' THEN shp.total_traffic ELSE 0 END) as total_traffic
                FROM mv_station_hourly_patterns shp
                WHERE shp.month_date = :analysis_month
                  AND shp.district_name = :district_name
                  AND shp.hour IN (6,7,8,9,17,18,19)  -- 러시아워만
                  AND shp.day_type = 'weekday'  -- 평일만
                GROUP BY shp.station_id, shp.station_name, shp.latitude, shp.longitude, 
                         shp.district_name, shp.administrative_dong
                HAVING SUM(CASE WHEN shp.hour IN (6,7,8,9,17,18,19) AND shp.day_type = 'weekday' THEN shp.total_traffic ELSE 0 END) >= 1000  -- 1000명 이상 필터링
            ),
            area_classification AS (
                SELECT *,
                    -- 주거지역 불균형 비율: (출근승차/출근하차) × (퇴근하차/퇴근승차)
                    CASE 
                        WHEN morning_alight > 0 AND evening_ride > 0 THEN 
                            (morning_ride::numeric / morning_alight::numeric) * (evening_alight::numeric / evening_ride::numeric)
                        ELSE 0 
                    END as residential_imbalance,
                    -- 업무지역 불균형 비율: (출근하차/출근승차) × (퇴근승차/퇴근하차)
                    CASE 
                        WHEN morning_ride > 0 AND evening_alight > 0 THEN 
                            (morning_alight::numeric / morning_ride::numeric) * (evening_ride::numeric / evening_alight::numeric)
                        ELSE 0 
                    END as business_imbalance
                FROM rush_hour_stats
            ),
            -- 서브쿼리로 각각 ORDER BY + LIMIT 적용
            residential_top AS (
                SELECT 'residential' as area_type, 
                       station_id, station_name, latitude, longitude, district_name, administrative_dong,
                       morning_ride, morning_alight, evening_ride, evening_alight, total_traffic,
                       ROUND(residential_imbalance, 3) as imbalance_ratio
                FROM area_classification
                WHERE residential_imbalance > 1.0
                ORDER BY residential_imbalance DESC
                LIMIT :top_n
            ),
            business_top AS (
                SELECT 'business' as area_type,
                       station_id, station_name, latitude, longitude, district_name, administrative_dong,
                       morning_ride, morning_alight, evening_ride, evening_alight, total_traffic,
                       ROUND(business_imbalance, 3) as imbalance_ratio
                FROM area_classification
                WHERE business_imbalance > 1.0
                ORDER BY business_imbalance DESC
                LIMIT :top_n
            )
            -- 주거지역과 업무지역 결과 UNION
            SELECT * FROM residential_top
            UNION ALL
            SELECT * FROM business_top
        """)
        
        try:
            # 통합 쿼리 실행
            result = await db.execute(
                combined_query, 
                {
                    "analysis_month": analysis_month,
                    "district_name": district_name,
                    "top_n": top_n
                }
            )
            all_rows = result.fetchall()
            
            # 결과를 주거지역/업무지역으로 분리
            residential_stations = []
            business_stations = []
            
            for row in all_rows:
                station_info = StationInfoSchema(
                    station_id=row.station_id,
                    station_name=row.station_name,
                    latitude=float(row.latitude),
                    longitude=float(row.longitude),
                    district_name=row.district_name,
                    administrative_dong=row.administrative_dong or "정보없음"
                )
                
                if row.area_type == 'residential':
                    residential_station = ResidentialAreaStationSchema(
                        station=station_info,
                        morning_ride=int(row.morning_ride),
                        morning_alight=int(row.morning_alight),
                        evening_ride=int(row.evening_ride),
                        evening_alight=int(row.evening_alight),
                        total_traffic=int(row.total_traffic),
                        imbalance_ratio=float(row.imbalance_ratio)
                    )
                    residential_stations.append(residential_station)
                    
                elif row.area_type == 'business':
                    business_station = BusinessAreaStationSchema(
                        station=station_info,
                        morning_ride=int(row.morning_ride),
                        morning_alight=int(row.morning_alight),
                        evening_ride=int(row.evening_ride),
                        evening_alight=int(row.evening_alight),
                        total_traffic=int(row.total_traffic),
                        imbalance_ratio=float(row.imbalance_ratio)
                    )
                    business_stations.append(business_station)
            
            self.logger.info(
                f"Area type analysis completed: {len(residential_stations)} residential, "
                f"{len(business_stations)} business stations for {district_name}"
            )
            
            return AreaTypeAnalysisSchema(
                residential_stations=residential_stations,
                business_stations=business_stations
            )
            
        except Exception as e:
            self.logger.error(f"Error in area type analysis: {e}")
            # 빈 결과 반환
            return AreaTypeAnalysisSchema(
                residential_stations=[],
                business_stations=[]
            )


    async def get_underutilized_stations(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 10
    ) -> List[UnderutilizedStationSchema]:
        """6. 저활용 정류장 분석 (운영 최적화 대상)
        
        비즈니스 로직:
        - 구별 하위 25% 교통량 기준 선별
        - 연결 노선수와 교통량 효율성 분석
        - 운영비용 대비 효과 측정 및 최적화 전략 제시
        """
        
        # MV를 활용한 저활용 정류장 분석 쿼리 (간소화)
        underutilized_query = text("""
            WITH station_stats AS (
                SELECT 
                    shp.station_id,
                    shp.station_name,
                    shp.latitude,
                    shp.longitude,
                    shp.district_name,
                    shp.administrative_dong,
                    ROUND(AVG(shp.total_traffic), 0) as avg_daily_passengers,
                    MAX(shp.total_traffic) as max_daily_passengers,
                    MAX(shp.route_count) as connecting_routes,
                    SUM(shp.total_traffic) as total_monthly_traffic
                FROM mv_station_hourly_patterns shp
                WHERE shp.month_date = :analysis_month
                  AND shp.district_name = :district_name
                GROUP BY shp.station_id, shp.station_name, shp.latitude, shp.longitude, 
                         shp.district_name, shp.administrative_dong
            ),
            district_benchmark AS (
                SELECT 
                    AVG(avg_daily_passengers) as district_avg_daily,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total_monthly_traffic) as bottom_25_percentile
                FROM station_stats
            )
            SELECT 
                ss.station_id,
                ss.station_name,
                ss.latitude,
                ss.longitude,
                ss.district_name,
                ss.administrative_dong,
                ss.avg_daily_passengers,
                ss.max_daily_passengers,
                COALESCE(ss.connecting_routes, 1) as connecting_routes,
                ROUND((ss.avg_daily_passengers / db.district_avg_daily) * 100, 1) as utilization_rate,
                ROUND(ss.avg_daily_passengers::numeric / GREATEST(COALESCE(ss.connecting_routes, 1), 1), 1) as efficiency_score
            FROM station_stats ss
            CROSS JOIN district_benchmark db
            WHERE ss.total_monthly_traffic <= db.bottom_25_percentile
              AND ss.avg_daily_passengers > 0
            ORDER BY ss.avg_daily_passengers ASC, efficiency_score ASC
            LIMIT :top_n
        """)
        
        try:
            # 쿼리 실행
            result = await db.execute(
                underutilized_query,
                {
                    "analysis_month": analysis_month,
                    "district_name": district_name,
                    "top_n": top_n
                }
            )
            all_rows = result.fetchall()
            
            # 결과 변환
            underutilized_stations = []
            for row in all_rows:
                station_info = StationInfoSchema(
                    station_id=row.station_id,
                    station_name=row.station_name,
                    latitude=float(row.latitude),
                    longitude=float(row.longitude),
                    district_name=row.district_name,
                    administrative_dong=row.administrative_dong or "정보없음"
                )
                
                underutilized_station = UnderutilizedStationSchema(
                    station=station_info,
                    avg_daily_passengers=int(row.avg_daily_passengers),
                    max_daily_passengers=int(row.max_daily_passengers),
                    connecting_routes=int(row.connecting_routes or 1),
                    utilization_rate=float(row.utilization_rate),
                    efficiency_score=float(row.efficiency_score)
                )
                underutilized_stations.append(underutilized_station)
            
            self.logger.info(
                f"Underutilized stations analysis completed: {len(underutilized_stations)} stations for {district_name}"
            )
            
            return underutilized_stations
            
        except Exception as e:
            self.logger.error(f"Error in underutilized stations analysis: {e}")
            return []


    async def get_integrated_anomaly_patterns(
        self,
        db: AsyncSession,
        district_name: str,
        analysis_month: date,
        top_n: int = 5
    ) -> IntegratedAnomalyPatternResponse:
        """통합 교통 특이패턴 분석 (6개 패턴 모두 호출)"""
        
        from datetime import datetime
        
        try:
            self.logger.info(f"Starting integrated analysis for {district_name} - {analysis_month}")
            
            # 6개 개별 패턴 분석 순차 호출 (DB 세션 동시성 문제 해결)
            weekend_stations = await self.get_weekend_dominant_stations(db, district_name, analysis_month, top_n)
            night_stations = await self.get_night_demand_stations(db, district_name, analysis_month, top_n)
            rush_stations = await self.get_rush_hour_stations(db, district_name, analysis_month, top_n)
            lunch_stations = await self.get_lunch_time_stations(db, district_name, analysis_month, top_n)
            area_analysis = await self.get_area_type_analysis(db, district_name, analysis_month, top_n)
            underutilized_stations = await self.get_underutilized_stations(db, district_name, analysis_month, top_n)
            
            # 통합 응답 생성
            integrated_response = IntegratedAnomalyPatternResponse(
                district_name=district_name,
                analysis_month=analysis_month.strftime("%Y-%m"),
                generated_at=datetime.now().isoformat(),
                weekend_dominant_stations=weekend_stations,
                night_demand_stations=night_stations,
                rush_hour_stations=rush_stations,
                lunch_time_stations=lunch_stations,
                area_type_analysis=area_analysis,
                underutilized_stations=underutilized_stations
            )
            
            self.logger.info(
                f"Integrated analysis completed for {district_name}: "
                f"weekend({len(weekend_stations)}), night({len(night_stations)}), "
                f"rush_hour(morning:{len(rush_stations.morning_rush)}, evening:{len(rush_stations.evening_rush)}), "
                f"lunch({len(lunch_stations)}), "
                f"area(residential:{len(area_analysis.residential_stations)}, business:{len(area_analysis.business_stations)}), "
                f"underutilized({len(underutilized_stations)})"
            )
            
            return integrated_response
            
        except Exception as e:
            self.logger.error(f"Error in integrated analysis: {e}")
            # 빈 결과 반환
            from datetime import datetime
            return IntegratedAnomalyPatternResponse(
                district_name=district_name,
                analysis_month=analysis_month.strftime("%Y-%m"),
                generated_at=datetime.now().isoformat(),
                weekend_dominant_stations=[],
                night_demand_stations=[],
                rush_hour_stations=RushHourStationSchema(morning_rush=[], evening_rush=[]),
                lunch_time_stations=[],
                area_type_analysis=AreaTypeAnalysisSchema(residential_stations=[], business_stations=[]),
                underutilized_stations=[]
            )