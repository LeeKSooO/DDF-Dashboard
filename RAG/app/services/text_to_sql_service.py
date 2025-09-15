"""
Text-to-SQL Service for Seoul Traffic Database
서울시 교통 데이터베이스를 위한 자연어-SQL 변환 서비스
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, date
import pytz
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

from app.services.llm_service import LLMService
from app.core.config import settings
from app.core.exceptions import RAGServiceException

logger = logging.getLogger(__name__)


class SQLQueryType(Enum):
    """SQL 쿼리 유형 분류"""
    BASIC = "basic"                 # 단순 SELECT, WHERE
    AGGREGATION = "aggregation"     # GROUP BY, SUM, AVG, COUNT
    TIME_SERIES = "time_series"     # 시계열 분석 (date, hour 기반)
    SPATIAL = "spatial"             # 지리정보 쿼리 (PostGIS)
    COMPLEX = "complex"             # JOIN, 서브쿼리, 윈도우 함수

@dataclass
class SQLGenerationResult:
    """SQL 생성 결과"""
    generated_sql: str
    query_type: SQLQueryType
    confidence: float           # 0.0 ~ 1.0
    reasoning: str             # 생성 근거
    tables_used: List[str]     # 사용된 테이블들
    columns_used: List[str]    # 사용된 컬럼들
    estimated_rows: Optional[int] = None  # 예상 결과 행 수
    execution_time_estimate: Optional[float] = None  # 예상 실행 시간


class TextToSQLService:
    """DRT 교통 데이터베이스 특화 Text-to-SQL 서비스"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

        # 데이터베이스 스키마 정보 (프롬프트용)
        self.database_schema = self._get_database_schema()

        # SQL 검증을 위한 DB 연결 정보
        self.db_config = {
            'host': getattr(settings, 'DB_HOST', 'localhost'),
            'port': getattr(settings, 'DB_PORT', 5432),
            'database': getattr(settings, 'DB_NAME', 'ddf_db'),
            'user': getattr(settings, 'DB_USER', 'ddf_user'),
            'password': getattr(settings, 'DB_PASSWORD', 'ddf_password')
         }
 
        logger.info("✅ Text-to-SQL service initialized")

    def _get_database_schema(self) -> Dict[str, Any]:
        """실제 데이터베이스 스키마 정보 반환 (2025년 7월 실데이터 기준)"""

        return {
            "database_type": "PostgreSQL + TimescaleDB + PostGIS",
            "domain": "서울시 대중교통 및 DRT(수요응답형 교통) 데이터",
            "data_period": "2025년 7월 19일 ~ 31일 (실제 데이터)",
            "total_records": "13,136,256건 (station_passenger_history)",

            "tables": {
                # 정류장 정보 (20,590건, 18MB)
                "bus_stops": {
                    "description": "서울시 버스 정류장 마스터 정보",
                    "type": "기본 테이블",
                    "row_count": 20590,
                    "size": "18MB",
                    "columns": {
                        "node_id": "정류장ID (VARCHAR 50, PRIMARY KEY)",
                        "node_name": "정류장명 (VARCHAR 200, NOT NULL)",
                        "coordinates_x": "경도 (NUMERIC 12,8)",
                        "coordinates_y": "위도 (NUMERIC 11,8)",
                        "coordinates": "PostGIS POINT 좌표 (GEOMETRY)",
                        "is_active": "사용 여부 (BOOLEAN, 기본값: true)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "활성 정류장만 조회: WHERE is_active = TRUE",
                        "좌표 기반 근처 정류장: ST_DWithin(coordinates, ST_Point(127.0, 37.5), 1000)",
                        "구별 정류장 조회: JOIN spatial_mapping ON bus_stops.node_id = spatial_mapping.node_id"
                    ]
                },

                # 버스 노선 정보 (232KB)
                "bus_routes": {
                    "description": "서울시 버스 노선 정보",
                    "type": "기본 테이블",
                    "size": "232KB",
                    "columns": {
                        "route_id": "노선ID (VARCHAR 50, PRIMARY KEY)",
                        "route_name": "노선명 (VARCHAR 100, 예: 1004, 9408)",
                        "route_type": "노선 유형 (INTEGER, 1: 간선, 2: 지선, 3: 순환, 4: 광역, 5: 마을)",
                        "total_distance": "총 거리 (DECIMAL 10,2, km)",
                        "start_point": "기점명 (VARCHAR 200)",
                        "end_point": "종점명 (VARCHAR 200)",
                        "is_operating": "운행 여부 (BOOLEAN)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "간선버스 노선 개수: WHERE route_type = 1",
                        "총 거리가 20km 이상인 노선: WHERE total_distance >= 20",
                        "현재 운행 중인 마을버스: WHERE route_type = 5 AND is_operating = TRUE"
                    ]
                },

                # 노선-정류장 매핑 (37MB)
                "route_stops": {
                    "description": "버스노선-정류장 매핑 테이블",
                    "type": "관계 테이블",
                    "size": "37MB",
                    "columns": {
                        "id": "일련번호 (BIGSERIAL, PRIMARY KEY)",
                        "route_id": "노선ID (VARCHAR 50, FK -> bus_routes)",
                        "stop_id": "정류장ID (VARCHAR 50, FK -> bus_stops)",
                        "node_sequence": "노드 순서 (INTEGER)",
                        "stop_sequence": "정류장 순서 (INTEGER)",
                        "cumulative_stop_distance": "누적거리 (DECIMAL 10,2, km)",
                        "is_active": "사용 여부 (BOOLEAN, 기본값: true)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "1004번 버스 정차 정류장: WHERE route_id = '1004' ORDER BY stop_sequence",
                        "특정 정류장 경유 노선수: GROUP BY stop_id, COUNT(DISTINCT route_id)",
                        "노선별 정류장 개수: GROUP BY route_id, COUNT(*)"
                    ]
                },

                # 정류장-행정구역 매핑 (17,615건, 6.4MB)
                "spatial_mapping": {
                    "description": "정류장-행정구역 매핑 테이블 (성능 최적화용)",
                    "type": "매핑 테이블",
                    "row_count": 17615,
                    "size": "6.4MB",
                    "columns": {
                        "node_id": "정류장ID (VARCHAR 50, PRIMARY KEY, FK -> bus_stops)",
                        "sgg_code": "시군구 코드 (VARCHAR 10, NOT NULL)",
                        "sgg_name": "시군구명 (VARCHAR 50, NOT NULL) - 강남구, 서초구 등 25개 구",
                        "adm_code": "행정동 코드 (VARCHAR 20)",
                        "adm_name": "행정동명 (VARCHAR 100)",
                        "is_seoul": "서울시 소속 여부 (BOOLEAN, 기본값: true)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "district_data": {
                        "description": "서울시 25개 구별 정류장 분포",
                        "top_districts": {
                            "서초구": 1035, "강남구": 984, "영등포구": 981, "마포구": 964,
                            "강서구": 923, "송파구": 894, "성북구": 844, "노원구": 833
                        }
                    },
                    "sample_queries": [
                        "강남구 정류장 개수: WHERE sgg_name = '강남구' AND is_seoul = TRUE",
                        "구별 정류장 개수 순위: GROUP BY sgg_name ORDER BY COUNT(*) DESC",
                        "서울시 전체 정류장 수: WHERE is_seoul = TRUE"
                    ]
                },

                # 📊 핵심 교통량 데이터 (TimescaleDB 하이퍼테이블, 13,136,256건)
                "station_passenger_history": {
                    "description": "정류장별 시간당 승하차 인원 이력 (핵심 테이블)",
                    "type": "TimescaleDB 하이퍼테이블",
                    "row_count": 13136256,
                    "data_period": "2025-07-15 ~ 2025-07-31 (실제 데이터 범위)",
                    "columns": {
                        "record_date": "기준일자 (DATE, PRIMARY KEY 일부)",
                        "route_id": "노선ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "node_id": "정류장ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "hour": "시간 (INTEGER 0-23, PRIMARY KEY 일부)",
                        "route_name": "노선명 (VARCHAR 100)",
                        "station_name": "정류장명 (VARCHAR 200)",
                        "station_sequence": "정류장 순번 (INTEGER)",
                        "ride_passenger": "승차 인원 (INTEGER, 기본값 0) - 핵심 지표",
                        "alight_passenger": "하차 인원 (INTEGER, 기본값 0) - 핵심 지표",
                        "created_at": "생성일시 (TIMESTAMP)"
                    },
                    "key_formula": "총 교통량 = ride_passenger + alight_passenger",
                    "sample_queries": [
                        "전체 교통량: SUM(ride_passenger + alight_passenger) WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'",
                        "상위 정류장: GROUP BY node_id, station_name ORDER BY SUM(ride_passenger + alight_passenger) DESC LIMIT 10",
                        "시간대별 패턴: GROUP BY hour ORDER BY hour"
                    ]
                },

                # 구간별 승객수 이력 (56KB)
                "section_passenger_history": {
                    "description": "구간별 시간당 승객수 이력 (TimescaleDB)",
                    "type": "TimescaleDB 하이퍼테이블",
                    "size": "56KB",
                    "columns": {
                        "record_date": "기준일자 (DATE, PRIMARY KEY 일부)",
                        "route_id": "노선ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "from_node_id": "출발 정류장ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "to_node_id": "도착 정류장ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "hour": "시간 (INTEGER 0-23, PRIMARY KEY 일부)",
                        "station_sequence": "정류장 순번 (INTEGER)",
                        "passenger_count": "해당 시간대 승객수 (INTEGER)",
                        "created_at": "생성일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "구간별 승객수: WHERE from_node_id = 'A' AND to_node_id = 'B'",
                        "혼잡 구간 TOP 10: GROUP BY from_node_id, to_node_id ORDER BY SUM(passenger_count) DESC",
                        "노선별 구간 분석: WHERE route_id = '1004' GROUP BY from_node_id, to_node_id"
                    ]
                },

                # 구간별 운행시간 이력 (56KB)
                "section_speed_history": {
                    "description": "구간별 시간당 운행시간 이력 (TimescaleDB)",
                    "type": "TimescaleDB 하이퍼테이블",
                    "size": "56KB",
                    "columns": {
                        "record_date": "기준일자 (DATE, PRIMARY KEY 일부)",
                        "route_id": "노선ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "from_node_id": "출발 정류장ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "to_node_id": "도착 정류장ID (VARCHAR 50, PRIMARY KEY 일부)",
                        "hour": "시간 (INTEGER 0-23, PRIMARY KEY 일부)",
                        "from_station_sequence": "출발 정류장 순번 (INTEGER)",
                        "to_station_sequence": "도착 정류장 순번 (INTEGER)",
                        "trip_time": "운행시간 (INTEGER, 분)",
                        "created_at": "생성일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "출근시간 평균 운행시간: WHERE hour BETWEEN 7 AND 9 GROUP BY from_node_id, to_node_id",
                        "노선별 평균 속도: GROUP BY route_id, AVG(trip_time)",
                        "교통 체증 시간대: GROUP BY hour ORDER BY AVG(trip_time) DESC"
                    ]
                },

                # OD 통행량 이력 (32KB)
                "od_traffic_history": {
                    "description": "행정동별 OD 통행량 이력 (TimescaleDB)",
                    "type": "TimescaleDB 하이퍼테이블",
                    "size": "32KB",
                    "columns": {
                        "record_date": "기준일자 (DATE, PRIMARY KEY 일부)",
                        "start_district": "출발 시군구 (VARCHAR 50, PRIMARY KEY 일부)",
                        "start_admin_dong": "출발 행정동 (VARCHAR 100, PRIMARY KEY 일부)",
                        "end_district": "도착 시군구 (VARCHAR 50, PRIMARY KEY 일부)",
                        "end_admin_dong": "도착 행정동 (VARCHAR 100, PRIMARY KEY 일부)",
                        "total_passenger_count": "총 통행량 (INTEGER)",
                        "created_at": "생성일시 (TIMESTAMP)"
                    },
                    "sample_queries": [
                        "강남-서초 통행량: WHERE start_district = '강남구' AND end_district = '서초구'",
                        "통행량 TOP 10: GROUP BY start_district, end_district ORDER BY SUM(total_passenger_count) DESC",
                        "지역 유입/유출: WHERE start_district = '강남구' OR end_district = '강남구'"
                    ]
                },

                # 대용량 OD 분석 데이터 (21GB)
                "daily_od_analysis": {
                    "description": "일별 OD 분석 데이터 (메인 분석 테이블)",
                    "type": "분석 테이블",
                    "row_count": "대용량",
                    "size": "21GB",
                    "columns_count": 61,
                    "key_columns": {
                        "from_station_id": "출발 정류장ID (VARCHAR 50)",
                        "to_station_id": "도착 정류장ID (VARCHAR 50)",
                        "analysis_date": "분석일자 (DATE)",
                        "total_passengers": "총 승객수 (INTEGER)",
                        "morning_peak_passengers": "아침 피크 승객수 (INTEGER)",
                        "evening_peak_passengers": "저녁 피크 승객수 (INTEGER)"
                    },
                    "sample_queries": [
                        "OD 쌍별 총 승객수: GROUP BY from_station_id, to_station_id",
                        "피크시간 OD 분석: WHERE morning_peak_passengers > 0",
                        "일별 OD 트렌드: GROUP BY analysis_date ORDER BY analysis_date"
                    ]
                },

                # DRT 점수 테이블들
                "drt_commuter_scores": {
                    "description": "출퇴근형 DRT 점수 (240MB)",
                    "type": "DRT 분석 테이블",
                    "size": "240MB",
                    "model_type": "commuter"
                },

                "drt_tourism_scores": {
                    "description": "관광특화형 DRT 점수 (321MB)",
                    "type": "DRT 분석 테이블",
                    "size": "321MB",
                    "model_type": "tourism"
                },

                "drt_vulnerable_scores": {
                    "description": "교통취약지형 DRT 점수 (111MB)",
                    "type": "DRT 분석 테이블",
                    "size": "111MB",
                    "model_type": "vulnerable"
                },

                # 관리/설정 테이블들
                "admin_boundaries": {
                    "description": "행정구역 경계 (632KB)",
                    "type": "지리정보 테이블",
                    "size": "632KB"
                },

                "operation_schedules": {
                    "description": "운행 스케줄 (168KB)",
                    "type": "운영 정보 테이블",
                    "size": "168KB"
                },

                "route_details": {
                    "description": "노선 상세 정보 (152KB)",
                    "type": "기본 테이블",
                    "size": "152KB"
                }
            },

            # Materialized Views (성능 최적화용)
            "materialized_views": {
                "mv_seoul_hourly_patterns": {
                    "description": "서울시 시간대별 패턴 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "서울시 전체 시간대별 교통량 분석용"
                },
                "mv_hourly_traffic_patterns": {
                    "description": "구별 시간대별 패턴 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "구별 시간대별 교통량 분석용"
                },
                "mv_station_hourly_patterns": {
                    "description": "정류장별 시간대별 패턴 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "정류장별 시간대별 교통량 분석용"
                },
                "mv_district_monthly_traffic": {
                    "description": "구별 월간 교통량 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "구별 월간 교통량 집계용"
                },
                "mv_station_monthly_traffic": {
                    "description": "정류장별 월간 교통량 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "정류장별 월간 교통량 집계용"
                },
                "mv_monthly_od_summary": {
                    "description": "월간 OD 요약 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "월간 OD 분석용"
                },
                "monthly_district_traffic_summary": {
                    "description": "구별 교통량 요약 (집계 뷰)",
                    "refresh": "매일 자동 갱신",
                    "usage": "구별 교통량 요약용"
                }
            },

            "table_relationships": {
                "bus_routes → route_stops": "route_id로 연결 (1:N)",
                "bus_stops → route_stops": "node_id = stop_id로 연결 (1:N)",
                "bus_stops → spatial_mapping": "node_id로 연결 (1:1)",
                "bus_stops → station_passenger_history": "node_id로 연결 (1:N)",
                "bus_routes → station_passenger_history": "route_id로 연결 (1:N)",
                "spatial_mapping → station_passenger_history": "node_id로 연결 (1:N, 지역별 집계용)",
                "daily_od_analysis": "독립적 분석 테이블 (정류장ID로 bus_stops과 연결 가능)"
            },

            "common_patterns": {
                "지역별 집계": "spatial_mapping.sgg_name으로 GROUP BY",
                "시간대별 분석": "hour 필드로 GROUP BY, WHERE hour BETWEEN 7 AND 9",
                "월별 트렌드": "DATE_TRUNC('month', record_date)로 GROUP BY",
                "노선별 통계": "route_id, route_name으로 GROUP BY",
                "정류장별 통계": "node_id, station_name으로 GROUP BY",
                "승하차 합계": "ride_passenger + alight_passenger",
                "성능 최적화": "Materialized View 활용 권장"
            },

            "business_context": {
                "DRT 분석": "수요응답형 교통 도입 지역 분석",
                "교통 수요": "시간대별, 지역별 교통 수요 패턴",
                "노선 효율성": "노선별 이용률 및 운행 효율성",
                "정류장 중요도": "승하차 인원 기준 정류장 순위",
                "혼잡 지역": "교통량이 많은 시간대/지역 식별",
                "정책 수립": "교통 정책 수립을 위한 데이터 근거"
            }
        }

    async def generate_sql(self, question: str) -> SQLGenerationResult:
        """자연어 질문을 SQL로 변환"""

        try:
            logger.info(f"🔄 Generating SQL for question: {question[:100]}...")

            # 1. 질문 전처리 및 분석
            processed_question = self._preprocess_question(question)
            query_type = self._analyze_query_type(processed_question)

            # 2. SQL 생성 프롬프트 구성
            sql_prompt = self._build_sql_prompt(processed_question, query_type)

            # 3. LLM을 통한 SQL 생성
            sql_response = await self.llm_service.generate_text(sql_prompt)

            # 4. SQL 파싱 및 검증
            parsed_result = self._parse_sql_response(sql_response, query_type)

            # 5. SQL 문법 검증 및 재시도 로직 (최대 3회)
            final_sql, attempts_made = await self._validate_and_retry_sql(
                parsed_result.generated_sql,
                processed_question,
                max_retries=3
            )

            if final_sql != parsed_result.generated_sql:
                parsed_result.generated_sql = final_sql
                parsed_result.confidence *= (0.9 ** attempts_made)  # 재시도 횟수만큼 신뢰도 감소
                parsed_result.reasoning += f" (자동 수정됨: {attempts_made}회 재시도 후 성공)"

            logger.info(f"✅ SQL generated successfully (confidence: {parsed_result.confidence:.2f})")
            return parsed_result

        except Exception as e:
            logger.error(f"❌ SQL generation failed: {e}")
            # 폴백: 기본 쿼리 반환
            return self._create_fallback_sql(question)

    def _preprocess_question(self, question: str) -> str:
        """질문 전처리 (현재 시간 기반 상대 시간 처리 포함)"""

        # 기본 정리
        question = question.strip()

        # 현재 시간 정보 가져오기 (한국 시간 기준)
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        today = now.date()
        current_year = today.year
        current_month = today.month
        current_day = today.day

        # 실제 데이터 범위 정보 (환경변수에서 가져옴)
        from app.core.config import settings
        DATA_START_DATE = settings.DATABASE_DATE_START
        DATA_END_DATE = settings.DATABASE_DATE_END

        # 상대적 시간 표현을 절대적 날짜로 변환
        time_replacements = {
            r'오늘': f'{today.strftime("%Y년 %m월 %d일")} ({today})',
            r'어제': f'{(today.replace(day=today.day-1)).strftime("%Y년 %m월 %d일")}',
            r'이번달': f'{current_year}년 {current_month}월',
            r'이번 달': f'{current_year}년 {current_month}월',
            r'올해': f'{current_year}년',
            r'이번년도': f'{current_year}년',
            r'현재': f'현재 ({today})',
            r'지금': f'현재 ({today})',
            r'요즘': f'최근 ({today} 기준)'
        }

        # 특정 월/연도 패턴을 실제 데이터 범위로 매핑
        month_year_patterns = {
            r'2025년\s*7월': f'2025년 7월 (실제 데이터: {DATA_START_DATE} ~ {DATA_END_DATE})',
            r'2025년\s*07월': f'2025년 7월 (실제 데이터: {DATA_START_DATE} ~ {DATA_END_DATE})',
            r'2025\s*7월': f'2025년 7월 (실제 데이터: {DATA_START_DATE} ~ {DATA_END_DATE})',
            r'2025-07': f'2025년 7월 (실제 데이터: {DATA_START_DATE} ~ {DATA_END_DATE})',
            r'7월': f'2025년 7월 (실제 데이터: {DATA_START_DATE} ~ {DATA_END_DATE})',
        }

        question_lower = question.lower()

        # 1. 먼저 특정 월/연도 패턴을 실제 데이터 범위로 변환
        for pattern, replacement in month_year_patterns.items():
            question = re.sub(pattern, replacement, question, flags=re.IGNORECASE)

        # 2. 일반적인 상대 시간 표현 변환
        for pattern, replacement in time_replacements.items():
            question = re.sub(pattern, replacement, question, flags=re.IGNORECASE)

        # 한국어 자연어 패턴 정규화
        replacements = {
            r'몇\s*개': '개수',
            r'얼마나\s*많이': '개수',
            r'어느\s*지역': '어떤 구',
            r'어떤\s*노선': '어떤 버스',
            r'언제': '어떤 시간',
            r'어디': '어떤 곳',
            r'누가': '어떤 사람',
            r'왜': '이유',
            r'어떻게': '방법'
        }

        for pattern, replacement in replacements.items():
            question = re.sub(pattern, replacement, question)

        # 교통량/승객수 관련 질문 처리 개선
        question_lower = question.lower()
        if any(keyword in question_lower for keyword in ['교통량', '통행량', '이용량', '승객', '승차', '이용객']):
            # 월별 교통량이면 TimescaleDB 시계열 함수 힌트 추가
            if any(month in question_lower for month in ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월', '월']):
                question = f"{question} (시계열 데이터에서 해당 월의 승하차 데이터 집계 - station_passenger_history, section_passenger_history 테이블 활용)"
            else:
                question = f"{question} (교통카드 승하차 데이터 기반으로 답변 - station_passenger_history 테이블 활용)"

        return question

    def _analyze_query_type(self, question: str) -> SQLQueryType:
        """질문 유형 분석하여 SQL 패턴 결정"""

        question_lower = question.lower()

        # 시계열 분석 패턴
        time_patterns = ['시간대별', '월별', '일별', '년도별', '시간', '언제', '시간당', '분기별']
        if any(pattern in question_lower for pattern in time_patterns):
            return SQLQueryType.TIME_SERIES

        # 집계 패턴
        agg_patterns = ['개수', '총', '평균', '최대', '최소', '합계', 'top', '상위', '하위']
        if any(pattern in question_lower for pattern in agg_patterns):
            return SQLQueryType.AGGREGATION

        # 공간 분석 패턴
        spatial_patterns = ['근처', '주변', '거리', '위치', '좌표', 'km', 'm', '지역', '구', '동']
        if any(pattern in question_lower for pattern in spatial_patterns):
            return SQLQueryType.SPATIAL

        # 복잡한 쿼리 패턴
        complex_patterns = ['비교', '분석', '관계', '연관', '영향', '상관관계', '패턴']
        if any(pattern in question_lower for pattern in complex_patterns):
            return SQLQueryType.COMPLEX

        return SQLQueryType.BASIC

    def _build_sql_prompt(self, question: str, query_type: SQLQueryType) -> str:
        """SQL 생성을 위한 프롬프트 구성"""

        # 환경설정 로드
        from app.core.config import settings
        DATA_START_DATE = settings.DATABASE_DATE_START
        DATA_END_DATE = settings.DATABASE_DATE_END

        # 현재 시간 정보 (쿼리 생성용)
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        today = now.date()

        base_prompt = f"""당신은 서울시 교통 데이터베이스 전문가입니다. 실제 운영 중인 데이터베이스의 정확한 스키마를 기반으로 PostgreSQL 쿼리를 생성해주세요.

## 현재 시간 정보 (쿼리 생성 참고용)
- **현재 날짜**: {today} ({today.strftime('%Y년 %m월 %d일, %A')})
- **현재 시간**: {now.strftime('%H:%M:%S')} (한국 시간)
- **현재 연도**: {today.year}년
- **현재 월**: {today.month}월

## ⚠️🚨 중요한 데이터베이스 제약사항 🚨⚠️

### 1. 날짜 범위 제약
- **이 데이터베이스의 모든 시계열 데이터는 2025년 7월 15일부터 2025년 7월 31일까지만 존재합니다**
- **날짜 관련 쿼리 생성 시 반드시 이 범위 내에서만 조회해야 합니다**
- **"7월", "이번 달", "최근" 등의 표현은 2025-07-15 ~ 2025-07-31 범위를 의미합니다**
- **존재하지 않는 날짜(예: 7월 1일~14일)에 대한 쿼리는 생성하지 마세요**

### 예시 매핑:
- "7월 교통량" → WHERE date BETWEEN '2025-07-15' AND '2025-07-31'
- "7월 초" → WHERE date BETWEEN '2025-07-15' AND '2025-07-20'
- "7월 말" → WHERE date BETWEEN '2025-07-27' AND '2025-07-31'
- "최근 일주일" → WHERE date >= '2025-07-25'

## 🏢 실제 데이터베이스 정보 (DDF-ASTGCN 프로젝트, 2025년 기준)
- 데이터베이스: PostgreSQL + TimescaleDB + PostGIS
- 도메인: 서울시 대중교통 및 DRT(수요응답형 교통) 데이터
- 실제 데이터 기간: {DATA_START_DATE} ~ {DATA_END_DATE}
- 데이터 규모: 총 34개 객체 (22개 테이블 + 7개 MV + 5개 뷰)
- 주요 데이터: 13,136,256건 (station_passenger_history)

## 📊 핵심 테이블 스키마 (실제 존재하는 테이블만)

### 1. 🚌 기본 인프라 테이블
```sql
-- 정류장 정보 (20,590건, 18MB)
bus_stops (
    node_id VARCHAR(50) PRIMARY KEY,       -- 정류장ID
    node_name VARCHAR(200) NOT NULL,       -- 정류장명
    coordinates_x NUMERIC(12,8),           -- 경도
    coordinates_y NUMERIC(11,8),           -- 위도
    coordinates GEOMETRY(POINT, 4326),     -- PostGIS 좌표
    is_active BOOLEAN DEFAULT TRUE         -- 사용여부
);

-- 정류장-행정구역 매핑 (17,615건, 6.4MB)
spatial_mapping (
    node_id VARCHAR(50) PRIMARY KEY,       -- 정류장ID (FK -> bus_stops)
    sgg_name VARCHAR(50) NOT NULL,         -- 시군구명 (강남구, 서초구 등 25개 구)
    adm_name VARCHAR(100),                 -- 행정동명
    is_seoul BOOLEAN DEFAULT TRUE          -- 서울시 여부
);

-- 버스 노선 정보 (232KB)
bus_routes (
    route_id VARCHAR(50) PRIMARY KEY,      -- 노선ID
    route_name VARCHAR(100),               -- 노선명 (1004, 9408 등)
    route_type INTEGER,                    -- 노선유형 (1:간선, 2:지선, 3:순환, 4:광역, 5:마을)
    total_distance DECIMAL(10,2),          -- 총거리 (km)
    is_operating BOOLEAN                   -- 운행여부
);

-- 노선-정류장 매핑 (37MB)
route_stops (
    route_id VARCHAR(50),                  -- 노선ID (FK -> bus_routes)
    stop_id VARCHAR(50),                   -- 정류장ID (FK -> bus_stops)
    node_sequence INTEGER,                 -- 노드순서
    stop_sequence INTEGER,                 -- 정류장순서
    cumulative_stop_distance DECIMAL(10,2) -- 누적거리
);
```

### 2. 📈 시계열 교통 데이터 (TimescaleDB 하이퍼테이블)
```sql
-- ⭐ 핵심: 정류장별 시간당 승하차 인원 (13,136,256건)
station_passenger_history (
    record_date DATE NOT NULL,             -- 기준일자 (2025-07-15 ~ 2025-07-31)
    route_id VARCHAR(50) NOT NULL,         -- 노선ID
    node_id VARCHAR(50) NOT NULL,          -- 정류장ID
    hour INTEGER NOT NULL,                 -- 시간 (0-23)
    route_name VARCHAR(100),               -- 노선명
    station_name VARCHAR(200),             -- 정류장명
    station_sequence INTEGER,              -- 정류장순번
    ride_passenger INTEGER DEFAULT 0,      -- 승차인원 ⭐⭐⭐
    alight_passenger INTEGER DEFAULT 0,    -- 하차인원 ⭐⭐⭐
    PRIMARY KEY (record_date, route_id, node_id, hour)
);

-- 구간별 시간당 승객수 (56KB)
section_passenger_history (
    record_date DATE,                      -- 기준일자
    route_id VARCHAR(50),                  -- 노선ID
    from_node_id VARCHAR(50),              -- 출발정류장ID
    to_node_id VARCHAR(50),                -- 도착정류장ID
    hour INTEGER,                          -- 시간 (0-23)
    passenger_count INTEGER,               -- 승객수 (시간당)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
);

-- 구간별 시간당 운행시간 (56KB)
section_speed_history (
    record_date DATE,                      -- 기준일자
    route_id VARCHAR(50),                  -- 노선ID
    from_node_id VARCHAR(50),              -- 출발정류장ID
    to_node_id VARCHAR(50),                -- 도착정류장ID
    hour INTEGER,                          -- 시간 (0-23)
    trip_time INTEGER,                     -- 운행시간 (분)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
);
```

### 3. 🎯 대용량 분석 데이터
```sql
-- OD 분석 데이터 (21GB, 61개 컬럼)
daily_od_analysis (
    from_station_id VARCHAR(50),           -- 출발정류장ID
    to_station_id VARCHAR(50),             -- 도착정류장ID
    analysis_date DATE,                    -- 분석일자
    total_passengers INTEGER,              -- 총승객수
    morning_peak_passengers INTEGER,       -- 아침피크 승객수
    evening_peak_passengers INTEGER        -- 저녁피크 승객수
    -- ... 기타 58개 컬럼
);
```

### 4. 🏆 Materialized Views (성능 최적화용)
```sql
-- 서울시 시간대별 패턴 (집계 뷰)
mv_seoul_hourly_patterns;

-- 구별 시간대별 패턴 (집계 뷰)
mv_hourly_traffic_patterns;

-- 정류장별 시간대별 패턴 (집계 뷰)
mv_station_hourly_patterns;

-- 구별 월간 교통량 (집계 뷰)
mv_district_monthly_traffic;

-- 정류장별 월간 교통량 (집계 뷰)
mv_station_monthly_traffic;

-- 월간 OD 요약 (집계 뷰)
mv_monthly_od_summary;

-- 구별 교통량 요약 (집계 뷰)
monthly_district_traffic_summary;
```



### 5. 🎯 DRT 점수 테이블 (모델별 전용)
```sql
-- 출퇴근형 DRT 점수 (240MB)
drt_commuter_scores (
    model_type VARCHAR(20) DEFAULT 'commuter',
    -- DRT 관련 점수 및 메트릭
);

-- 관광특화형 DRT 점수 (321MB)
drt_tourism_scores (
    model_type VARCHAR(20) DEFAULT 'tourism',
    -- DRT 관련 점수 및 메트릭
);

-- 교통취약지형 DRT 점수 (111MB)
drt_vulnerable_scores (
    model_type VARCHAR(20) DEFAULT 'vulnerable',
    -- DRT 관련 점수 및 메트릭
);
```

### 6. 🗺️ 행정구역 및 지리정보
```sql
-- 행정구역 경계 (632KB)
admin_boundaries (
    -- 행정구역 경계 정보
);

-- 좌표계 참조 (7MB)
spatial_ref_sys (
    -- PostGIS 좌표계 정보
);
```

## ⭐ 핵심 쿼리 작성 가이드라인 (실제 데이터 기준)

### 🔥 중요: 실제 데이터 정보 & 시간 기간 제한
- **데이터 기간**: 2025년 7월 15일 ~ 31일만 존재 (이 범위 밖에는 데이터 없음)
- **절대 사용 금지**: '2025-07-01' ~ '2025-07-14' (데이터 없음)
- **반드시 사용**: WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'
- **월단위 요청시**: "2025년 7월" = 실제로는 '2025-07-15' ~ '2025-07-31' 범위
- **핵심 공식**: 총 교통량 = ride_passenger + alight_passenger (승차+하차)

### 📊 정류장 수 관련 제약사항 (중요!)

#### ❌ 잘못된 접근법 (물리적 정류장 수)
```sql
-- 잘못된 방법: 물리적으로 존재하는 모든 정류장 (부정확)
SELECT COUNT(*) FROM spatial_mapping sm
JOIN bus_stops bs ON sm.node_id = bs.node_id
WHERE bs.is_active = TRUE AND sm.sgg_name = '서초구'
```

#### ✅ 올바른 접근법 (실제 운영 정류장 수)
```sql
-- 올바른 방법: 실제 교통량이 있는 운영 정류장만 카운트
SELECT COUNT(DISTINCT sm.node_id)
FROM spatial_mapping sm
WHERE sm.sgg_name = '서초구'
AND EXISTS (
    SELECT 1 FROM station_passenger_history sph
    WHERE sph.node_id = sm.node_id
    AND (sph.ride_passenger > 0 OR sph.alight_passenger > 0)
    AND sph.record_date BETWEEN '2025-07-15' AND '2025-07-31'
)
```
**제약사항**: 정류장 수 조회 시 station_passenger_history에 실제 승하차 데이터가 있는 정류장만 카운트

### 🏢 지역별/구별 집계 제약사항

#### ❌ 잘못된 접근법 (패턴 기반 추정)
```sql
-- 잘못된 방법: node_id 패턴으로 지역 판단 (부정확)
WHERE node_id LIKE '1%'  -- 강남구 추정 (틀림)
```

#### ✅ 올바른 접근법 (spatial_mapping 조인)
```sql
-- 올바른 방법: spatial_mapping 테이블 조인 필수
FROM station_passenger_history sph
JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sm.sgg_name = '강남구'
AND sm.is_seoul = TRUE  -- 서울시 확실한 매핑만
AND sph.record_date BETWEEN '2025-07-15' AND '2025-07-31'
```
**제약사항**: 지역별 분석은 spatial_mapping 테이블과의 조인 필수

### 📈 히트맵 교통량 집계 제약사항

#### ✅ 대시보드 히트맵 표준 로직
```sql
-- 구별 총 교통량 (월간 합계)
SELECT
    sm.sgg_name,
    SUM(sph.ride_passenger + sph.alight_passenger) as total_traffic
FROM station_passenger_history sph
JOIN spatial_mapping sm ON sph.node_id = sm.node_id
WHERE sph.record_date BETWEEN '2025-07-15' AND '2025-07-31'
GROUP BY sm.sgg_name
ORDER BY total_traffic DESC
```
**제약사항**: 히트맵은 승차+하차의 총 교통량으로 계산

### 🎯 DRT 점수 관련 제약사항

#### ✅ 모델별 전용 테이블 사용
```sql
-- 출퇴근형 DRT 점수
SELECT * FROM drt_commuter_scores
WHERE model_type = 'commuter'

-- 관광특화형 DRT 점수
SELECT * FROM drt_tourism_scores
WHERE model_type = 'tourism'

-- 교통취약지형 DRT 점수
SELECT * FROM drt_vulnerable_scores
WHERE model_type = 'vulnerable'
```
**제약사항**: DRT 점수는 모델별로 별도 테이블에서 조회

### 🚌 승하차 데이터 제약사항

#### ✅ 핵심 테이블별 사용법
```sql
-- 시간대별 승하차 (station_passenger_history)
SELECT hour, ride_passenger, alight_passenger
FROM station_passenger_history
WHERE hour BETWEEN 7 AND 9  -- 출근시간
AND record_date BETWEEN '2025-07-15' AND '2025-07-31'

-- OD 분석 (daily_od_analysis)
SELECT from_station_id, to_station_id, total_passengers
FROM daily_od_analysis
WHERE analysis_date BETWEEN '2025-07-15' AND '2025-07-31'
```
**제약사항**: station_passenger_history(시간대별), daily_od_analysis(일별 OD) 구분 사용

### 🏁 특이패턴 분석 제약사항

#### ✅ 시간대별/요일별 필터 조건
```sql
-- 심야시간 (23시-03시)
WHERE hour IN (23,0,1,2,3)
AND record_date BETWEEN '2025-07-15' AND '2025-07-31'

-- 러시아워 (평일만)
WHERE hour IN (6,7,8,17,18,19)
AND EXTRACT(DOW FROM record_date) BETWEEN 1 AND 5  -- 평일만
AND record_date BETWEEN '2025-07-15' AND '2025-07-31'

-- 주말
WHERE EXTRACT(DOW FROM record_date) IN (0,6)
AND record_date BETWEEN '2025-07-15' AND '2025-07-31'
```
**제약사항**: 특이패턴은 특정 시간대/요일 조건 + 날짜 범위 필수 적용

### ⚠️ 필수 조인 관계

#### ✅ 핵심 조인 키 (node_id 기준)
```sql
-- 정류장 정보 + 지역 매핑
FROM bus_stops bs
JOIN spatial_mapping sm ON bs.node_id = sm.node_id

-- 승하차 데이터 + 정류장 + 지역
FROM station_passenger_history sph
JOIN spatial_mapping sm ON sph.node_id = sm.node_id
LEFT JOIN bus_stops bs ON sph.node_id = bs.node_id
```
**제약사항**: node_id를 통한 조인이 핵심

### 상대적 시간 처리 규칙
- **"오늘"** → 현재 날짜가 데이터 범위 내라면 해당 날짜, 아니면 최신 데이터 날짜
- **"이번 달"** → 현재 월이 7월이라면 7월, 아니면 데이터 범위 설명
- **"최근"** → 2025년 7월 31일 (가장 최신 데이터)
- **데이터 범위 밖 요청시** → 사용자에게 데이터 범위 안내

### 🎯 종합 제약사항 요약
1. **시계열 데이터**: 2025-07-15 ~ 2025-07-31만 존재
2. **정류장 수**: 실제 교통량이 있는 운영정류장만 카운트 (station_passenger_history 존재 여부 확인)
3. **지역별 분석**: spatial_mapping 테이블 조인 필수
4. **교통량 계산**: 승차+하차 합계로 계산
5. **DRT 점수**: 모델별 전용 테이블 사용
6. **특이패턴**: 특정 시간대/요일 조건 + 날짜 범위 필수
7. **조인 키**: node_id를 통한 테이블 간 조인이 핵심



## 🚨 중요: 존재하지 않는 테이블 (절대 사용 금지)

❌ **사용 금지 테이블들** (실제 DB에 존재하지 않음):
- `mv_daily_hourly_traffic` (존재하지 않음)
- `traffic_summary` (존재하지 않음)
- `bus_station_traffic` (존재하지 않음)
- `daily_traffic_summary` (존재하지 않음)
- `hourly_traffic_summary` (존재하지 않음)

## 📋 테이블 조인 규칙 (실제 스키마 기준)

### ✅ 핵심 조인 패턴
```sql
-- 1. 정류장 + 지역 정보
FROM bus_stops bs
JOIN spatial_mapping sm ON bs.node_id = sm.node_id

-- 2. 교통량 + 지역 집계
FROM station_passenger_history sph
JOIN spatial_mapping sm ON sph.node_id = sm.node_id

-- 3. 노선 + 정류장 정보
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops bs ON rs.stop_id = bs.node_id
```

### 📊 집계 규칙
- **구별 집계**: `GROUP BY sm.sgg_name`
- **시간대별 분석**: `GROUP BY hour (0-23)`
- **월별 분석**: `DATE_TRUNC('month', record_date)`
- **정류장별 집계**: `GROUP BY node_id, station_name`
- **노선별 집계**: `GROUP BY route_id, route_name`

## 🚨 SQL 생성 전 필수 체크리스트 🚨

### ✅ 테이블명 확인
- **사용 가능**: `bus_stops`, `spatial_mapping`, `station_passenger_history`, `daily_od_analysis`
- **사용 금지**: `mv_daily_hourly_traffic`, `traffic_summary`, `bus_station_traffic`

### ✅ 컬럼명 확인
- **승하차 데이터**: `ride_passenger`, `alight_passenger` (정확한 컬럼명)
- **총 교통량**: `ride_passenger + alight_passenger`
- **지역명**: `sgg_name` (spatial_mapping 테이블)
- **정류장명**: `node_name` (bus_stops), `station_name` (station_passenger_history)

### ✅ 날짜 범위 확인
- **필수 조건**: `WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'`
- **존재하지 않는 날짜**: 2025-07-01 ~ 2025-07-14

## 🎯 질문 분석
**질문**: {question}
**예상 쿼리 유형**: {query_type.value}

다음 형식으로 답변해주세요:

```sql
-- 생성된 SQL 쿼리
SELECT ...
```

**설명**: 쿼리 작성 근거와 주요 로직 설명
**테이블**: 사용된 테이블명들
**컬럼**: 주요 컬럼명들
**예상결과**: 대략적인 결과 행 수와 실행 시간"""

        # 쿼리 타입별 추가 가이드
        if query_type == SQLQueryType.TIME_SERIES:
            base_prompt += """

### ⏰ 시계열 분석 특화 가이드
- `record_date`와 `hour` 필드 활용 필수
- 날짜 범위 필터링 필수: `WHERE record_date BETWEEN '2025-07-15' AND '2025-07-31'`
- `DATE_TRUNC('month', record_date)` 함수로 월별 집계
- `GROUP BY hour` 시간대별 패턴 분석
- Materialized View 우선 사용 권장 (성능 최적화)
"""

        elif query_type == SQLQueryType.AGGREGATION:
            base_prompt += """

### 📊 집계 분석 특화 가이드
- 실제 운영 정류장만 카운트: `EXISTS (SELECT 1 FROM station_passenger_history WHERE ...)`
- 교통량 계산: `SUM(ride_passenger + alight_passenger)`
- 구별 집계: `JOIN spatial_mapping` 필수
- TOP N 순위: `ORDER BY ... DESC LIMIT N`
- 집계 결과 필터링: `HAVING` 절 활용
- Materialized View 우선 사용 (mv_district_monthly_traffic 등)
"""

        elif query_type == SQLQueryType.SPATIAL:
            base_prompt += """

### 🗺️ 공간 분석 특화 가이드
- PostGIS 함수: `ST_Distance`, `ST_DWithin`, `ST_Buffer`
- 좌표 필드: `coordinates_x`, `coordinates_y`, `coordinates`
- 거리 계산: SRID 4326 (위경도) 사용
- 행정구역 매핑: `spatial_mapping` 테이블 JOIN 필수
- 서울시 범위: `WHERE is_seoul = TRUE`
"""

        return base_prompt

    def _parse_sql_response(self, response: str, query_type: SQLQueryType) -> SQLGenerationResult:
        """LLM 응답에서 SQL과 메타데이터 파싱"""

        try:
            # SQL 추출
            sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
            if sql_match:
                generated_sql = sql_match.group(1).strip().rstrip(';')
            else:
                # 백틱 없는 경우 SELECT로 시작하는 첫 번째 라인들 추출
                lines = response.split('\n')
                sql_lines = []
                sql_started = False
                for line in lines:
                    line = line.strip()
                    if line.upper().startswith('SELECT') or line.upper().startswith('WITH'):
                        sql_started = True
                    if sql_started:
                        if line.startswith('**') or line.startswith('###') or line.startswith('설명:'):
                            break
                        sql_lines.append(line)
                generated_sql = '\n'.join(sql_lines).strip()

            # 세미콜론 제거 (백엔드에서 서브쿼리 처리시 문법 오류 방지)
            generated_sql = generated_sql.rstrip(';')

            # 메타데이터 추출
            reasoning = self._extract_field(response, r'\*\*설명\*\*:?\s*(.*?)(?=\*\*|$)', "SQL 생성 완료")
            tables_used = self._extract_field(response, r'\*\*테이블\*\*:?\s*(.*?)(?=\*\*|$)', "").split(', ')
            columns_used = self._extract_field(response, r'\*\*컬럼\*\*:?\s*(.*?)(?=\*\*|$)', "").split(', ')

            # 신뢰도 계산
            confidence = self._calculate_confidence(generated_sql, reasoning, query_type)

            return SQLGenerationResult(
                generated_sql=generated_sql,
                query_type=query_type,
                confidence=confidence,
                reasoning=reasoning,
                tables_used=[t.strip() for t in tables_used if t.strip()],
                columns_used=[c.strip() for c in columns_used if c.strip()]
            )

        except Exception as e:
            logger.error(f"Failed to parse SQL response: {e}")
            return self._create_fallback_sql("파싱 실패")

    def _extract_field(self, text: str, pattern: str, default: str) -> str:
        """정규식으로 필드 추출"""
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else default

    def _calculate_confidence(self, sql: str, reasoning: str, query_type: SQLQueryType) -> float:
        """SQL 신뢰도 계산"""

        confidence = 0.5  # 기본값

        # SQL 구문 검사
        if sql and 'SELECT' in sql.upper():
            confidence += 0.2

        if 'FROM' in sql.upper():
            confidence += 0.1

        # 실제 존재하는 테이블명 검증 (2025년 실제 DB 스키마 기준)
        valid_tables = [
            # 📊 핵심 테이블 (실제 존재)
            'bus_stops',                    # 정류장 마스터 (20,590건, 18MB)
            'spatial_mapping',              # 정류장-지역 매핑 (17,615건, 6.4MB)
            'station_passenger_history',    # 승하차 데이터 (13,136,256건, 핵심)
            'daily_od_analysis',           # OD 분석 (21GB, 61개 컬럼)

            # 🚌 노선/운영 테이블 (실제 존재)
            'bus_routes',                  # 버스 노선 (232KB)
            'route_stops',                 # 노선-정류장 매핑 (37MB)
            'operation_schedules',         # 운행 스케줄 (168KB)
            'route_details',              # 노선 상세 (152KB)

            # 📈 시계열 테이블 (TimescaleDB, 실제 존재)
            'section_passenger_history',   # 구간별 승객수 (56KB)
            'section_speed_history',       # 구간별 운행시간 (56KB)
            'od_traffic_history',         # OD 통행량 (32KB)
            'station_passenger_history',   # 승하차 이력 (72KB)
            'road_traffic_history',       # 도로 교통 (72KB)

            # 🎯 DRT 점수 테이블 (실제 존재)
            'drt_commuter_scores',        # 출퇴근형 DRT (240MB)
            'drt_tourism_scores',         # 관광특화형 DRT (321MB)
            'drt_vulnerable_scores',      # 교통취약지형 DRT (111MB)

            # 🗺️ 지리/행정 테이블 (실제 존재)
            'admin_boundaries',           # 행정구역 경계 (632KB)
            'spatial_ref_sys',           # 좌표계 참조 (7MB)

            # 💾 관리/캐시 테이블 (실제 존재)
            'area_vulnerability_scores',   # 지역 취약성 (32KB)
            'poi_tourism_weights',        # POI 관광 가중치 (32KB)
            'population_cache',           # 인구 캐시 (16KB)
            'etl_job_status',            # ETL 작업 상태 (96KB)
            'etl_job_logs',              # ETL 로그 (40KB)

            # 📊 Materialized Views (성능 최적화용)
            'mv_seoul_hourly_patterns',
            'mv_hourly_traffic_patterns',
            'mv_station_hourly_patterns',
            'mv_district_monthly_traffic',
            'mv_station_monthly_traffic',
            'mv_monthly_od_summary',
            'monthly_district_traffic_summary'
        ]

        # 쿼리 타입별 가중치
        type_patterns = {
            SQLQueryType.TIME_SERIES: ['hour', 'record_date', 'DATE_TRUNC'],
            SQLQueryType.AGGREGATION: ['GROUP BY', 'SUM', 'COUNT', 'AVG'],
            SQLQueryType.SPATIAL: ['ST_', 'coordinates', 'geometry'],
            SQLQueryType.BASIC: ['WHERE', 'ORDER BY'],
            SQLQueryType.COMPLEX: ['JOIN', 'SUBQUERY', 'WITH', 'CASE WHEN']
        }

        # 실제 존재하는 테이블 사용 확인
        for table in valid_tables:
            if table in sql.lower():
                confidence += 0.05

        # 존재하지 않는 테이블 사용시 신뢰도 감소
        invalid_patterns = ['mv_daily_hourly_traffic', 'traffic_summary', 'bus_station_traffic']
        for pattern in invalid_patterns:
            if pattern in sql.lower():
                confidence -= 0.3

        # 필수 날짜 범위 확인
        if '2025-07-15' in sql and '2025-07-31' in sql:
            confidence += 0.1

        # 쿼리 타입별 패턴 확인
        if query_type in type_patterns:
            for pattern in type_patterns[query_type]:
                if pattern.lower() in sql.lower():
                    confidence += 0.1

        return min(max(confidence, 0.1), 1.0)  # 0.1 ~ 1.0 범위로 제한

    async def _validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """SQL 문법 검증 (실제 DB 연결 없이 기본 검증)"""

        try:
            # 기본 문법 검증
            if not sql or not sql.strip():
                return False, "빈 SQL 쿼리"

            sql_upper = sql.upper().strip()

            # SQL 시작 키워드 확인
            if not any(sql_upper.startswith(kw) for kw in ['SELECT', 'WITH']):
                return False, "유효하지 않은 SQL 시작 키워드"

            # 기본 구조 확인
            if 'SELECT' in sql_upper and 'FROM' not in sql_upper:
                return False, "FROM 절이 없습니다"

            # 위험한 키워드 확인 (읽기 전용)
            dangerous_keywords = ['DELETE', 'DROP', 'INSERT', 'UPDATE', 'TRUNCATE', 'ALTER']
            for keyword in dangerous_keywords:
                if keyword in sql_upper:
                    return False, f"허용되지 않은 키워드: {keyword}"

            # 균형 잡힌 괄호 확인
            if sql.count('(') != sql.count(')'):
                return False, "괄호 불균형"

            return True, None

        except Exception as e:
            return False, f"검증 오류: {str(e)}"

    async def _validate_and_retry_sql(self, initial_sql: str, question: str, max_retries: int = 3) -> Tuple[str, int]:
        """SQL 검증 및 재시도 로직 (최대 3회까지 재시도)"""

        current_sql = initial_sql
        attempts = 0
        error_history = []

        for attempt in range(max_retries + 1):  # 0번째는 초기 시도, 1-3번째는 재시도
            is_valid, validation_error = await self._validate_sql(current_sql)

            if is_valid:
                if attempt == 0:
                    logger.info("✅ SQL이 처음 시도에서 성공했습니다")
                else:
                    logger.info(f"✅ SQL이 {attempt}번째 재시도에서 성공했습니다")
                return current_sql, attempt

            attempts += 1
            error_history.append(validation_error)
            logger.warning(f"❌ SQL 검증 실패 (시도 {attempt + 1}/{max_retries + 1}): {validation_error}")

            if attempt < max_retries:  # 아직 재시도 가능
                # 더 상세한 수정 프롬프트 생성
                corrected_sql = await self._correct_sql_with_context(
                    current_sql,
                    validation_error,
                    question,
                    error_history,
                    attempt + 1
                )

                if corrected_sql:
                    current_sql = corrected_sql
                    logger.info(f"🔄 SQL 수정 완료 (시도 {attempt + 1})")
                else:
                    logger.warning(f"⚠️ SQL 수정 실패 (시도 {attempt + 1})")
                    break
            else:
                logger.error(f"❌ 최대 재시도 횟수 ({max_retries})에 도달했습니다")

        # 모든 시도 실패 시 마지막 SQL과 시도 횟수 반환
        return current_sql, attempts

    async def _correct_sql_with_context(
        self,
        sql: str,
        error: str,
        original_question: str,
        error_history: List[str],
        retry_count: int
    ) -> Optional[str]:
        """컨텍스트를 포함한 향상된 SQL 수정"""

        try:
            # 이전 오류들을 포함한 더 상세한 프롬프트
            error_context = ""
            if len(error_history) > 1:
                error_context = f"\n\n**이전 시도들에서 발생한 오류들:**\n"
                for i, prev_error in enumerate(error_history[:-1], 1):
                    error_context += f"시도 {i}: {prev_error}\n"

            correction_prompt = f"""당신은 PostgreSQL + TimescaleDB + PostGIS 전문가입니다.

다음 SQL 쿼리에 오류가 있습니다. **{retry_count}번째 수정 시도**입니다.

**원래 질문:** {original_question}

**현재 SQL:**
```sql
{sql}
```

**현재 오류:** {error}

{error_context}

**중요 지침:**
1. 테이블명과 컬럼명을 정확히 확인하고 사용하세요
2. PostgreSQL 문법을 정확히 따르세요
3. TimescaleDB 시계열 함수를 적절히 사용하세요
4. JOIN 조건을 명확히 지정하세요
5. 이전 오류를 반복하지 마세요

**수정된 SQL만 반환해주세요:**
```sql
-- 수정된 쿼리 (시도 {retry_count})
```"""

            response = await self.llm_service.generate_text(correction_prompt)

            # 수정된 SQL 추출
            sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
            if sql_match:
                corrected_sql = sql_match.group(1).strip()
                # 주석 제거
                corrected_sql = re.sub(r'--.*\n', '\n', corrected_sql).strip()
                return corrected_sql

            return None

        except Exception as e:
            logger.error(f"SQL correction failed on attempt {retry_count}: {e}")
            return None

    async def _correct_sql(self, sql: str, error: str) -> Optional[str]:
        """SQL 오류 자동 수정"""

        try:
            correction_prompt = f"""다음 SQL 쿼리에 오류가 있습니다. 수정해주세요.

**원본 SQL:**
```sql
{sql}
```

**오류:** {error}

**수정된 SQL만 반환해주세요:**
```sql
-- 수정된 쿼리
```"""

            response = await self.llm_service.generate_text(correction_prompt)

            # 수정된 SQL 추출
            sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
            if sql_match:
                corrected_sql = sql_match.group(1).strip()
                # 간단한 재검증
                is_valid, _ = await self._validate_sql(corrected_sql)
                if is_valid:
                    return corrected_sql

            return None

        except Exception as e:
            logger.error(f"SQL correction failed: {e}")
            return None

    def _create_fallback_sql(self, question: str) -> SQLGenerationResult:
        """폴백: 기본 쿼리 반환"""

        # 간단한 정류장 조회 쿼리
        fallback_sql = """
SELECT
    bs.node_id,
    bs.node_name,
    sm.sgg_name as district_name,
    bs.is_active
FROM bus_stops bs
JOIN spatial_mapping sm ON bs.node_id = sm.node_id
WHERE bs.is_active = true
  AND sm.is_seoul = true
ORDER BY bs.node_name
LIMIT 10;
"""

        return SQLGenerationResult(
            generated_sql=fallback_sql.strip(),
            query_type=SQLQueryType.BASIC,
            confidence=0.3,
            reasoning=f"질문 '{question}' 처리 실패로 인한 기본 쿼리",
            tables_used=['bus_stops', 'spatial_mapping'],
            columns_used=['node_id', 'node_name', 'sgg_name', 'is_active']
        )

    async def execute_sql(self, sql: str) -> Dict[str, Any]:
        """SQL 실행 (읽기 전용)"""

        try:
            # 백엔드 API를 통한 SQL 실행
            backend_url = getattr(settings, 'BACKEND_API_URL', 'http://localhost:8000')

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{backend_url}/api/v1/sql/execute",
                    json={"sql": sql, "read_only": True}
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "data": result.get("data", []),
                        "columns": result.get("columns", []),
                        "row_count": result.get("row_count", 0),
                        "execution_time": result.get("execution_time", 0)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"SQL 실행 실패: HTTP {response.status_code}",
                        "details": response.text
                    }

        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return {
                "success": False,
                "error": f"SQL 실행 오류: {str(e)}",
                "details": str(e)
            }

    async def health_check(self) -> bool:
        """서비스 상태 확인"""
        try:
            # 간단한 SQL 생성 테스트
            test_result = await self.generate_sql("활성화된 정류장 개수")
            return test_result.confidence > 0.3

        except Exception as e:
            logger.error(f"Text-to-SQL health check failed: {e}")
            return False


class TextToSQLException(RAGServiceException):
    """Text-to-SQL 서비스 관련 예외"""
    pass