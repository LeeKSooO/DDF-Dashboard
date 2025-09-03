# 🚀 하이브리드 RAG 시스템 전략서
## Vanna ChromaDB + Tag Chain 결합

## 📊 현황 분석

### 1. Vanna ChromaDB 구조 분석
Vanna는 3개의 벡터 컬렉션을 사용:
- **sql_collection**: 질문-SQL 쌍 저장
- **ddl_collection**: 테이블 스키마 정보
- **documentation_collection**: 비즈니스 로직 문서

### 2. 현재 문제점
- **태그 체인 시스템**: 키워드 기반이라 유연성 부족
- **Vanna 순수 방식**: LLM 의존도 높아 정확도 불안정

## 🎯 하이브리드 전략

### Phase 1: 학습 데이터셋 구축 전략

#### 1.1 질문-SQL 쌍 생성 (sql_collection)
```python
training_pairs = [
    # === 기본 집계 패턴 ===
    {
        "question": "강남구에 정류장이 몇 개 있어?",
        "sql": """
        SELECT COUNT(DISTINCT sm.node_id) as station_count
        FROM spatial_mapping sm 
        INNER JOIN bus_stops bs ON sm.node_id = bs.node_id
        WHERE sm.sgg_name = '강남구' AND bs.is_active = TRUE
        """
    },
    {
        "question": "강남구 정류장 개수는?", 
        "sql": "위와 동일"
    },
    {
        "question": "강남구에 있는 정류장 수를 알려줘",
        "sql": "위와 동일"
    },
    
    # === 승하차 패턴 ===
    {
        "question": "강남구 평일 승차 인원",
        "sql": """
        SELECT SUM(ride_count) as total_ride
        FROM station_passenger_history sph
        INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
        WHERE sm.sgg_name = '강남구'
        AND EXTRACT(DOW FROM sph.record_date) BETWEEN 1 AND 5
        """
    },
    {
        "question": "강남구에서 평일에 버스 타는 사람 수",
        "sql": "위와 동일"
    },
    {
        "question": "강남구 주중 탑승객",
        "sql": "위와 동일"
    },
    
    # === 시간대별 패턴 ===
    {
        "question": "강남구 아침 피크시간 승하차 인원",
        "sql": """
        SELECT hour, SUM(ride_count + alight_count) as traffic
        FROM station_passenger_history sph
        INNER JOIN spatial_mapping sm ON sph.node_id = sm.node_id
        WHERE sm.sgg_name = '강남구'
        AND hour BETWEEN 7 AND 9
        GROUP BY hour
        """
    },
    {
        "question": "강남구 출근 시간대 교통량",
        "sql": "위와 동일"
    },
    
    # === 비교 분석 패턴 ===
    {
        "question": "강남구와 서초구 정류장 수 비교",
        "sql": """
        SELECT 
            sm.sgg_name as district,
            COUNT(DISTINCT sm.node_id) as station_count
        FROM spatial_mapping sm 
        INNER JOIN bus_stops bs ON sm.node_id = bs.node_id
        WHERE sm.sgg_name IN ('강남구', '서초구')
        AND bs.is_active = TRUE
        GROUP BY sm.sgg_name
        """
    }
]
```

#### 1.2 DDL 정보 구조화 (ddl_collection)
```python
ddl_documents = [
    # 테이블별 스키마 + 설명
    """
    TABLE: bus_stops
    DESCRIPTION: 서울시 버스 정류장 정보
    COLUMNS:
    - node_id (VARCHAR): 정류장 고유 ID
    - node_name (VARCHAR): 정류장 이름
    - latitude (DECIMAL): 위도
    - longitude (DECIMAL): 경도
    - is_active (BOOLEAN): 운영 여부
    USAGE: 정류장 위치, 이름, 운영 상태 조회
    """,
    
    """
    TABLE: spatial_mapping
    DESCRIPTION: 정류장의 행정구역 매핑
    COLUMNS:
    - node_id (VARCHAR): 정류장 ID
    - sgg_name (VARCHAR): 구 이름 (강남구, 서초구 등)
    - emd_name (VARCHAR): 동 이름 (삼성동, 역삼동 등)
    USAGE: 구/동별 정류장 필터링
    """,
    
    """
    TABLE: station_passenger_history
    DESCRIPTION: 정류장별 시간대별 승하차 이력
    COLUMNS:
    - node_id (VARCHAR): 정류장 ID
    - record_date (DATE): 기록 날짜
    - hour (INTEGER): 시간 (0-23)
    - ride_count (INTEGER): 승차 인원
    - alight_count (INTEGER): 하차 인원
    - dispatch_count (INTEGER): 배차 수
    USAGE: 승하차 통계, 시간대별 분석, 요일별 패턴
    """
]
```

