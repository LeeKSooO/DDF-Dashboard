"""
서울시 교통량 히트맵 서비스
구별/정류장별 교통량 집계 및 지도 경계 데이터 제공
"""

from typing import List, Optional, Dict
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
import statistics
import json

from app.schemas.heatmap import (
    SeoulHeatmapSchema,
    DistrictTrafficSchema,
    StationTrafficSchema,
    CoordinateSchema,
    BoundarySchema,
    HeatmapStatisticsSchema
)
from app.utils.response import (
    bad_request_response,
    handle_database_error
)
from app.core.redis_client import cache_result

logger = logging.getLogger(__name__)


class HeatmapService:
    """히트맵 컴포넌트 서비스"""
    
    def __init__(self):
        pass
    
    @cache_result(key_prefix="heatmap:seoul", use_month_ttl=True)
    async def get_seoul_heatmap(
        self,
        db: AsyncSession,
        analysis_month: date,
        include_station_details: bool = True,
        min_traffic_threshold: Optional[int] = None
    ) -> SeoulHeatmapSchema:
        """서울시 교통량 히트맵 데이터 조회"""
        try:
            # 입력 유효성 검사
            self._validate_inputs(analysis_month)
            
            logger.info(f"Getting heatmap data for {analysis_month}")
            
            # 1. 서울시 경계 조회 (최적화)
            seoul_boundary = await self._get_seoul_boundary_optimized(db)
            
            # 2. 구별 교통량 집계 조회 (N+1 문제 해결)
            districts_data = await self._get_districts_traffic_data_optimized(
                db, analysis_month, include_station_details, min_traffic_threshold
            )
            
            # 3. 통계 계산
            statistics_data = self._calculate_statistics(districts_data)
            
            # 4. 응답 구성
            return SeoulHeatmapSchema(
                analysis_month=analysis_month.strftime("%Y-%m"),
                seoul_boundary=seoul_boundary,
                districts=districts_data,
                statistics=statistics_data,
                data_period=f"{analysis_month.strftime('%Y-%m')}-16 ~ {analysis_month.strftime('%Y-%m')}-31",
                last_updated=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error in get_seoul_heatmap: {e}")
            raise handle_database_error(e)
    
    def _validate_inputs(self, analysis_month: date):
        """입력 파라미터 유효성 검사"""
        # 날짜 형식은 FastAPI가 자동 검증
        pass
    
    async def _get_seoul_boundary_optimized(self, db: AsyncSession) -> BoundarySchema:
        """서울시 경계 좌표 조회 (최적화: 정확한 조건 사용)"""
        try:
            # PostGIS 쿼리 단순화
            boundary_query = text("""
                SELECT ST_AsGeoJSON(ST_ExteriorRing(ST_Union(geometry))) as boundary
                FROM admin_boundaries 
                WHERE sidonm = '서울특별시'
                LIMIT 1
            """)
            
            result = await db.execute(boundary_query)
            boundary_row = result.fetchone()
            
            if boundary_row and boundary_row[0]:
                import json
                geojson = json.loads(boundary_row[0])
                
                # GeoJSON coordinates를 CoordinateSchema로 변환
                coordinates = []
                if geojson.get('coordinates'):
                    for coord_pair in geojson['coordinates']:
                        # GeoJSON은 [lng, lat] 순서
                        coordinates.append(CoordinateSchema(
                            lat=coord_pair[1], 
                            lng=coord_pair[0]
                        ))
                
                return BoundarySchema(coordinates=[coordinates])
            
        except Exception as e:
            logger.warning(f"Failed to get Seoul boundary from DB: {e}")
        
        # 실패 시 더미 경계 데이터 반환
        return BoundarySchema(
            coordinates=[[
                CoordinateSchema(lat=37.4290, lng=126.7340),  # 남서쪽
                CoordinateSchema(lat=37.4290, lng=127.2690),  # 남동쪽  
                CoordinateSchema(lat=37.7010, lng=127.2690),  # 북동쪽
                CoordinateSchema(lat=37.7010, lng=126.7340),  # 북서쪽
                CoordinateSchema(lat=37.4290, lng=126.7340)   # 닫기
            ]]
        )
    
    async def _get_districts_traffic_data(
        self,
        db: AsyncSession,
        analysis_month: date,
        include_station_details: bool,
        min_traffic_threshold: Optional[int]
    ) -> List[DistrictTrafficSchema]:
        """구별 교통량 데이터 조회 (mv_district_monthly_traffic 기반)"""
        try:
            # 최적화된 Materialized View 쿼리
            district_query = text("""
                SELECT 
                    district_code,
                    district_name,
                    total_traffic,
                    total_ride,
                    total_alight,
                    station_count,
                    avg_daily_traffic
                FROM mv_district_monthly_traffic
                WHERE month_date = :month_date
                    AND total_traffic > COALESCE(:min_threshold, 0)
                ORDER BY total_traffic DESC
            """)
            
            params = {
                "month_date": analysis_month,
                "min_threshold": min_traffic_threshold or 0
            }
            
            logger.info(f"Executing district query with params: {params}")
            result = await db.execute(district_query, params)
            district_rows = result.fetchall()
            
            logger.info(f"Found {len(district_rows)} districts")
            
            districts = []
            for idx, row in enumerate(district_rows):
                # 구별 기본 정보
                district_code = str(row[0]) if row[0] else "unknown"
                district_name = row[1] or "알 수 없음"
                total_traffic = int(row[2] or 0)
                total_ride = int(row[3] or 0) 
                total_alight = int(row[4] or 0)
                station_count = int(row[5] or 0)
                daily_average = float(row[6] or 0)
                
                logger.info(f"District {district_name}: traffic={total_traffic}, stations={station_count}")
                
                # 구 경계 데이터
                logger.info(f"About to call _get_district_boundary for {district_name}")
                boundary = await self._get_district_boundary(db, district_name)
                logger.info(f"Got boundary for {district_name}: {len(boundary.coordinates[0]) if boundary.coordinates else 0} coordinates")
                
                # 정류장별 데이터
                stations = []
                if include_station_details:
                    stations = await self._get_stations_in_district(
                        db, analysis_month, district_name, min_traffic_threshold
                    )
                
                # 교통량 밀도 계산
                traffic_density = total_traffic / station_count if station_count > 0 else 0
                
                district = DistrictTrafficSchema(
                    district_code=district_code,
                    district_name=district_name,
                    boundary=boundary,
                    total_traffic=total_traffic,
                    total_ride=total_ride,
                    total_alight=total_alight,
                    daily_average=daily_average,
                    station_count=station_count,
                    stations=stations,
                    traffic_rank=idx + 1,  # 순위 (ORDER BY total_traffic DESC)
                    traffic_density=round(traffic_density, 2)
                )
                
                districts.append(district)
            
            return districts
            
        except Exception as e:
            logger.error(f"Error in _get_districts_traffic_data: {e}")
            raise
    
    async def _get_district_boundary(self, db: AsyncSession, district_name: str) -> BoundarySchema:
        """구별 경계 좌표 조회"""
        logger.info(f"Getting boundary for district: {district_name}")
        try:
            # PostGIS 쿼리 단순화
            boundary_query = text("""
                SELECT ST_AsGeoJSON(ST_ExteriorRing((ST_Dump(geometry)).geom)) as boundary
                FROM admin_boundaries 
                WHERE sggnm = :district_name AND sidonm = '서울특별시'
                LIMIT 1
            """)
            
            result = await db.execute(boundary_query, {"district_name": district_name})
            boundary_row = result.fetchone()
            
            logger.info(f"Boundary query result for {district_name}: {boundary_row}")
            
            if boundary_row and boundary_row[0]:
                import json
                geojson = json.loads(boundary_row[0])
                
                # GeoJSON coordinates를 CoordinateSchema로 변환
                coordinates = []
                if geojson.get('coordinates'):
                    for coord_pair in geojson['coordinates']:
                        # GeoJSON은 [lng, lat] 순서
                        coordinates.append(CoordinateSchema(
                            lat=coord_pair[1], 
                            lng=coord_pair[0]
                        ))
                
                return BoundarySchema(coordinates=[coordinates])
            
        except Exception as e:
            logger.error(f"Failed to get district boundary for {district_name}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        # 실패 시 더미 경계 데이터 반환
        return BoundarySchema(
            coordinates=[[
                CoordinateSchema(lat=37.4800, lng=126.8800),
                CoordinateSchema(lat=37.4800, lng=126.9200), 
                CoordinateSchema(lat=37.5200, lng=126.9200),
                CoordinateSchema(lat=37.5200, lng=126.8800),
                CoordinateSchema(lat=37.4800, lng=126.8800)
            ]]
        )
    
    async def _get_stations_in_district(
        self,
        db: AsyncSession,
        analysis_month: date,
        district_name: str,
        min_traffic_threshold: Optional[int]
    ) -> List[StationTrafficSchema]:
        """구 내 정류장별 교통량 데이터 조회"""
        try:
            station_query = text("""
                SELECT 
                    station_id,
                    station_name,
                    latitude,
                    longitude,
                    total_traffic,
                    total_ride,
                    total_alight,
                    daily_average
                FROM mv_station_monthly_traffic
                WHERE month_date = :month_date
                    AND district_name = :district_name
                    AND total_traffic > COALESCE(:min_threshold, 0)
                ORDER BY total_traffic DESC
            """)
            
            params = {
                "month_date": analysis_month,
                "district_name": district_name,
                "min_threshold": min_traffic_threshold or 0
            }
            
            result = await db.execute(station_query, params)
            station_rows = result.fetchall()
            
            logger.info(f"Found {len(station_rows)} stations in {district_name}")
            
            stations = []
            for row in station_rows:
                station_id = str(row[0])
                station_name = row[1] or "알 수 없음"
                latitude = float(row[2]) if row[2] else 37.5665
                longitude = float(row[3]) if row[3] else 126.9780
                total_traffic = int(row[4] or 0)
                total_ride = int(row[5] or 0)
                total_alight = int(row[6] or 0) 
                daily_average = float(row[7] or 0)
                
                station = StationTrafficSchema(
                    station_id=station_id,
                    station_name=station_name,
                    coordinate=CoordinateSchema(lat=latitude, lng=longitude),
                    total_traffic=total_traffic,
                    total_ride=total_ride,
                    total_alight=total_alight,
                    daily_average=round(daily_average, 1)
                )
                
                stations.append(station)
            
            return stations
            
        except Exception as e:
            logger.error(f"Error in _get_stations_in_district: {e}")
            raise
    
    def _calculate_statistics(self, districts: List[DistrictTrafficSchema]) -> HeatmapStatisticsSchema:
        """히트맵 통계 계산"""
        if not districts:
            return HeatmapStatisticsSchema(
                max_district_traffic=0,
                min_district_traffic=0,
                max_station_traffic=0,
                min_station_traffic=0,
                total_seoul_traffic=0,
                total_stations=0,
                district_traffic_quartiles=[0, 0, 0],
                station_traffic_quartiles=[0, 0, 0]
            )
        
        # 구별 교통량 통계
        district_traffics = [d.total_traffic for d in districts]
        max_district = max(district_traffics)
        min_district = min(district_traffics) 
        total_seoul = sum(district_traffics)
        
        # 정류장별 교통량 통계
        all_station_traffics = []
        total_stations = 0
        for district in districts:
            total_stations += len(district.stations)
            all_station_traffics.extend([s.total_traffic for s in district.stations])
        
        max_station = max(all_station_traffics) if all_station_traffics else 0
        min_station = min(all_station_traffics) if all_station_traffics else 0
        
        # 사분위수 계산 
        district_quartiles = self._calculate_quartiles(district_traffics)
        station_quartiles = self._calculate_quartiles(all_station_traffics) if all_station_traffics else [0, 0, 0]
        
        return HeatmapStatisticsSchema(
            max_district_traffic=max_district,
            min_district_traffic=min_district,
            max_station_traffic=max_station,
            min_station_traffic=min_station,
            total_seoul_traffic=total_seoul,
            total_stations=total_stations,
            district_traffic_quartiles=district_quartiles,
            station_traffic_quartiles=station_quartiles
        )
    
    def _calculate_quartiles(self, data: List[int]) -> List[int]:
        """사분위수 계산 (Q1, Q2, Q3)"""
        if not data:
            return [0, 0, 0]
        
        sorted_data = sorted(data)
        q1 = int(statistics.quantiles(sorted_data, n=4)[0])
        q2 = int(statistics.quantiles(sorted_data, n=4)[1]) 
        q3 = int(statistics.quantiles(sorted_data, n=4)[2])
        
        return [q1, q2, q3]
    
    async def _get_districts_traffic_data_optimized(
        self,
        db: AsyncSession,
        analysis_month: date,
        include_station_details: bool,
        min_traffic_threshold: Optional[int]
    ) -> List[DistrictTrafficSchema]:
        """구별 교통량 데이터 조회 (N+1 문제 해결)"""
        try:
            # 최적화된 Materialized View 쿼리 (N+1 문제 해결)
            district_query = text("""
                SELECT 
                    district_code,
                    district_name,
                    total_traffic,
                    total_ride,
                    total_alight,
                    station_count,
                    avg_daily_traffic
                FROM mv_district_monthly_traffic
                WHERE month_date = :month_date
                    AND total_traffic > COALESCE(:min_threshold, 0)
                ORDER BY total_traffic DESC
            """)
            
            params = {
                "month_date": analysis_month,
                "min_threshold": min_traffic_threshold or 0
            }
            
            logger.info(f"Executing optimized district query with params: {params}")
            result = await db.execute(district_query, params)
            district_rows = result.fetchall()
            
            logger.info(f"Found {len(district_rows)} districts")
            
            # 2. 모든 구 경계를 한 번에 조회 (N+1 해결)
            district_names = [row[1] for row in district_rows]
            boundaries_map = await self._get_all_district_boundaries(db, district_names)
            
            # 3. 정류장 상세 데이터를 한 번에 조회 (N+1 해결)
            stations_map = {}
            if include_station_details:
                stations_map = await self._get_all_stations_by_districts(
                    db, analysis_month, district_names, min_traffic_threshold
                )
            
            # 4. 결과 조합
            districts = []
            for idx, row in enumerate(district_rows):
                district_code = str(row[0]) if row[0] else "unknown"
                district_name = row[1] or "알 수 없음"
                total_traffic = int(row[2] or 0)
                total_ride = int(row[3] or 0) 
                total_alight = int(row[4] or 0)
                station_count = int(row[5] or 0)
                daily_average = float(row[6] or 0)
                
                boundary = boundaries_map.get(district_name, self._get_default_boundary())
                stations = stations_map.get(district_name, [])
                traffic_density = total_traffic / station_count if station_count > 0 else 0
                
                district = DistrictTrafficSchema(
                    district_code=district_code,
                    district_name=district_name,
                    boundary=boundary,
                    total_traffic=total_traffic,
                    total_ride=total_ride,
                    total_alight=total_alight,
                    daily_average=daily_average,
                    station_count=station_count,
                    stations=stations,
                    traffic_rank=idx + 1,
                    traffic_density=round(traffic_density, 2)
                )
                districts.append(district)
            
            return districts
            
        except Exception as e:
            logger.error(f"Error in _get_districts_traffic_data_optimized: {e}")
            raise
    
    async def _get_all_district_boundaries(
        self, 
        db: AsyncSession, 
        district_names: List[str]
    ) -> Dict[str, BoundarySchema]:
        """모든 구 경계를 한 번에 조회 (N+1 해결)"""
        try:
            if not district_names:
                return {}
            
            # PostGIS 쿼리 - MultiPolygon 처리를 위해 ST_Dump 사용
            boundary_query = text("""
                SELECT 
                    sggnm as district_name,
                    ST_AsGeoJSON(ST_ExteriorRing((ST_Dump(geometry)).geom)) as boundary
                FROM admin_boundaries 
                WHERE sggnm = ANY(:district_names) 
                    AND sidonm = '서울특별시'
            """)
            
            result = await db.execute(boundary_query, {"district_names": district_names})
            boundary_rows = result.fetchall()
            
            boundaries_map = {}
            for row in boundary_rows:
                district_name = row[0]
                if row[1]:
                    geojson = json.loads(row[1])
                    
                    coordinates = []
                    if geojson.get('coordinates'):
                        for coord_pair in geojson['coordinates']:
                            coordinates.append(CoordinateSchema(
                                lat=coord_pair[1], 
                                lng=coord_pair[0]
                            ))
                    
                    boundaries_map[district_name] = BoundarySchema(coordinates=[coordinates])
                else:
                    boundaries_map[district_name] = self._get_default_boundary()
            
            # 경계 데이터가 없는 구는 기본값 설정
            for district_name in district_names:
                if district_name not in boundaries_map:
                    boundaries_map[district_name] = self._get_default_boundary()
            
            logger.info(f"Loaded boundaries for {len(boundaries_map)} districts")
            return boundaries_map
            
        except Exception as e:
            logger.error(f"Error in _get_all_district_boundaries: {e}")
            # 트랜잭션 롤백
            try:
                await db.rollback()
            except:
                pass
            return {name: self._get_default_boundary() for name in district_names}
    
    async def _get_all_stations_by_districts(
        self,
        db: AsyncSession,
        analysis_month: date,
        district_names: List[str],
        min_traffic_threshold: Optional[int]
    ) -> Dict[str, List[StationTrafficSchema]]:
        """모든 구의 정류장 데이터를 한 번에 조회 (mv_station_monthly_traffic 기반, N+1 해결)"""
        try:
            if not district_names:
                return {}
            
            # 최적화된 Materialized View 쿼리
            station_query = text("""
                SELECT 
                    district_name,
                    station_id,
                    station_name,
                    latitude,
                    longitude,
                    total_traffic,
                    total_ride,
                    total_alight,
                    daily_average
                FROM mv_station_monthly_traffic
                WHERE month_date = :month_date
                    AND district_name = ANY(:district_names)
                    AND total_traffic > COALESCE(:min_threshold, 0)
                ORDER BY district_name, total_traffic DESC
            """)
            
            params = {
                "month_date": analysis_month,
                "district_names": district_names,
                "min_threshold": min_traffic_threshold or 0
            }
            
            # 트랜잭션 상태 확인 및 필요시 롤백
            try:
                result = await db.execute(station_query, params)
            except Exception as query_error:
                logger.error(f"Query execution failed, retrying: {query_error}")
                await db.rollback()
                # 재시도
                result = await db.execute(station_query, params)

            station_rows = result.fetchall()
            
            # 구별로 정류장 그룹화
            stations_map = {name: [] for name in district_names}
            
            for row in station_rows:
                district_name = row[0]
                station_id = str(row[1])
                station_name = row[2] or "알 수 없음"
                latitude = float(row[3]) if row[3] else 37.5665
                longitude = float(row[4]) if row[4] else 126.9780
                total_traffic = int(row[5] or 0)
                total_ride = int(row[6] or 0)
                total_alight = int(row[7] or 0)
                daily_average = float(row[8] or 0)
                
                station = StationTrafficSchema(
                    station_id=station_id,
                    station_name=station_name,
                    coordinate=CoordinateSchema(lat=latitude, lng=longitude),
                    total_traffic=total_traffic,
                    total_ride=total_ride,
                    total_alight=total_alight,
                    daily_average=round(daily_average, 1)
                )
                
                if district_name in stations_map:
                    stations_map[district_name].append(station)
            
            return stations_map
            
        except Exception as e:
            logger.error(f"Error in _get_all_stations_by_districts: {e}")
            return {name: [] for name in district_names}
    
    def _get_default_boundary(self) -> BoundarySchema:
        """기본 경계 데이터 반환"""
        return BoundarySchema(
            coordinates=[[
                CoordinateSchema(lat=37.4800, lng=126.8800),
                CoordinateSchema(lat=37.4800, lng=126.9200), 
                CoordinateSchema(lat=37.5200, lng=126.9200),
                CoordinateSchema(lat=37.5200, lng=126.8800),
                CoordinateSchema(lat=37.4800, lng=126.8800)
            ]]
        )