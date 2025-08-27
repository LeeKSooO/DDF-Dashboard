# DRT Feature 구현 계획서

## 📋 개요

3가지 DRT 모델 (출퇴근형, 관광특화형, 교통취약지형)의 feature를 실제 DB 데이터로 구현하는 구체적인 계획서입니다.

---

## 🎯 구현 전략

### Phase 1: 핵심 Feature 구현 (우선순위 높음)
- **목표**: 각 모델의 동적 feature 9개 완전 구현
- **예상 완료율**: 75%
- **구현 방법**: Python ETL 스크립트 + SQL 쿼리

### Phase 2: POI 기반 Feature 보완 (우선순위 중간)  
- **목표**: 정적 가중치 3개 부분 구현
- **예상 완료율**: 추가 15-20%
- **구현 방법**: 공간 조인 + 기본값 할당

---

## 🚌 출퇴근형 DRT 모델 구현

### 1. TC_t (시간 집중도 지수) ✅
```sql
-- 구현 방법
WITH daily_max AS (
  SELECT route_id, node_id, record_date,
         MAX(dispatch_count) as max_dispatch
  FROM station_passenger_history 
  GROUP BY route_id, node_id, record_date
)
SELECT 
  sph.route_id, sph.node_id, sph.hour,
  CASE WHEN dm.max_dispatch > 0 
       THEN sph.dispatch_count::float / dm.max_dispatch 
       ELSE 0 END as TC_t
FROM station_passenger_history sph
JOIN daily_max dm USING (route_id, node_id, record_date)
```

**구현 상태**: ✅ 완전 구현 가능  
**데이터 소스**: `station_passenger_history.dispatch_count`  
**커버리지**: 100%

### 2. PDR_t (피크 수요 비율) ✅
```sql
-- 구현 방법
WITH daily_max_pax AS (
  SELECT route_id, node_id, record_date,
         MAX(ride_passenger + alight_passenger) as max_passengers
  FROM station_passenger_history 
  GROUP BY route_id, node_id, record_date
)
SELECT 
  sph.route_id, sph.node_id, sph.hour,
  (sph.ride_passenger + sph.alight_passenger) as total_pax,
  CASE WHEN dmp.max_passengers > 0 
       THEN (sph.ride_passenger + sph.alight_passenger)::float / dmp.max_passengers 
       ELSE 0 END as PDR_t
FROM station_passenger_history sph
JOIN daily_max_pax dmp USING (route_id, node_id, record_date)
```

**구현 상태**: ✅ 완전 구현 가능  
**데이터 소스**: `ride_passenger + alight_passenger`  
**커버리지**: 100%

### 3. RU_t (노선 활용도) ✅
```sql
-- 구현 방법
SELECT 
  route_id, from_node_id, to_node_id, hour,
  avg_passengers / 1000.0 as RU_t
FROM section_passenger_history
WHERE record_date = '2025-07-16'
```

**구현 상태**: ✅ 완전 구현 가능  
**데이터 소스**: `section_passenger_history.avg_passengers`  
**커버리지**: 100%

### 4. PCW (POI 카테고리 가중치) ⚠️
```python
# 구현 방법
def assign_poi_weights(node_id, coordinates):
    """정류장별 POI 가중치 할당"""
    
    # Step 1: 행정동 기반 POI 매핑
    admin_dong = get_admin_dong_by_coordinates(coordinates)
    
    # Step 2: POI CSV에서 해당 지역 카테고리 조회
    poi_category = poi_df[poi_df['area_includes'] == admin_dong]['CATEGORY'].iloc[0]
    
    # Step 3: 카테고리별 가중치 반환
    weights = {
        '인구밀집지역': 1.0,
        '발달상권': 0.8, 
        '관광특구': 0.6,
        '고궁·문화유산': 0.4,
        '공원': 0.2
    }
    return weights.get(poi_category, 0.5)  # 기본값 0.5
```

**구현 상태**: ⚠️ 부분 구현 (공간 조인 필요)  
**데이터 소스**: `seoul_poi_info.csv` + 공간 매핑  
**커버리지**: 30% (행정동 기반 근사치)

---

## 🏛️ 관광특화형 DRT 모델 구현

### 1. TC_t (관광 집중도) ✅
```sql
-- 구현 방법 (출퇴근형 + 관광시간 가중치)
WITH daily_max AS (
  SELECT route_id, node_id, record_date,
         MAX(dispatch_count) as max_dispatch
  FROM station_passenger_history 
  GROUP BY route_id, node_id, record_date
),
base_tc AS (
  SELECT 
    sph.route_id, sph.node_id, sph.hour,
    CASE WHEN dm.max_dispatch > 0 
         THEN sph.dispatch_count::float / dm.max_dispatch 
         ELSE 0 END as base_tc
  FROM station_passenger_history sph
  JOIN daily_max dm USING (route_id, node_id, record_date)
)
SELECT 
  route_id, node_id, hour,
  CASE WHEN hour BETWEEN 10 AND 16 
       THEN base_tc * 1.2  -- 관광시간 가중치 1.2
       ELSE base_tc END as TC_t_tourism
FROM base_tc
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 10-16시 관광시간 가중치 1.2 적용  
**커버리지**: 100%

### 2. TDR_t (관광 수요 비율) ✅
```sql
-- 구현 방법 (PDR 기반 + 관광시간 가중치 1.1)
SELECT 
  route_id, node_id, hour,
  CASE WHEN hour BETWEEN 10 AND 16 
       THEN pdr_base * 1.1  -- 관광시간 가중치 1.1
       ELSE pdr_base END as TDR_t