#### 1.3 비즈니스 로직 문서화 (documentation_collection)
```python
documentation = [
    """
    TERM: 피크시간
    DEFINITION: 
    - 아침 피크: 07:00-09:00
    - 저녁 피크: 17:00-20:00
    - 피크시간 전체: 07:00-09:00, 17:00-20:00
    SQL_PATTERN: hour BETWEEN 7 AND 9 OR hour BETWEEN 17 AND 20
    """,
    
    """
    TERM: 평일/주말
    DEFINITION:
    - 평일: 월요일-금요일 (DOW 1-5)
    - 주말: 토요일-일요일 (DOW 0, 6)
    SQL_PATTERN: 
    - 평일: EXTRACT(DOW FROM record_date) BETWEEN 1 AND 5
    - 주말: EXTRACT(DOW FROM record_date) IN (0, 6)
    """,
    
    """
    METRIC: 교통량
    DEFINITION: 승차 인원 + 하차 인원
    SQL_PATTERN: ride_count + alight_count
    SYNONYMS: 이용객, 승하차인원, 탑승객수
    """,
    
    """
    AGGREGATION: 정류장 개수
    DEFINITION: 특정 지역의 활성 정류장 수
    SQL_PATTERN: COUNT(DISTINCT node_id) WHERE is_active = TRUE
    COMMON_QUESTIONS: 몇개, 개수, 수량, 얼마나
    """
]
```

### Phase 2: 하이브리드 처리 프로세스

```python
class HybridRAGSystem:
    def __init__(self):
        self.tag_chain = TagChainSQLGenerator()  # 기존 태그 체인
        self.vector_store = ChromaDB_VectorStore()  # Vanna 벡터 스토어
        self.confidence_threshold = 0.85
    
    def process_question(self, question: str):
        # Step 1: 태그 체인 시도 (빠른 응답)
        tag_result = self.tag_chain.generate_sql(question)
        if tag_result.get('confidence', 0) >= self.confidence_threshold:
            return {
                'method': 'tag_chain',
                'sql': tag_result['sql'],
                'confidence': tag_result['confidence']
            }
        
        # Step 2: 벡터 검색 (유사 질문 찾기)
        similar_questions = self.vector_store.get_similar_question_sql(question)
        if similar_questions and self._calculate_similarity(question, similar_questions[0]) > 0.8:
            return {
                'method': 'vector_similarity',
                'sql': similar_questions[0]['sql'],
                'confidence': 0.9
            }
        
        # Step 3: 컨텍스트 강화 SQL 생성
        context = {
            'similar_questions': similar_questions[:3],
            'related_ddl': self.vector_store.get_related_ddl(question),
            'documentation': self.vector_store.get_related_documentation(question),
            'tag_hints': tag_result.get('extracted_tags', [])
        }
        
        # Step 4: LLM 생성 (최후의 수단)
        enhanced_sql = self._generate_with_context(question, context)
        
        return {
            'method': 'llm_generation',
            'sql': enhanced_sql,
            'confidence': 0.7
        }
```

### Phase 3: 학습 데이터 자동 확장

```python
def expand_training_data():
    """질문 변형을 통한 학습 데이터 자동 확장"""
    
    variations = {
        "정류장": ["정류소", "정거장", "버스정류장", "승강장"],
        "몇개": ["몇 개", "개수", "수", "얼마나", "총 몇"],
        "있어": ["있나", "있는지", "존재해", "위치해"],
        "강남구": ["강남", "강남지역", "강남구역"]
    }
    
    base_questions = [
        "강남구에 정류장이 몇개 있어?",
        "강남구 평일 승차 인원",
        "강남구 피크시간 교통량"
    ]
    
    expanded = []
    for question in base_questions:
        # 단어 치환으로 변형 생성
        for word, synonyms in variations.items():
            if word in question:
                for synonym in synonyms:
                    expanded.append(question.replace(word, synonym))
    
    return expanded
```

### Phase 4: 실시간 피드백 학습

```python
class FeedbackLearning:
    def learn_from_correction(self, question, wrong_sql, correct_sql):
        """사용자 수정으로부터 학습"""
        
        # 1. 새로운 question-sql 쌍 추가
        self.vector_store.add_question_sql(question, correct_sql)
        
        # 2. 유사 패턴 자동 생성
        patterns = self._extract_patterns(question, correct_sql)
        for pattern_q, pattern_sql in patterns:
            self.vector_store.add_question_sql(pattern_q, pattern_sql)
        
        # 3. 태그 체인 템플릿 업데이트 제안
        if self._is_new_pattern(question, correct_sql):
            self._suggest_template_update(question, correct_sql)
```

## 📈 기대 효과

### 정확도 향상
- 태그 체인: 80% → 60% (빠른 응답)
- 벡터 유사도: 30% → 90% (유연한 매칭)
- LLM 생성: 10% → 70% (컨텍스트 강화)
- **전체 정확도: 60-80% → 85-95%**

### 응답 시간
- 60%의 쿼리: <0.5초 (태그 체인)
- 30%의 쿼리: <1초 (벡터 검색)
- 10%의 쿼리: 2-3초 (LLM 생성)

### 유연성
- 동의어/유사어 자동 처리
- 문장 구조 변형 대응
- 새로운 패턴 자동 학습

## 🔧 구현 우선순위

1. **Phase 1**: ChromaDB에 학습 데이터 구축 (100+ 질문-SQL 쌍)
2. **Phase 2**: 하이브리드 처리 파이프라인 구현
3. **Phase 3**: 자동 확장 메커니즘 구축
4. **Phase 4**: 실시간 학습 시스템 추가

## 💡 핵심 인사이트

1. **태그 체인의 장점 유지**: 자주 사용되는 패턴은 빠르게 처리
2. **벡터 검색으로 유연성 확보**: 유사한 질문 찾아 SQL 재사용
3. **LLM은 최후의 수단**: 충분한 컨텍스트와 함께 사용
4. **지속적 학습**: 사용하면서 점점 똑똑해지는 시스템