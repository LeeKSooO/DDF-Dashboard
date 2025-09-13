"""
OD 데이터 기반 DRT 도입 우선순위 분석 서비스
웹 대시보드에서 DRT 의사결정 지원을 위한 다양한 분석 정보 제공
"""

from typing import List, Optional
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from app.schemas.od import (
    DRTPriorityMatrixResponse,
    HighPriorityTransferSchema,
    HighDemandDirectRouteSchema,
    LowDemandLongDistanceSchema,
    TimeBasedDemandSchema,
    ODPairInfoSchema,
    DRTPriorityBreakdownSchema,
    TimeBasedOriginAnalysisSchema,
    DestinationStationSchema,
    TimeBasedOriginAnalysisResponse,
    DemandSupplyMismatchSchema,
    ODPairHourlyAnalysisSchema
)
from app.core.redis_client import cache_result

logger = logging.getLogger(__name__)


class ODService:
    """OD 데이터 기반 DRT 분석 서비스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_drt_priority_matrix(
        self,
        db: AsyncSession,
        analysis_month: date,
        top_n: int = 20
    ) -> DRTPriorityMatrixResponse:
        """
        DRT 도입 우선순위 매트릭스 분석
        
        Args:
            db: 데이터베이스 세션
            analysis_month: 분석 대상 월
            top_n: 상위 N개 결과
            
        Returns:
            DRT 우선순위 매트릭스 응답
        """
        try:
            self.logger.info(f"Starting DRT priority matrix analysis for {analysis_month}")
            
            # 고우선순위 환승 구간 (P1, P2) 조회
            high_priority_transfers = await self._get_high_priority_transfers(
                db, analysis_month, top_n
            )
            
            # 직행노선 부족 고수요 구간 (P3) 조회
            high_demand_direct_routes = await self._get_high_demand_direct_routes(
                db, analysis_month, top_n
            )
            
            # 저효율 구간 (P4) 조회
            low_efficiency_routes = await self._get_low_efficiency_routes(
                db, analysis_month, top_n
            )
            
            # 시간대별 분석
            time_based_analysis = await self._get_time_based_analysis(
                db, analysis_month
            )
            
            # 전체 요약 지표 계산
            summary_stats = await self._get_summary_statistics(db, analysis_month)
            
            # 우선순위별 분포 계산
            priority_distribution = await self._get_priority_distribution(db, analysis_month)
            
            return DRTPriorityMatrixResponse(
                analysis_month=analysis_month.strftime("%Y-%m"),
                generated_at=datetime.now().isoformat(),
                **summary_stats,
                priority_distribution=priority_distribution,
                high_priority_transfers=high_priority_transfers,
                high_demand_direct_routes=high_demand_direct_routes,
                low_efficiency_routes=low_efficiency_routes,
                time_based_analysis=time_based_analysis
            )
            
        except Exception as e:
            self.logger.error(f"Error in get_drt_priority_matrix: {str(e)}")
            raise

    @cache_result(key_prefix="od:p1_transfers", use_month_ttl=True)
    async def get_p1_transfer_routes(
        self,
        db: AsyncSession,
        analysis_month: date,
        top_n: int
    ) -> List[HighPriorityTransferSchema]:
        """P1 환승 필요 구간 조회 (기존 P1+P2 통합) - Updated"""
        
        query = """
        SELECT 
            from_station_id, from_station_name, from_station_num,
            to_station_id, to_station_name, to_station_num,
            from_district_name, to_district_name, avg_distance_km,
            daily_avg_passengers, ever_transfer_required,
            CASE 
                WHEN p1_score > 0 THEN 'P1_고수요_환승구간'
                WHEN p2_score > 0 THEN 'P1_저수요_환승구간'
            END as priority_category,
            (p1_score + p2_score) as priority_score
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month 
        AND (p1_score > 0 OR p2_score > 0)
        ORDER BY (p1_score + p2_score) DESC, daily_avg_passengers DESC
        LIMIT :top_n
        """
        
        result = await db.execute(text(query), {"analysis_month": analysis_month, "top_n": top_n})
        rows = result.fetchall()
        transfers = []
        
        for row in rows:
            od_pair = ODPairInfoSchema(
                from_station_id=row.from_station_id,
                from_station_name=row.from_station_name,
                from_station_num=row.from_station_num,
                to_station_id=row.to_station_id,
                to_station_name=row.to_station_name,
                to_station_num=row.to_station_num,
                from_district=row.from_district_name,
                to_district=row.to_district_name,
                distance_km=float(row.avg_distance_km)
            )
            
            transfers.append(HighPriorityTransferSchema(
                od_pair=od_pair,
                daily_demand=int(row.daily_avg_passengers),
                transfer_required=row.ever_transfer_required,
                priority_category=row.priority_category
            ))
        
        return transfers

    async def _get_priority_transfers(
        self,
        db: AsyncSession,
        analysis_month: date,
        top_n: int,
        priority_type: str
    ) -> List[HighPriorityTransferSchema]:
        """우선순위별 환승 구간 조회"""
        
        if priority_type == "p1":
            query = """
            SELECT 
                from_station_id, from_station_name, from_station_num,
                to_station_id, to_station_name, to_station_num,
                from_district_name, to_district_name, avg_distance_km,
                daily_avg_passengers, ever_transfer_required,
                'P1_최우선' as priority_category, p1_score as priority_score
            FROM mv_monthly_od_summary 
            WHERE DATE(analysis_month) = :analysis_month AND p1_score > 0
            ORDER BY p1_score DESC LIMIT :top_n
            """
        else:  # p2
            query = """
            SELECT 
                from_station_id, from_station_name, from_station_num,
                to_station_id, to_station_name, to_station_num,
                from_district_name, to_district_name, avg_distance_km,
                daily_avg_passengers, ever_transfer_required,
                'P2_우선' as priority_category, p2_score as priority_score
            FROM mv_monthly_od_summary 
            WHERE DATE(analysis_month) = :analysis_month AND p2_score > 0
            ORDER BY p2_score DESC LIMIT :top_n
            """
        
        result = await db.execute(
            text(query),
            {
                "analysis_month": analysis_month,
                "top_n": top_n
            }
        )
        
        rows = result.fetchall()
        transfers = []
        
        for row in rows:
            od_pair = ODPairInfoSchema(
                from_station_id=row.from_station_id,
                from_station_name=row.from_station_name,
                from_station_num=row.from_station_num,
                to_station_id=row.to_station_id,
                to_station_name=row.to_station_name,
                to_station_num=row.to_station_num,
                from_district=row.from_district_name,
                to_district=row.to_district_name,
                distance_km=float(row.avg_distance_km)
            )
            
            transfers.append(HighPriorityTransferSchema(
                od_pair=od_pair,
                daily_demand=int(row.daily_avg_passengers),
                transfer_required=row.ever_transfer_required,
                priority_category=row.priority_category
            ))
        
        return transfers

    @cache_result(key_prefix="od:p2_high_demand", use_month_ttl=True)
    async def get_p2_high_demand_routes(
        self,
        db: AsyncSession,
        analysis_month: date,
        top_n: int
    ) -> List[HighDemandDirectRouteSchema]:
        """P2 직행노선 부족 고수요 구간 조회 (기존 P3)"""
        
        query = """
        SELECT 
            from_station_id, from_station_name, from_station_num,
            to_station_id, to_station_name, to_station_num,
            from_district_name, to_district_name, avg_distance_km,
            daily_avg_passengers, ever_transfer_required,
            avg_dispatch_interval, 'P2_직행노선부족' as priority_category
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month AND p3_score > 0
        AND from_district_name IS NOT NULL AND to_district_name IS NOT NULL
        ORDER BY p3_score DESC LIMIT :top_n
        """
        
        result = await db.execute(text(query), {"analysis_month": analysis_month, "top_n": top_n})
        rows = result.fetchall()
        routes = []
        
        for row in rows:
            od_pair = ODPairInfoSchema(
                from_station_id=row.from_station_id,
                from_station_name=row.from_station_name,
                from_station_num=row.from_station_num,
                to_station_id=row.to_station_id,
                to_station_name=row.to_station_name,
                to_station_num=row.to_station_num,
                from_district=row.from_district_name,
                to_district=row.to_district_name,
                distance_km=float(row.avg_distance_km)
            )
            
            routes.append(HighDemandDirectRouteSchema(
                od_pair=od_pair,
                daily_demand=int(row.daily_avg_passengers),
                transfer_required=row.ever_transfer_required,
                avg_dispatch_interval=float(row.avg_dispatch_interval) if row.avg_dispatch_interval else None,
                priority_category=row.priority_category
            ))
        
        return routes

    @cache_result(key_prefix="od:p3_low_efficiency", use_month_ttl=True)
    async def get_p3_low_efficiency_routes(
        self,
        db: AsyncSession,
        analysis_month: date,
        top_n: int
    ) -> List[LowDemandLongDistanceSchema]:
        """P3 저수요 장거리 구간 조회 (기존 P4)"""
        
        query = """
        SELECT 
            from_station_id, from_station_name, from_station_num,
            to_station_id, to_station_name, to_station_num,
            from_district_name, to_district_name, avg_distance_km,
            daily_avg_passengers,
            CASE 
                WHEN avg_distance_km > 0 THEN daily_avg_passengers / avg_distance_km 
                ELSE 0 
            END as demand_per_km
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month AND p4_score > 0
        AND from_district_name IS NOT NULL AND to_district_name IS NOT NULL
        ORDER BY p4_score DESC LIMIT :top_n
        """
        
        result = await db.execute(text(query), {"analysis_month": analysis_month, "top_n": top_n})
        rows = result.fetchall()
        routes = []
        
        for row in rows:
            od_pair = ODPairInfoSchema(
                from_station_id=row.from_station_id,
                from_station_name=row.from_station_name,
                from_station_num=row.from_station_num,
                to_station_id=row.to_station_id,
                to_station_name=row.to_station_name,
                to_station_num=row.to_station_num,
                from_district=row.from_district_name,
                to_district=row.to_district_name,
                distance_km=float(row.avg_distance_km)
            )
            
            routes.append(LowDemandLongDistanceSchema(
                od_pair=od_pair,
                daily_demand=int(row.daily_avg_passengers),
                demand_per_km=float(row.demand_per_km),
                service_recommendation="DRT 전환 권장" if row.demand_per_km < 10 else "현행 유지"
            ))
        
        return routes

    # @cache_result(key_prefix="od:time_based_origin_v2", use_month_ttl=True)  # 스키마 변경으로 임시 비활성화
    async def get_time_based_origin_analysis(
        self,
        db: AsyncSession,
        analysis_month: date,
        time_period: str,
        top_n: int
    ) -> TimeBasedOriginAnalysisResponse:
        """시간대별 출발지 분석"""
        
        # 시간대별 컬럼 매핑
        time_period_columns = {
            "morning_peak": "monthly_morning_peak",
            "evening_peak": "monthly_evening_peak", 
            "night": "monthly_night",
            "daytime": "monthly_daytime"
        }
        
        time_period_names = {
            "morning_peak": "출근시간(07-09시)",
            "evening_peak": "퇴근시간(17-19시)",
            "night": "심야시간(23-06시)",
            "daytime": "주간시간(10-16시)"
        }
        
        if time_period not in time_period_columns:
            raise ValueError(f"Invalid time_period: {time_period}")
            
        time_column = time_period_columns[time_period]
        
        # 1단계: 출발지별 시간대 수요 기준 정렬 (동일 정류장 제외)
        main_query = f"""
        SELECT 
            from_station_id, from_station_name, from_station_num, from_district_name,
            from_coordinates_x, from_coordinates_y,
            SUM({time_column}) as time_period_demand,
            SUM(monthly_total_passengers) as total_monthly_demand,
            COUNT(DISTINCT to_station_id) as destination_count,
            AVG(avg_distance_km) as avg_distance_km
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month 
        AND from_station_id != to_station_id  -- 동일 정류장 제외
        AND from_coordinates_x IS NOT NULL 
        AND from_coordinates_y IS NOT NULL
        AND {time_column} > 0
        AND from_district_name IS NOT NULL
        GROUP BY from_station_id, from_station_name, from_station_num, from_district_name,
                 from_coordinates_x, from_coordinates_y
        HAVING SUM({time_column}) > 0
        ORDER BY SUM({time_column}) DESC
        LIMIT :top_n
        """
        
        result = await db.execute(
            text(main_query), 
            {"analysis_month": analysis_month, "top_n": top_n}
        )
        rows = result.fetchall()
        
        analysis_results = []
        
        for row in rows:
            # 2단계: 각 출발지별 상위 목적지 조회 (최대 20개)
            destinations_query = f"""
            SELECT 
                to_station_id, to_station_name, to_station_num, to_district_name,
                to_coordinates_x, to_coordinates_y,
                {time_column} as demand,
                ROW_NUMBER() OVER (ORDER BY {time_column} DESC) as rank
            FROM mv_monthly_od_summary
            WHERE DATE(analysis_month) = :analysis_month
            AND from_station_id = :from_station_id
            AND from_station_id != to_station_id  -- 동일 정류장 제외
            AND {time_column} > 0
            AND to_coordinates_x IS NOT NULL
            AND to_coordinates_y IS NOT NULL
            AND to_district_name IS NOT NULL
            ORDER BY {time_column} DESC
            LIMIT 20
            """
            
            dest_result = await db.execute(
                text(destinations_query),
                {"analysis_month": analysis_month, "from_station_id": row.from_station_id}
            )
            dest_rows = dest_result.fetchall()
            
            # 상위 목적지 리스트 구성 (DestinationStationSchema 형식)
            to_stations = [
                DestinationStationSchema(
                    station_id=dest.to_station_id,
                    station_name=dest.to_station_name,
                    station_num=dest.to_station_num,
                    district_name=dest.to_district_name,
                    coordinates={"x": float(dest.to_coordinates_x), "y": float(dest.to_coordinates_y)},
                    demand=int(dest.demand),
                    rank=dest.rank
                )
                for dest in dest_rows
            ]
            
            # 계산 로직
            time_period_ratio = (
                row.time_period_demand / row.total_monthly_demand 
                if row.total_monthly_demand > 0 else 0
            )
            
            # 목적지 분산도 계산 (to_stations의 district 개수 기준)
            unique_districts = set(station.district_name for station in to_stations)
            district_count = len(unique_districts)
            if district_count <= 3:
                destination_spread = "집중형"
            elif district_count <= 7:
                destination_spread = "분산형"  
            else:
                destination_spread = "광역형"
            
            # DRT 잠재력 계산
            if row.destination_count >= 20:
                drt_potential = "높음"
            elif row.destination_count >= 10:
                drt_potential = "보통"
            else:
                drt_potential = "낮음"
                
            # 서비스 권장사항
            if time_period_ratio > 0.4:
                service_recommendation = "시간대 집중 운영"
            elif time_period_ratio > 0.2:
                service_recommendation = "기존 노선 보완"
            else:
                service_recommendation = "수요 모니터링 필요"
            
            analysis_results.append(TimeBasedOriginAnalysisSchema(
                from_station={
                    "station_id": row.from_station_id,
                    "station_name": row.from_station_name,
                    "station_num": row.from_station_num,
                    "district_name": row.from_district_name,
                    "coordinates": {"x": float(row.from_coordinates_x), "y": float(row.from_coordinates_y)}
                },
                destination_count=row.destination_count,
                time_period_demand=int(row.time_period_demand),
                avg_distance_km=round(float(row.avg_distance_km), 2),
                to_stations=to_stations,
                drt_potential=drt_potential,
                service_recommendation=service_recommendation
            ))
        
        # 메타데이터 계산
        total_demand = sum(result.time_period_demand for result in analysis_results)
        avg_destinations = sum(result.destination_count for result in analysis_results) / len(analysis_results) if analysis_results else 0
        
        return TimeBasedOriginAnalysisResponse(
            time_period=time_period,
            time_period_name=time_period_names[time_period],
            analysis_month=analysis_month.strftime("%Y-%m"),
            total_origins=len(analysis_results),
            total_demand=total_demand,
            avg_destinations_per_origin=round(avg_destinations, 1),
            origins=analysis_results
        )

    # @cache_result(key_prefix="od:demand_supply_mismatch", use_month_ttl=True)  # 캐싱 임시 비활성화
    async def get_demand_supply_mismatch_analysis(
        self,
        db: AsyncSession,
        analysis_month: date,
        min_passengers: int = 10,
        top_n: int = 50
    ) -> List[DemandSupplyMismatchSchema]:
        """수요-공급 미스매치 분석 - 수요 대비 서비스 품질이 떨어지는 구간"""
        
        try:
            # 기본 데이터 조회 쿼리
            query = text("""
                SELECT 
                    from_station_id, from_station_name, from_station_num, from_district_name,
                    to_station_id, to_station_name, to_station_num, to_district_name,
                    from_coordinates_x, from_coordinates_y,
                    to_coordinates_x, to_coordinates_y,
                    monthly_total_passengers, daily_avg_passengers, avg_distance_km,
                    min_direct_connections, 
                    common_routes, from_routes, to_routes
                FROM mv_monthly_od_summary
                WHERE DATE(analysis_month) = :analysis_month
                    AND daily_avg_passengers >= :min_passengers
                    AND from_coordinates_x IS NOT NULL 
                    AND from_coordinates_y IS NOT NULL
                    AND to_coordinates_x IS NOT NULL 
                    AND to_coordinates_y IS NOT NULL
                ORDER BY daily_avg_passengers DESC
                LIMIT :limit_count
            """)
            
            result = await db.execute(query, {
                "analysis_month": analysis_month,
                "min_passengers": min_passengers,
                "limit_count": top_n * 3  # 여유분을 두고 조회 후 필터링
            })
            rows = result.fetchall()
            
            mismatch_results = []
            
            for row in rows:
                # 1. 서비스 품질 계산
                service_quality_metrics = self._calculate_service_quality(
                    row.min_direct_connections,
                    row.common_routes,
                    row.from_routes, 
                    row.to_routes
                )
                
                # 2. 수요-서비스 미스매치 계산
                demand_service_ratio = float(row.daily_avg_passengers) / max(service_quality_metrics['service_quality_score'], 1)
                
                # 3. 미스매치 임계값 필터링 (높은 비율만)
                if demand_service_ratio >= 1.0:  # 수요가 서비스보다 높은 경우만
                    
                    mismatch_results.append(DemandSupplyMismatchSchema(
                        od_pair=ODPairInfoSchema(
                            from_station_id=row.from_station_id,
                            from_station_name=row.from_station_name,
                            from_station_num=row.from_station_num,
                            from_coordinates={"x": float(row.from_coordinates_x), "y": float(row.from_coordinates_y)},
                            to_station_id=row.to_station_id,
                            to_station_name=row.to_station_name,
                            to_station_num=row.to_station_num,
                            to_coordinates={"x": float(row.to_coordinates_x), "y": float(row.to_coordinates_y)},
                            from_district=row.from_district_name,
                            to_district=row.to_district_name,
                            distance_km=round(float(row.avg_distance_km), 2)
                        ),
                        monthly_total_passengers=row.monthly_total_passengers,
                        daily_avg_passengers=round(float(row.daily_avg_passengers), 1),
                        distance_km=round(float(row.avg_distance_km), 2),
                        service_quality_score=round(service_quality_metrics['service_quality_score'], 1),
                        avg_dispatch_interval_min=round(service_quality_metrics['avg_dispatch_interval'], 1),
                        route_diversity_index=round(service_quality_metrics['route_diversity_index'], 1),
                        transfer_penalty=service_quality_metrics['transfer_penalty'],
                        demand_service_ratio=round(demand_service_ratio, 2)
                    ))
            
            # demand_service_ratio 기준으로 내림차순 정렬 후 상위 N개 반환
            mismatch_results.sort(key=lambda x: x.demand_service_ratio, reverse=True)
            return mismatch_results[:top_n]
            
        except Exception as e:
            logger.error(f"Error in get_demand_supply_mismatch_analysis: {e}")
            raise
    
    def _calculate_service_quality(self, min_direct_connections, common_routes, from_routes, to_routes):
        """서비스 품질 지표 계산"""
        
        try:
            if min_direct_connections > 0:
                # Case 1: 직행 구간
                intervals = []
                route_types = []
                
                for route in common_routes:
                    if 'dispatch_interval' in route:
                        intervals.append(route['dispatch_interval'])
                    if 'route_type' in route:
                        route_types.append(route['route_type'])
                
                # 배차간격 (조화평균)
                if intervals:
                    avg_dispatch_interval = len(intervals) / sum(1/max(i, 1) for i in intervals)
                else:
                    avg_dispatch_interval = 60  # 기본값
                
                # 노선 다양성
                weights = {"간선": 3, "지선": 2, "마을": 1, "공항": 4}
                route_diversity_index = sum(weights.get(route_type, 1) for route_type in route_types)
                
                transfer_penalty = 0.0
                
            else:
                # Case 2: 환승 필요 구간
                from_intervals = []
                to_intervals = []
                
                for route in from_routes:
                    if 'dispatch_interval' in route:
                        from_intervals.append(route['dispatch_interval'])
                
                for route in to_routes:
                    if 'dispatch_interval' in route:
                        to_intervals.append(route['dispatch_interval'])
                
                # 환승 페널티: 두 노선의 평균 배차간격 + 환승시간
                from_avg = sum(from_intervals) / len(from_intervals) if from_intervals else 30
                to_avg = sum(to_intervals) / len(to_intervals) if to_intervals else 30
                avg_dispatch_interval = from_avg + to_avg + 10  # 환승 시간 페널티
                
                route_diversity_index = 0  # 직행 없음
                transfer_penalty = 1.0
            
            # 서비스 품질 종합 점수 (0-100)
            interval_score = max(0, 100 - avg_dispatch_interval * 1.5)  # 배차간격이 길수록 감점
            diversity_score = min(100, route_diversity_index * 15)  # 다양성이 많을수록 가산
            transfer_score = 100 if transfer_penalty == 0 else 30  # 환승시 큰 페널티
            
            service_quality_score = (
                interval_score * 0.6 +      # 배차간격 최우선
                diversity_score * 0.2 +     # 선택권
                transfer_score * 0.2        # 환승 여부 - 다시 중요도 상향
            )
            
            return {
                'service_quality_score': service_quality_score,
                'avg_dispatch_interval': avg_dispatch_interval,
                'route_diversity_index': route_diversity_index,
                'transfer_penalty': transfer_penalty
            }
            
        except Exception as e:
            logger.error(f"Error in _calculate_service_quality: {e}")
            # 기본값 반환
            return {
                'service_quality_score': 50.0,
                'avg_dispatch_interval': 30.0,
                'route_diversity_index': 1.0,
                'transfer_penalty': 0.0
            }

    async def _get_time_based_analysis(
        self,
        db: AsyncSession,
        analysis_month: date
    ) -> List[TimeBasedDemandSchema]:
        """시간대별 수요 분석 - 임시 구현"""
        return []

    async def _get_summary_statistics(self, db: AsyncSession, analysis_month: date) -> dict:
        """전체 요약 지표 계산"""
        query = """
        SELECT 
            COUNT(*) as total_od_pairs,
            COUNT(CASE WHEN drt_priority_score > 0 THEN 1 END) as drt_applicable_pairs,
            SUM(CASE WHEN ever_transfer_required = true THEN monthly_total_passengers ELSE 0 END) as monthly_transfer_demand
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month
        """
        
        result = await db.execute(text(query), {"analysis_month": analysis_month})
        row = result.fetchone()
        
        return {
            "total_od_pairs": row.total_od_pairs,
            "drt_applicable_pairs": row.drt_applicable_pairs,
            "monthly_transfer_demand": int(row.monthly_transfer_demand) if row.monthly_transfer_demand else 0
        }

    async def _get_priority_distribution(self, db: AsyncSession, analysis_month: date) -> dict:
        """우선순위별 분포 계산"""
        query = """
        SELECT 
            COUNT(CASE WHEN p1_score > 0 THEN 1 END) as p1_count,
            COUNT(CASE WHEN p2_score > 0 THEN 1 END) as p2_count,
            COUNT(CASE WHEN p3_score > 0 THEN 1 END) as p3_count,
            COUNT(CASE WHEN p4_score > 0 THEN 1 END) as p4_count
        FROM mv_monthly_od_summary 
        WHERE DATE(analysis_month) = :analysis_month
        """
        
        result = await db.execute(text(query), {"analysis_month": analysis_month})
        row = result.fetchone()
        
        return {
            "p1_최우선": row.p1_count,
            "p2_우선": row.p2_count,
            "p3_고려": row.p3_count,
            "p4_적합": row.p4_count
        }

    async def get_od_pair_hourly_analysis(
        self, 
        db: AsyncSession, 
        analysis_month: date, 
        from_station_id: str, 
        to_station_id: str
    ) -> ODPairHourlyAnalysisSchema:
        """특정 OD Pair의 시간대별 상세 분석"""
        
        try:
            query = """
            SELECT 
                from_station_id, from_station_name, from_station_num,
                to_station_id, to_station_name, to_station_num,
                from_district_name, to_district_name, avg_distance_km,
                daily_avg_passengers, appearance_days,
                monthly_h00, monthly_h01, monthly_h02, monthly_h03, monthly_h04, monthly_h05,
                monthly_h06, monthly_h07, monthly_h08, monthly_h09, monthly_h10, monthly_h11,
                monthly_h12, monthly_h13, monthly_h14, monthly_h15, monthly_h16, monthly_h17,
                monthly_h18, monthly_h19, monthly_h20, monthly_h21, monthly_h22, monthly_h23,
                monthly_morning_peak, monthly_evening_peak, monthly_night, monthly_daytime
            FROM mv_monthly_od_summary 
            WHERE DATE(analysis_month) = :analysis_month
            AND from_station_id = :from_station_id
            AND to_station_id = :to_station_id
            """
            
            result = await db.execute(text(query), {
                "analysis_month": analysis_month,
                "from_station_id": from_station_id,
                "to_station_id": to_station_id
            })
            
            row = result.fetchone()
            if not row:
                raise ValueError(f"OD Pair not found: {from_station_id} -> {to_station_id}")
            
            # 24시간 월간 누적 데이터
            monthly_hourly_data = [
                row.monthly_h00, row.monthly_h01, row.monthly_h02, row.monthly_h03,
                row.monthly_h04, row.monthly_h05, row.monthly_h06, row.monthly_h07,
                row.monthly_h08, row.monthly_h09, row.monthly_h10, row.monthly_h11,
                row.monthly_h12, row.monthly_h13, row.monthly_h14, row.monthly_h15,
                row.monthly_h16, row.monthly_h17, row.monthly_h18, row.monthly_h19,
                row.monthly_h20, row.monthly_h21, row.monthly_h22, row.monthly_h23
            ]
            
            # 일평균으로 변환 (appearance_days로 나누기)
            appearance_days = row.appearance_days if row.appearance_days > 0 else 1
            hourly_data = [monthly / appearance_days for monthly in monthly_hourly_data]
            
            # hourly_passengers dict 생성 (일평균으로)
            hourly_passengers = {str(i): round(hourly_data[i], 1) for i in range(24)}
            
            # 총합 계산 
            total_monthly = sum(hourly_data)
            if total_monthly == 0:
                total_monthly = 1  # 0으로 나누기 방지
            
            # 피크 시간 찾기
            peak_hour = hourly_data.index(max(hourly_data))
            peak_passengers = round(max(hourly_data), 1)
            
            # 시간대별 비율 계산 (일평균 기준)
            morning_peak_avg = row.monthly_morning_peak / appearance_days
            evening_peak_avg = row.monthly_evening_peak / appearance_days
            daytime_avg = row.monthly_daytime / appearance_days
            night_avg = row.monthly_night / appearance_days
            
            morning_peak_pct = (morning_peak_avg / total_monthly) * 100
            evening_peak_pct = (evening_peak_avg / total_monthly) * 100
            daytime_pct = (daytime_avg / total_monthly) * 100
            night_pct = (night_avg / total_monthly) * 100
            
            # 패턴 타입 결정
            if morning_peak_pct > evening_peak_pct and morning_peak_pct > 20:
                pattern_type = "출근시간 집중형"
            elif evening_peak_pct > morning_peak_pct and evening_peak_pct > 20:
                pattern_type = "퇴근시간 집중형"
            elif daytime_pct > 50:
                pattern_type = "주간 분산형"
            else:
                pattern_type = "균등 분산형"
            
            return ODPairHourlyAnalysisSchema(
                od_pair=ODPairInfoSchema(
                    from_station_id=row.from_station_id,
                    from_station_name=row.from_station_name,
                    from_station_num=row.from_station_num,
                    to_station_id=row.to_station_id,
                    to_station_name=row.to_station_name,
                    to_station_num=row.to_station_num,
                    from_district=row.from_district_name,
                    to_district=row.to_district_name,
                    distance_km=float(row.avg_distance_km)
                ),
                daily_avg_passengers=float(row.daily_avg_passengers),
                hourly_passengers=hourly_passengers,
                time_summary={
                    "peak_hour": peak_hour,
                    "peak_passengers": peak_passengers,
                    "morning_peak_pct": round(morning_peak_pct, 1),
                    "evening_peak_pct": round(evening_peak_pct, 1),
                    "daytime_pct": round(daytime_pct, 1),
                    "night_pct": round(night_pct, 1),
                    "pattern_type": pattern_type
                }
            )
            
        except Exception as e:
            logger.error(f"Error in get_od_pair_hourly_analysis: {e}")
            raise