FROM (
  -- PDR_t 계산 로직과 동일
) pdr_calculation
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 10-16시 관광시간 가중치 1.1 적용  
**커버리지**: 100%

### 3. RU_t (구간 이용률 - 시간대별 분배) ✅
```python
# 구현 방법
def calculate_tourism_ru(hour, base_ru):
    """관광 시간대별 구간 이용률 분배"""
    if 10 <= hour <= 16:  # 관광시간
        return base_ru * 0.6
    else:  # 비관광시간  
        return base_ru * 0.4

# SQL 적용
SELECT 
  route_id, hour,
  CASE WHEN hour BETWEEN 10 AND 16 
       THEN (avg_passengers / 1000.0) * 0.6
       ELSE (avg_passengers / 1000.0) * 0.4 END as RU_t_tourism
FROM section_passenger_history
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 관광시간 60%, 비관광시간 40% 분배  
**커버리지**: 100%

### 4. PCW (POI 관광 가중치) ⚠️
```python
# 관광특화형 POI 가중치
tourism_weights = {
    '관광특구': 1.0,
    '고궁·문화유산': 0.9,
    '발달상권': 0.8,
    '공원': 0.7
}

def get_tourism_poi_weight(admin_dong):
    # POI 매핑 후 관광 가중치 반환
    return tourism_weights.get(poi_category, 0.7)  # 관광지역 기본값 0.7
```

**구현 상태**: ⚠️ 부분 구현  
**커버리지**: 40% (관광특구 데이터 활용도 높음)

---

## 🚑 교통취약지형 DRT 모델 구현

### 1. VAR_t (취약 접근성 비율) ✅
```python
# 취약 시간대 정의
VULNERABLE_HOURS = {
    'medical': [9, 10, 11],    # 의료시간 09-11시
    'welfare': [14, 15, 16],   # 복지시간 14-16시  
    'evening': [18, 19, 20]    # 저녁시간 18-20시
}

# 구현 SQL
WITH vulnerable_dispatch_sum AS (
  SELECT route_id, node_id, record_date,
         SUM(dispatch_count) as vuln_total
  FROM station_passenger_history
  WHERE hour IN (9,10,11,14,15,16,18,19,20)  -- 취약시간
  GROUP BY route_id, node_id, record_date
)
SELECT 
  sph.route_id, sph.node_id, sph.hour,
  CASE WHEN vds.vuln_total > 0
       THEN sph.dispatch_count::float / vds.vuln_total
       ELSE 0 END as VAR_t_base,
  -- 시간별 가중치 적용
  CASE 
    WHEN sph.hour IN (9,10,11) THEN VAR_t_base * 1.5  -- 의료시간 가중치
    WHEN sph.hour IN (14,15,16) THEN VAR_t_base * 1.3 -- 복지시간 가중치
    WHEN sph.hour IN (18,19,20) THEN VAR_t_base * 1.2 -- 저녁시간 가중치
    ELSE VAR_t_base 
  END as VAR_t
FROM station_passenger_history sph
JOIN vulnerable_dispatch_sum vds USING (route_id, node_id, record_date)
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 의료(1.5), 복지(1.3), 저녁(1.2) 시간별 가중치  
**커버리지**: 100%

