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
    MATERIALIZED_VIEW = "mv"        # Materialized View 활용


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
                # 기본 인프라 테이블
                "bus_stops": {
                    "description": "서울시 버스 정류장 기본 정보 - 20,590건",
                    "type": "기본 테이블 (24MB)",
                    "columns": {
                        "node_id": "정류장ID (VARCHAR 50, PRIMARY KEY)",
                        "node_name": "정류장명 (VARCHAR 200, NOT NULL)",
                        "node_description": "정류장 설명 (VARCHAR 200)",
                        "node_num": "정류장 번호 (VARCHAR 20)",
                        "node_type": "노드 유형 (INTEGER, 기본값: 0)",
                        "coordinates_x": "경도 (NUMERIC 12,8)",
                        "coordinates_y": "위도 (NUMERIC 11,8)",
                        "coordinates": "PostGIS POINT 좌표 (GEOMETRY)",
                        "mapping_x": "매핑 경도 (NUMERIC 12,8)",
                        "mapping_y": "매핑 위도 (NUMERIC 11,8)",
                        "mapping_coordinates": "PostGIS 매핑 좌표 (GEOMETRY)",
                        "is_standard": "표준코드 여부 (BOOLEAN, 기본값: false)",
                        "is_active": "사용 여부 (BOOLEAN, 기본값: true)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "join_usage": "spatial_mapping과 JOIN으로 행정구역 정보 결합 필요",
                    "sample_queries": [
                        "활성 정류장만 조회: WHERE is_active = TRUE",
                        "좌표 기반 근처 정류장: ST_DWithin(coordinates, ST_Point(127.0, 37.5), 1000)",
                        "구별 정류장 조회: JOIN spatial_mapping ON bus_stops.node_id = spatial_mapping.node_id"
                    ]
                },

                "bus_routes": {
                    "description": "서울시 버스 노선 정보",
                    "type": "기본 테이블",
                    "columns": {
                        "route_id": "노선ID (PRIMARY KEY)",
                        "route_name": "노선명 (예: 1004, 9408)",
                        "route_type": "노선 유형 (1: 간선, 2: 지선, 3: 순환, 4: 광역, 5: 마을)",
                        "region_id": "지역ID",
                        "total_distance": "총 거리 (km)",
                        "start_point": "기점명",
                        "end_point": "종점명",
                        "authorized_vehicles": "인가 대수",
                        "is_operating": "운행 여부 (boolean)",
                        "created_at": "생성일시",
                        "updated_at": "수정일시"
                    },
                    "sample_queries": [
                        "간선버스 노선 개수",
                        "총 거리가 20km 이상인 노선들",
                        "현재 운행 중인 마을버스 개수"
                    ]
                },

                "route_stops": {
                    "description": "노선-정류장 매핑 테이블",
                    "type": "관계 테이블",
                    "columns": {
                        "id": "일련번호 (PRIMARY KEY)",
                        "route_id": "노선ID (FK -> bus_routes)",
                        "stop_id": "정류장ID (FK -> bus_stops)",
                        "node_sequence": "노드 순서",
                        "stop_sequence": "정류장 순서",
                        "section_id": "구간ID",
                        "cumulative_section_distance": "구간 누적거리",
                        "cumulative_stop_distance": "정류장 누적거리",
                        "direction_guide": "방향 안내",
                        "is_active": "사용 여부",
                        "created_at": "생성일시",
                        "updated_at": "수정일시"
                    },
                    "sample_queries": [
                        "1004번 버스가 정차하는 정류장 목록",
                        "특정 정류장을 지나는 노선 개수",
                        "노선별 정류장 개수"
                    ]
                },

                "spatial_mapping": {
                    "description": "정류장-행정구역 매핑 테이블 (성능 최적화용) - 17,615건",
                    "type": "매핑 테이블",
                    "columns": {
                        "node_id": "정류장ID (VARCHAR 50, PRIMARY KEY, FK -> bus_stops)",
                        "sido_code": "시도 코드 (VARCHAR 10, 기본값: '11')",
                        "sido_name": "시도명 (VARCHAR 50, 기본값: '서울특별시')",
                        "sgg_code": "시군구 코드 (VARCHAR 10, NOT NULL)",
                        "sgg_name": "시군구명 (VARCHAR 50, NOT NULL) - 강남구, 서초구 등 25개 구",
                        "adm_code": "행정동 코드 (VARCHAR 20)",
                        "adm_name": "행정동명 (VARCHAR 100)",
                        "is_seoul": "서울시 소속 여부 (BOOLEAN, 기본값: true)",
                        "is_major_stop": "주요 정류장 여부 (BOOLEAN, 기본값: false)",
                        "stop_type": "정류장 유형 (INTEGER)",
                        "created_at": "생성일시 (TIMESTAMP)",
                        "updated_at": "수정일시 (TIMESTAMP)"
                    },
                    "district_counts": {
                        "서초구": 1035, "강남구": 984, "영등포구": 981, "마포구": 964,
                        "강서구": 923, "송파구": 894, "성북구": 844, "노원구": 833
                    },
                    "sample_queries": [
                        "강남구 정류장 개수: WHERE sgg_name = '강남구' AND is_seoul = TRUE",
                        "구별 정류장 개수 순위: GROUP BY sgg_name ORDER BY COUNT(*) DESC",
                        "서울시 전체 정류장 수: WHERE is_seoul = TRUE"
                    ]
                },

                # 시계열 교통 데이터 (TimescaleDB 하이퍼테이블)
                "station_passenger_history": {
                    "description": "정류장별 시간당 승하차 인원 이력 (TimescaleDB 하이퍼테이블)",
                    "type": "시계열 테이블 (하이퍼테이블) - 13,136,256건",
                    "columns": {
                        "record_date": "기준일자 (DATE) - PRIMARY KEY 일부",
                        "route_id": "노선ID (VARCHAR 50) - PRIMARY KEY 일부",
                        "node_id": "정류장ID (VARCHAR 50) - PRIMARY KEY 일부",
                        "hour": "시간 (INTEGER 0-23) - PRIMARY KEY 일부",
                        "route_name": "노선명 (VARCHAR 100)",
                        "station_name": "정류장명 (VARCHAR 200)",
                        "station_sequence": "정류장 순번 (INTEGER)",
                        "dispatch_count": "배차수 (INTEGER, 기본값 0)",
                        "ride_passenger": "승차 인원 (INTEGER, 기본값 0) - 핵심 컬럼",
                        "alight_passenger": "하차 인원 (INTEGER, 기본값 0) - 핵심 컬럼",
                        "created_at": "생성일시 (TIMESTAMP)"
                    },
                    "data_period": "2025년 7월 19일 ~ 31일",
                    "key_formula": "총 교통량 = ride_passenger + alight_passenger",
                    "sample_queries": [
                        "2025년 7월 전체 서울시 교통량: SUM(ride_passenger + alight_passenger)",
                        "7월 상위 10개 정류장: GROUP BY node_id, station_name ORDER BY SUM(ride_passenger + alight_passenger) DESC",
                        "시간대별 교통량 패턴: GROUP BY hour ORDER BY hour"
                    ]
                },

                "section_passenger_history": {
                    "description": "구간별 시간당 승객수 이력 (TimescaleDB)",
                    "type": "시계열 테이블 (하이퍼테이블)",
                    "columns": {
                        "record_date": "기준일자",
                        "route_id": "노선ID",
                        "from_node_id": "출발 정류장ID",
                        "to_node_id": "도착 정류장ID",
                        "hour": "시간 (0-23)",
                        "station_sequence": "정류장 순번",
                        "passenger_count": "해당 시간대 승객수",
                        "daily_total_passengers": "일일 총 승객수",
                        "created_at": "생성일시"
                    },
                    "sample_queries": [
                        "강남역-서초역 구간 시간대별 승객수",
                        "승객수가 가장 많은 구간 TOP 10",
                        "특정 노선의 구간별 혼잡도"
                    ]
                },

                "section_speed_history": {
                    "description": "구간별 시간당 운행시간 이력 (TimescaleDB)",
                    "type": "시계열 테이블 (하이퍼테이블)",
                    "columns": {
                        "record_date": "기준일자",
                        "route_id": "노선ID",
                        "from_node_id": "출발 정류장ID",
                        "to_node_id": "도착 정류장ID",
                        "hour": "시간 (0-23)",
                        "from_station_sequence": "출발 정류장 순번",
                        "to_station_sequence": "도착 정류장 순번",
                        "trip_time": "운행시간 (분)",
                        "created_at": "생성일시"
                    },
                    "sample_queries": [
                        "출근시간 평균 운행시간이 긴 구간",
                        "노선별 평균 속도 비교",
                        "교통 체증이 심한 시간대와 구간"
                    ]
                },

                "od_traffic_history": {
                    "description": "행정동별 OD 통행량 이력 (TimescaleDB)",
                    "type": "시계열 테이블 (하이퍼테이블)",
                    "columns": {
                        "record_date": "기준일자",
                        "start_district": "출발 시군구",
                        "start_admin_dong": "출발 행정동",
                        "end_district": "도착 시군구",
                        "end_admin_dong": "도착 행정동",
                        "total_passenger_count": "총 통행량",
                        "created_at": "생성일시"
                    },
                    "sample_queries": [
                        "강남구에서 서초구로 가는 일일 통행량",
                        "통행량이 가장 많은 OD 쌍 TOP 10",
                        "특정 지역의 유입/유출 통행량"
                    ]
                },

                # 성능 최적화용 Materialized Views
                "mv_hourly_traffic_patterns": {
                    "description": "시간대별 교통량 패턴 집계 뷰 (성능 최적화)",
                    "type": "Materialized View",
                    "columns": {
                        "month_date": "월 기준일 (월별 집계)",
                        "day_type": "요일 구분 (weekday/weekend)",
                        "sgg_code": "시군구 코드",
                        "sgg_name": "시군구명",
                        "hour": "시간 (0-23)",
                        "avg_ride_passengers": "평균 승차 인원",
                        "avg_alight_passengers": "평균 하차 인원",
                        "avg_total_passengers": "평균 총 승객",
                        "max_ride_passengers": "최대 승차 인원",
                        "max_alight_passengers": "최대 하차 인원",
                        "station_count": "정류장 수",
                        "day_count": "운영일 수"
                    },
                    "sample_queries": [
                        "강남구 평일 출근시간 평균 승차 인원",
                        "주말 vs 평일 교통량 비교",
                        "구별 시간대별 교통량 히트맵 데이터"
                    ]
                },

                "mv_district_monthly_traffic": {
                    "description": "구별 월간 교통량 총계 뷰 (히트맵용)",
                    "type": "Materialized View",
                    "columns": {
                        "month_date": "월 기준일",
                        "district_code": "구 코드",
                        "district_name": "구명",
                        "total_ride": "총 승차 인원",
                        "total_alight": "총 하차 인원",
                        "total_traffic": "총 교통량",
                        "avg_daily_traffic": "일평균 교통량",
                        "station_count": "정류장 수",
                        "operating_days": "운영일 수",
                        "q1_traffic": "교통량 1분위수",
                        "q2_traffic": "교통량 중위수",
                        "q3_traffic": "교통량 3분위수",
                        "max_hourly_traffic": "최대 시간당 교통량"
                    },
                    "sample_queries": [
                        "2024년 8월 구별 총 교통량 순위",
                        "월별 교통량 증감률",
                        "교통량 분위수 기준 구 분류"
                    ]
                }
            },

            "relationships": {
                "bus_routes → route_stops": "route_id로 연결 (1:N)",
                "bus_stops → route_stops": "node_id = stop_id로 연결 (1:N)",
                "bus_stops → spatial_mapping": "node_id로 연결 (1:1)",
                "bus_stops → station_passenger_history": "node_id로 연결 (1:N)",
                "bus_routes → station_passenger_history": "route_id로 연결 (1:N)",
                "bus_routes → section_passenger_history": "route_id로 연결 (1:N)",
                "bus_routes → section_speed_history": "route_id로 연결 (1:N)"
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

        question_lower = question.lower()
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
        agg_patterns = ['개수', '총', '평균', '최대', '최소', '합계', '순위', 'top', '상위', '하위']
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

## 실제 데이터베이스 정보 (2025년 7월 기준)
- 데이터베이스: PostgreSQL + TimescaleDB + PostGIS
- 도메인: 서울시 대중교통 및 DRT(수요응답형 교통) 데이터
- 실제 데이터 기간: 2025년 7월 19일 ~ 31일
- 주요 데이터: 13,136,256건 (station_passenger_history)

## 주요 테이블 스키마

### 1. 핵심 테이블 (실제 존재하는 테이블만)
```sql
-- 정류장 정보 (20,590건)
bus_stops (
    node_id VARCHAR(50) PRIMARY KEY,       -- 정류장ID
    node_name VARCHAR(200) NOT NULL,       -- 정류장명
    coordinates_x NUMERIC(12,8),           -- 경도
    coordinates_y NUMERIC(11,8),           -- 위도
    coordinates GEOMETRY(POINT, 4326),     -- PostGIS 좌표
    is_active BOOLEAN DEFAULT TRUE         -- 사용여부
);

-- 정류장-행정구역 매핑 (17,615건)
spatial_mapping (
    node_id VARCHAR(50) PRIMARY KEY,       -- 정류장ID (FK -> bus_stops)
    sgg_name VARCHAR(50) NOT NULL,         -- 시군구명 (강남구, 서초구 등)
    adm_name VARCHAR(100),                 -- 행정동명
    is_seoul BOOLEAN DEFAULT TRUE          -- 서울시 여부
);

-- ⭐ 교통량 데이터 (TimescaleDB, 13,136,256건)
station_passenger_history (
    record_date DATE NOT NULL,             -- 기준일자 (2025-07-19 ~ 2025-07-31)
    route_id VARCHAR(50) NOT NULL,         -- 노선ID
    node_id VARCHAR(50) NOT NULL,          -- 정류장ID
    hour INTEGER NOT NULL,                 -- 시간 (0-23)
    route_name VARCHAR(100),               -- 노선명
    station_name VARCHAR(200),             -- 정류장명
    ride_passenger INTEGER DEFAULT 0,      -- 승차인원 ⭐⭐⭐
    alight_passenger INTEGER DEFAULT 0,    -- 하차인원 ⭐⭐⭐
    PRIMARY KEY (record_date, route_id, node_id, hour)
);

-- 노선-정류장 매핑
route_stops (
    route_id VARCHAR(50),                 -- 노선ID (FK)
    stop_id VARCHAR(50),                  -- 정류장ID (FK)
    node_sequence INTEGER,                -- 노드순서
    cumulative_stop_distance DECIMAL(10,2) -- 누적거리
)

-- 정류장-행정구역 매핑 (성능 최적화용)
spatial_mapping (
    node_id VARCHAR(50) PRIMARY KEY,      -- 정류장ID
    sgg_name VARCHAR(50),                 -- 시군구명 (강남구, 서초구 등)
    adm_name VARCHAR(100),                -- 행정동명
    is_seoul BOOLEAN DEFAULT TRUE         -- 서울시 소속여부
)
```

### 2. 시계열 교통 데이터 (TimescaleDB 하이퍼테이블)
```sql
-- 정류장별 시간당 승하차 인원
station_passenger_history (
    record_date DATE,                     -- 기준일자
    route_id VARCHAR(50),                 -- 노선ID
    node_id VARCHAR(50),                  -- 정류장ID
    hour INTEGER,                         -- 시간 (0-23)
    route_name VARCHAR(100),              -- 노선명
    station_name VARCHAR(200),            -- 정류장명
    ride_passenger INTEGER,               -- 승차인원 (시간당)
    alight_passenger INTEGER,             -- 하차인원 (시간당)
    PRIMARY KEY (record_date, route_id, node_id, hour)
)

-- 구간별 시간당 승객수
section_passenger_history (
    record_date DATE,                     -- 기준일자
    route_id VARCHAR(50),                 -- 노선ID
    from_node_id VARCHAR(50),             -- 출발정류장ID
    to_node_id VARCHAR(50),               -- 도착정류장ID
    hour INTEGER,                         -- 시간 (0-23)
    passenger_count INTEGER,              -- 승객수 (시간당)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
)

-- 구간별 시간당 운행시간
section_speed_history (
    record_date DATE,                     -- 기준일자
    route_id VARCHAR(50),                 -- 노선ID
    from_node_id VARCHAR(50),             -- 출발정류장ID
    to_node_id VARCHAR(50),               -- 도착정류장ID
    hour INTEGER,                         -- 시간 (0-23)
    trip_time INTEGER,                    -- 운행시간 (분)
    PRIMARY KEY (record_date, route_id, from_node_id, to_node_id, hour)
)
```

### 3. 성능 최적화용 Materialized Views
```sql
-- 시간대별 교통량 패턴 (구별 + 시간별 집계)
mv_hourly_traffic_patterns (
    month_date DATE,                      -- 월 기준일
    day_type VARCHAR(10),                 -- weekday/weekend
    sgg_name VARCHAR(50),                 -- 구명
    hour INTEGER,                         -- 시간
    avg_ride_passengers NUMERIC(10,2),    -- 평균 승차인원
    avg_alight_passengers NUMERIC(10,2),  -- 평균 하차인원
    avg_total_passengers NUMERIC(10,2),   -- 평균 총승객
    station_count INTEGER                 -- 정류장수
)

-- 구별 월간 교통량 총계
mv_district_monthly_traffic (
    month_date DATE,                      -- 월 기준일
    district_name VARCHAR(50),            -- 구명
    total_traffic BIGINT,                 -- 총 교통량
    avg_daily_traffic NUMERIC(10,2),      -- 일평균 교통량
    station_count INTEGER                 -- 정류장수
)
```

### 4. DRT(수요응답형 교통) 관련 테이블
```sql
-- MST-GCN용 DRT 피처 테이블 (TimescaleDB 하이퍼테이블)
drt_features_mstgcn (
    feature_id BIGSERIAL,
    stop_id VARCHAR(50),                  -- 정류장ID (FK)
    recorded_at TIMESTAMP,                -- 기록시간 (파티션 키)
    normalized_log_boarding_count DECIMAL(8,4),  -- 정규화된 승차인원
    service_availability INTEGER,         -- 서비스 가용성 (0:비운행, 1:시간외, 2:시간내)
    is_rest_day BOOLEAN,                  -- 휴일여부 (주말+공휴일)
    normalized_interval DECIMAL(8,4),     -- 정규화된 배차간격
    hour_of_day INTEGER,                  -- 시간 (0-23)
    day_of_week INTEGER,                  -- 요일 (0=일요일)
    drt_probability DECIMAL(8,4),         -- DRT 수요 확률 (0~1)
    PRIMARY KEY (feature_id, recorded_at)
)

-- 정류장 공간 특성 정보
stop_spatial_features (
    stop_id VARCHAR(50) PRIMARY KEY,      -- 정류장ID
    latitude DECIMAL(10, 8),              -- 위도
    longitude DECIMAL(11, 8),             -- 경도
    district VARCHAR(50),                 -- 지역구
    total_routes INTEGER,                 -- 경유 노선수
    avg_interval_minutes INTEGER,         -- 평균 배차간격(분)
    accessibility_level VARCHAR(20),      -- 접근성 수준
    drt_potential_level VARCHAR(30),      -- DRT 잠재성 수준
    isolation_score DECIMAL(5,3)          -- 교통 격리도 (0~1)
)

-- 예측 모델 메타데이터
model_metadata (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100),              -- 모델명
    model_version VARCHAR(50),            -- 버전
    model_type VARCHAR(50),               -- 모델 타입 (MSTGCN 등)
    metrics JSONB,                        -- 성능 지표 JSON
    hyperparameters JSONB,                -- 하이퍼파라미터 JSON
    is_active BOOLEAN,                    -- 활성 모델 여부
    created_at TIMESTAMP
)

-- 예측 결과 저장
predictions (
    prediction_id SERIAL PRIMARY KEY,
    request_id UUID,                      -- 요청 그룹 ID
    stop_id VARCHAR(50),                  -- 정류장ID
    prediction_time TIMESTAMP,            -- 예측 수행 시점
    target_time TIMESTAMP,                -- 예측 대상 시점
    drt_probability DECIMAL(10, 4),       -- 예측된 DRT 확률
    predicted_boarding_count DECIMAL(10, 2), -- 예측 승차인원
    model_id INTEGER,                     -- 사용된 모델ID
    confidence_interval JSONB             -- 신뢰구간 JSON
)
```

## ⭐ 핵심 쿼리 작성 가이드라인 (실제 데이터 기준)

### 🔥 중요: 실제 데이터 정보 & 시간 기반 쿼리
- 데이터 기간: **2025년 7월 19일 ~ 31일만** 존재
- 날짜 조건: WHERE record_date >= '2025-07-19' AND record_date <= '2025-07-31'
- 핵심 공식: **총 교통량 = ride_passenger + alight_passenger**

### 상대적 시간 처리 규칙
- "오늘" → 현재 날짜가 데이터 범위 내라면 해당 날짜, 아니면 최신 데이터 날짜
- "이번 달" → 현재 월이 7월이라면 7월, 아니면 데이터 범위 설명
- "최근" → 2025년 7월 31일 (가장 최신 데이터)
- 데이터 범위 밖 요청시 → 사용자에게 데이터 범위 안내

### 필수 패턴
1. **서울시 전체 교통량**
   ```sql
   SELECT SUM(ride_passenger + alight_passenger) AS total_traffic
   FROM station_passenger_history
   WHERE record_date >= '2025-07-19';
   ```

2. **구별 정류장 개수**
   ```sql
   SELECT COUNT(DISTINCT sm.node_id) AS stop_count
   FROM spatial_mapping sm
   JOIN bus_stops bs ON sm.node_id = bs.node_id
   WHERE sm.sgg_name = '강남구' AND bs.is_active = TRUE;
   ```

3. **상위 정류장 조회**
   ```sql
   SELECT node_id, station_name, SUM(ride_passenger + alight_passenger) AS total
   FROM station_passenger_history
   GROUP BY node_id, station_name
   ORDER BY total DESC LIMIT 10;
   ```

### 테이블 조인 규칙
- **행정구역 정보 필요시**: spatial_mapping JOIN bus_stops
- **구별 집계시**: GROUP BY spatial_mapping.sgg_name
- **시간대별 분석**: GROUP BY hour (0-23)
- **월별 분석**: DATE_TRUNC('month', record_date)

## 질문: {question}
예상 쿼리 유형: {query_type.value}

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

### 시계열 분석 특화 가이드
- record_date와 hour 필드 활용
- 시간 범위 필터링 필수 (성능상 중요)
- DATE_TRUNC 함수로 월별/일별 집계
- mv_hourly_traffic_patterns 우선 활용 권장
"""

        elif query_type == SQLQueryType.AGGREGATION:
            base_prompt += """

### 집계 분석 특화 가이드
- GROUP BY와 적절한 집계 함수 사용
- COUNT, SUM, AVG, MAX, MIN 활용
- HAVING 절로 집계 결과 필터링
- ORDER BY로 순위 정렬
- LIMIT으로 TOP N 결과 제한
"""

        elif query_type == SQLQueryType.SPATIAL:
            base_prompt += """

### 공간 분석 특화 가이드
- PostGIS 함수 활용: ST_Distance, ST_DWithin, ST_Buffer
- coordinates GEOMETRY 필드 사용
- 거리 계산시 SRID 4326 (위경도) 고려
- spatial_mapping 테이블로 행정구역 매핑
"""

        return base_prompt

    def _parse_sql_response(self, response: str, query_type: SQLQueryType) -> SQLGenerationResult:
        """LLM 응답에서 SQL과 메타데이터 파싱"""

        try:
            # SQL 추출
            sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
            if sql_match:
                generated_sql = sql_match.group(1).strip()
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

        # 실제 존재하는 테이블명 검증 (2025년 7월 실데이터 기준)
        valid_tables = [
            # 기본 인프라 테이블 (실제 존재)
            'bus_stops', 'bus_routes', 'route_stops', 'spatial_mapping',
            # TimescaleDB 시계열 테이블 (실제 존재)
            'station_passenger_history', 'section_passenger_history',
            'od_traffic_history', 'section_speed_history', 'road_traffic_history',
            # 관리/설정 테이블 (실제 존재)
            'etl_job_logs', 'etl_job_status', 'operation_schedules', 'route_details',
            # 행정구역/공간 테이블 (실제 존재)
            'admin_boundaries', 'spatial_ref_sys',
            # DRT 스코어 테이블 (스키마만 존재, 데이터 없음)
            'drt_commuter_scores', 'drt_tourism_scores', 'drt_vulnerable_scores',
            # 캐시/설정 테이블 (실제 존재)
            'population_cache', 'area_vulnerability_scores', 'poi_tourism_weights'
        ]

        for table in valid_tables:
            if table in sql.lower():
                confidence += 0.05

        # 쿼리 타입별 가중치
        type_patterns = {
            SQLQueryType.TIME_SERIES: ['hour', 'record_date', 'DATE_TRUNC'],
            SQLQueryType.AGGREGATION: ['GROUP BY', 'SUM', 'COUNT', 'AVG'],
            SQLQueryType.SPATIAL: ['ST_', 'coordinates', 'geometry'],
            SQLQueryType.BASIC: ['WHERE', 'ORDER BY']
        }

        if query_type in type_patterns:
            for pattern in type_patterns[query_type]:
                if pattern.lower() in sql.lower():
                    confidence += 0.1

        return min(confidence, 1.0)

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
                    f"{backend_url}/api/sql/execute",
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