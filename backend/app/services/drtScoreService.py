"""
DRT Score 분석 서비스
출퇴근형, 관광특화형, 교통취약지형 3개 모델에 따른 DRT 점수 계산

리팩토링 방향:
1. 각 모델별로 명확하게 분리된 구조
2. 성능 최적화를 위한 배치 처리
3. 명확한 책임 분리
"""

from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.schemas.drtScore import (
    StationDRTScoreSummary,
    DistrictDRTScoreResponse,
    StationDRTDetailResponse,
    StationInfoSchema,
    CoordinateSchema
)


class DRTScoreService:
    """DRT Score 분석 서비스"""
    
    def __init__(self):
        # 모델별 테이블 매핑
        self.table_mapping = {
            'commuter': 'drt_commuter_scores',
            'tourism': 'drt_tourism_scores',
            'vulnerable': 'drt_vulnerable_scores'
        }
        
        # 모델별 feature columns 매핑 (실제 테이블 컬럼명에 맞춤)
        self.feature_columns = {
            'commuter': ['tc_score', 'pdr_score', 'ru_score', 'pcw_score'],
            'tourism': ['tc_t_score', 'tdr_t_score', 'ru_t_score', 'pcw_score'],
            'vulnerable': ['var_t_score', 'sed_t_score', 'mdi_t_score', 'avs_score']
        }
    
    def _get_table_name(self, model_type: str) -> str:
        """모델 타입에 따른 테이블명 반환"""
        return self.table_mapping.get(model_type, 'drt_commuter_scores')
    
    def _get_feature_columns(self, model_type: str) -> List[str]:
        """모델 타입에 따른 feature columns 반환"""
        return self.feature_columns.get(model_type, [])
    
    # ==========================================
    # 메인 엔드포인트 메서드들
    # ==========================================
    
    async def get_district_drt_scores(
        self,
        db: AsyncSession,
        district_name: str,
        model_type: str,
        analysis_month: date
    ) -> DistrictDRTScoreResponse:
        """
        구별 DRT Score 히트맵 데이터 조회
        요구사항:
        - 선택된 구의 모든 정류장 DRT 점수 계산
        - 24시간 중 최고 점수와 peak_hour만 반환
        - 점수 높은 순으로 정렬
        - 상위 5개 정류장 별도 제공
        """
        print(f"[DRT SERVICE] Getting DRT scores for {district_name}, model: {model_type}, month: {analysis_month}")
        
        # 모델별 테이블 선택
        table_name = self._get_table_name(model_type)
        month_start = analysis_month.replace(day=1)
        
        # 구별 정류장의 최고 DRT 점수 조회 (24시간 중 최고점)
        query = text(f"""
            WITH station_peak_scores AS (
                SELECT 
                    drt.station_id,
                    MAX(drt.total_drt_score) as peak_drt_score,
                    (ARRAY_AGG(drt.hour_of_day ORDER BY drt.total_drt_score DESC))[1] as peak_hour
                FROM {table_name} drt
                WHERE drt.district_name = :district_name
                    AND drt.analysis_month = :analysis_month
                GROUP BY drt.station_id
            )
            SELECT 
                sps.station_id,
                bs.node_name as station_name,
                bs.coordinates_y as latitude,
                bs.coordinates_x as longitude,
                sps.peak_drt_score,
                sps.peak_hour
            FROM station_peak_scores sps
            JOIN bus_stops bs ON sps.station_id = bs.node_id
            ORDER BY sps.peak_drt_score DESC
        """)
        
        try:
            result = await db.execute(query, {
                "district_name": district_name,
                "analysis_month": month_start
            })
            
            rows = result.fetchall()
            
            # StationDRTScoreSummary 리스트 생성
            stations = []
            for row in rows:
                station_summary = StationDRTScoreSummary(
                    station_id=row.station_id,
                    station_name=row.station_name,
                    coordinate=CoordinateSchema(
                        lat=float(row.latitude),
                        lng=float(row.longitude)
                    ),
                    drt_score=float(row.peak_drt_score),
                    peak_hour=int(row.peak_hour)
                )
                stations.append(station_summary)
            
            # 상위 5개 추출
            top_stations = stations[:5] if stations else []
            
            print(f"[DRT SERVICE] Found {len(stations)} stations in {district_name}, top 5 extracted")
            
            return DistrictDRTScoreResponse(
                district_name=district_name,
                model_type=model_type,
                analysis_month=analysis_month.strftime("%Y-%m"),
                stations=stations,
                top_stations=top_stations
            )
            
        except Exception as e:
            print(f"[DRT SERVICE ERROR] Failed to get district DRT scores: {str(e)}")
            return DistrictDRTScoreResponse(
                district_name=district_name,
                model_type=model_type,
                analysis_month=analysis_month.strftime("%Y-%m"),
                stations=[],
                top_stations=[]
            )
    
    async def get_station_drt_detail(
        self,
        db: AsyncSession,
        station_id: str,
        model_type: str,
        analysis_month: date,
        hour: Optional[int] = None
    ) -> StationDRTDetailResponse:
        """
        정류장 상세 DRT Score 분석
        요구사항:
        - 정류장 클릭 시 상세 정보 제공
        - 24시간 전체 점수 데이터
        - 세부 지표별 점수 (feature_scores)
        - 선택 시간대 정보 (current_hour, current_score)
        """
        print(f"[DRT SERVICE] Getting detailed DRT for station: {station_id}, model: {model_type}")
        
        table_name = self._get_table_name(model_type)
        feature_cols = self._get_feature_columns(model_type)
        month_start = analysis_month.replace(day=1)
        
        try:
            # 1. 정류장 기본 정보 조회
            station_info_query = text("""
                SELECT 
                    bs.node_id as station_id,
                    bs.node_name as station_name,
                    bs.coordinates_y as latitude,
                    bs.coordinates_x as longitude,
                    sm.sgg_name as district_name,
                    sm.adm_name as administrative_dong
                FROM bus_stops bs
                JOIN spatial_mapping sm ON bs.node_id = sm.node_id
                WHERE bs.node_id = :station_id
            """)
            
            station_result = await db.execute(station_info_query, {"station_id": station_id})
            station_row = station_result.fetchone()
            
            if not station_row:
                raise ValueError(f"Station {station_id} not found")
            
            station_info = StationInfoSchema(
                station_id=station_row.station_id,
                station_name=station_row.station_name,
                latitude=float(station_row.latitude),
                longitude=float(station_row.longitude),
                district_name=station_row.district_name,
                administrative_dong=station_row.administrative_dong
            )
            
            # 2. 24시간 DRT 점수 및 Feature scores 조회
            # Feature columns 동적 생성
            feature_select = ', '.join(feature_cols)
            
            scores_query = text(f"""
                SELECT 
                    hour_of_day,
                    total_drt_score,
                    {feature_select}
                FROM {table_name}
                WHERE station_id = :station_id
                    AND analysis_month = :analysis_month
                ORDER BY hour_of_day
            """)
            
            scores_result = await db.execute(scores_query, {
                "station_id": station_id,
                "analysis_month": month_start
            })
            
            scores_rows = scores_result.fetchall()
            
            if not scores_rows:
                raise ValueError(f"No DRT scores found for station {station_id} in {month_start}")
            
            # 3. 시간대별 점수 데이터 구성
            hourly_scores = []
            all_scores = []
            peak_score = 0.0
            peak_hour = 0
            current_score = 0.0
            current_hour_data = hour if hour is not None else None
            feature_scores_for_current = {}
            
            for row in scores_rows:
                hour_data = {
                    "hour": row.hour_of_day,
                    "score": float(row.total_drt_score)
                }
                hourly_scores.append(hour_data)
                all_scores.append(float(row.total_drt_score))
                
                # Peak score 추적
                if float(row.total_drt_score) > peak_score:
                    peak_score = float(row.total_drt_score)
                    peak_hour = row.hour_of_day
                
                # Current hour 데이터 저장
                if hour is not None and row.hour_of_day == hour:
                    current_score = float(row.total_drt_score)
                    current_hour_data = hour
                    # Feature scores 저장
                    for col in feature_cols:
                        feature_scores_for_current[col] = float(getattr(row, col))
            
            # hour가 지정되지 않은 경우 peak_hour 사용
            if hour is None:
                current_hour_data = peak_hour
                current_score = peak_score
                # Peak hour의 feature scores 찾기
                for row in scores_rows:
                    if row.hour_of_day == peak_hour:
                        for col in feature_cols:
                            feature_scores_for_current[col] = float(getattr(row, col))
                        break
            
            # 4. 월평균 계산
            monthly_average = sum(all_scores) / len(all_scores) if all_scores else 0.0
            
            print(f"[DRT SERVICE] Station {station_id} - Peak: {peak_score:.2f}@{peak_hour}h, Avg: {monthly_average:.2f}")
            
            return StationDRTDetailResponse(
                station=station_info,
                model_type=model_type,
                analysis_month=analysis_month.strftime("%Y-%m"),
                current_hour=current_hour_data,
                current_score=current_score,
                peak_score=peak_score,
                peak_hour=peak_hour,
                monthly_average=monthly_average,
                feature_scores=feature_scores_for_current,
                hourly_scores=hourly_scores
            )
            
        except Exception as e:
            print(f"[DRT SERVICE ERROR] Failed to get station detail: {str(e)}")
            # 에러 발생 시 기본값 반환
            return StationDRTDetailResponse(
                station=StationInfoSchema(
                    station_id=station_id,
                    station_name="Unknown",
                    latitude=0.0,
                    longitude=0.0,
                    district_name="Unknown",
                    administrative_dong="Unknown"
                ),
                model_type=model_type,
                analysis_month=analysis_month.strftime("%Y-%m"),
                current_hour=hour or 0,
                current_score=0.0,
                peak_score=0.0,
                peak_hour=0,
                monthly_average=0.0,
                feature_scores={},
                hourly_scores=[]
            )
    
    # ==========================================
    # 통계 및 분석 메서드
    # ==========================================
    
    async def get_model_statistics(
        self,
        db: AsyncSession,
        model_type: str,
        analysis_month: date
    ) -> Dict:
        """
        모델별 월간 통계 정보 조회
        - 전체 정류장 수
        - 평균 DRT 점수
        - 최고/최저 점수 정류장
        - 시간대별 평균 점수
        """
        table_name = self._get_table_name(model_type)
        month_start = analysis_month.replace(day=1)
        
        query = text(f"""
            WITH station_stats AS (
                SELECT 
                    station_id,
                    AVG(total_drt_score) as avg_score,
                    MAX(total_drt_score) as max_score,
                    MIN(total_drt_score) as min_score
                FROM {table_name}
                WHERE analysis_month = :analysis_month
                GROUP BY station_id
            ),
            hourly_avg AS (
                SELECT 
                    hour_of_day,
                    AVG(total_drt_score) as hourly_avg_score
                FROM {table_name}
                WHERE analysis_month = :analysis_month
                GROUP BY hour_of_day
            )
            SELECT 
                (SELECT COUNT(DISTINCT station_id) FROM station_stats) as total_stations,
                (SELECT AVG(avg_score) FROM station_stats) as overall_avg_score,
                (SELECT MAX(max_score) FROM station_stats) as overall_max_score,
                (SELECT MIN(min_score) FROM station_stats) as overall_min_score,
                (SELECT hour_of_day FROM hourly_avg ORDER BY hourly_avg_score DESC LIMIT 1) as peak_hour,
                (SELECT hour_of_day FROM hourly_avg ORDER BY hourly_avg_score ASC LIMIT 1) as lowest_hour
        """)
        
        result = await db.execute(query, {"analysis_month": month_start})
        row = result.fetchone()
        
        if row:
            return {
                "model_type": model_type,
                "analysis_month": analysis_month.strftime("%Y-%m"),
                "total_stations": row.total_stations,
                "overall_avg_score": float(row.overall_avg_score) if row.overall_avg_score else 0.0,
                "overall_max_score": float(row.overall_max_score) if row.overall_max_score else 0.0,
                "overall_min_score": float(row.overall_min_score) if row.overall_min_score else 0.0,
                "peak_hour": row.peak_hour,
                "lowest_hour": row.lowest_hour
            }
        
        return {}
    
    async def compare_models_for_station(
        self,
        db: AsyncSession,
        station_id: str,
        analysis_month: date
    ) -> Dict:
        """
        특정 정류장의 3개 모델 점수 비교
        """
        month_start = analysis_month.replace(day=1)
        results = {}
        
        for model_type in ['commuter', 'tourism', 'vulnerable']:
            table_name = self._get_table_name(model_type)
            
            query = text(f"""
                SELECT 
                    MAX(total_drt_score) as peak_score,
                    (ARRAY_AGG(hour_of_day ORDER BY total_drt_score DESC))[1] as peak_hour,
                    AVG(total_drt_score) as avg_score
                FROM {table_name}
                WHERE station_id = :station_id
                    AND analysis_month = :analysis_month
            """)
            
            result = await db.execute(query, {
                "station_id": station_id,
                "analysis_month": month_start
            })
            
            row = result.fetchone()
            if row and row.peak_score:
                results[model_type] = {
                    "peak_score": float(row.peak_score),
                    "peak_hour": int(row.peak_hour),
                    "avg_score": float(row.avg_score)
                }
            else:
                results[model_type] = {
                    "peak_score": 0.0,
                    "peak_hour": 0,
                    "avg_score": 0.0
                }
        
        return {
            "station_id": station_id,
            "analysis_month": analysis_month.strftime("%Y-%m"),
            "model_comparison": results
        }