### 2. SED_t (사회 형평성 수요) ✅
```sql
-- 구현 방법
WITH vulnerable_pax_sum AS (
  SELECT route_id, node_id, record_date,
         SUM(ride_passenger + alight_passenger) as vuln_pax_total
  FROM station_passenger_history
  WHERE hour IN (9,10,11,14,15,16,18,19,20)
  GROUP BY route_id, node_id, record_date
),
base_sed AS (
  SELECT 
    sph.route_id, sph.node_id, sph.hour,
    sph.ride_passenger + sph.alight_passenger as total_pax,
    CASE WHEN vps.vuln_pax_total > 0
         THEN (sph.ride_passenger + sph.alight_passenger)::float / vps.vuln_pax_total
         ELSE 0 END as SED_t_base
  FROM station_passenger_history sph
  JOIN vulnerable_pax_sum vps USING (route_id, node_id, record_date)
)
SELECT 
  route_id, node_id, hour, total_pax,
  CASE 
    WHEN total_pax < 100 AND hour IN (9,14,18) THEN SED_t_base * 1.4 * 1.2  -- 저이용+핵심시간
    WHEN total_pax < 100 THEN SED_t_base * 1.4  -- 저이용 구간 가중치
    WHEN hour IN (9,14,18) THEN SED_t_base * 1.2 -- 핵심 취약시간 가중치  
    ELSE SED_t_base 
  END as SED_t
FROM base_sed
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 저이용구간(1.4), 핵심취약시간(1.2) 가중치  
**커버리지**: 100%

### 3. MDI_t (이동성 불리 지수) ✅
```sql
-- 구현 방법 (역전 지수)
WITH section_mapped AS (
  SELECT 
    sph.route_id, sph.node_id, sph.hour,
    COALESCE(AVG(sec.avg_passengers), 0) as avg_section_pax
  FROM station_passenger_history sph
  LEFT JOIN section_passenger_history sec 
    ON sph.route_id = sec.route_id AND sph.hour = sec.hour
  GROUP BY sph.route_id, sph.node_id, sph.hour
)
SELECT 
  route_id, node_id, hour,
  (1000 - LEAST(avg_section_pax, 1000)) / 1000.0 as MDI_t_base,
  -- 취약/일반 시간대 분배
  CASE 
    WHEN hour IN (9,10,11,14,15,16,18,19,20) THEN MDI_t_base * 0.3  -- 취약시간 30%
    ELSE MDI_t_base * 0.7  -- 일반시간 70%
  END as MDI_t
FROM section_mapped
```

**구현 상태**: ✅ 완전 구현 가능  
**특이사항**: 역전지수 + 시간대별 분배 (취약30%, 일반70%)  
**커버리지**: 100%

### 4. AVS (지역 취약성 점수) ⚠️
```python
# 취약성 점수 매핑
vulnerability_scores = {
    '인구밀집지역': 0.9,
    '공원': 0.8,
    '고궁·문화유산': 0.7,
    '발달상권': 0.6,
    '관광특구': 0.5
}

def get_vulnerability_score(admin_dong):
    # 행정동 → POI 카테고리 매핑 후 취약성 점수 반환
    return vulnerability_scores.get(poi_category, 0.7)  # 취약지역 기본값
```

**구현 상태**: ⚠️ 부분 구현  
**커버리지**: 30% (POI 매핑 한계)

---

## 🛠️ 구현 아키텍처

### 1. ETL 파이프라인 구조
```
data/etl/traffic_feature/
├── drt_feature_generator.py    # 메인 ETL 스크립트
├── sql_queries/
│   ├── commute_features.sql    # 출퇴근형 쿼리
│   ├── tourism_features.sql    # 관광특화형 쿼리  
│   └── vulnerable_features.sql # 교통취약지형 쿼리
├── poi_mapper.py              # POI 공간 매핑 유틸
├── config.py                  # 가중치 설정
└── Dockerfile                 # 컨테이너화
```

### 2. 실행 순서
```bash
# Step 1: 기본 feature 계산 (동적)
python drt_feature_generator.py --model commute --date 2025-07-16

# Step 2: POI 가중치 매핑 (정적)  
python poi_mapper.py --input commute_features.csv --output final_features.csv

# Step 3: 최종 DRT 점수 계산
python calculate_drt_scores.py --input final_features.csv
```

### 3. 출력 데이터 형태
```csv
record_date,route_id,node_id,hour,TC_t,PDR_t,RU_t,PCW,commute_drt_score
2025-07-16,11-001,113000468,7,0.85,0.92,0.12,0.8,0.724
2025-07-16,11-001,113000468,8,1.0,1.0,0.15,0.8,0.785
...
```

---

## 📊 예상 성과

### 구현 완료 후 달성 목표
- **출퇴근형 DRT 모델**: 82.5% 정확도로 출퇴근 패턴 기반 DRT 필요도 분석
- **관광특화형 DRT 모델**: 85% 정확도로 관광지역 시간대별 수요 예측
- **교통취약지형 DRT 모델**: 82.5% 정확도로 사회적 약자 교통 지원 우선순위 도출

### 활용 방안
1. **대시보드 연동**: API를 통한 실시간 DRT 분석 제공
2. **정책 의사결정**: 3가지 모델 기반 DRT 도입 우선순위 수립  
3. **운영 최적화**: 시간대별/지역별 맞춤형 DRT 서비스 설계

---

## ⏱️ 구현 일정

| 단계 | 작업 내용 | 예상 소요시간 | 완료 기준 |
|------|----------|--------------|----------|
| **1주차** | 핵심 동적 feature 9개 구현 | 3일 | SQL 쿼리 + Python 스크립트 완성 |
| **2주차** | POI 매핑 로직 구현 | 2일 | 공간조인 + 기본값 할당 완료 |
| **3주차** | 테스트 및 검증 | 2일 | 샘플 데이터 검증 + 성능 튜닝 |

**총 예상 구현 기간: 7일**  
**최종 예상 커버리지: 82-85%**