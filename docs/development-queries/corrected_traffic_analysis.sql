/*
#################################################################################
#                                                                               #
#                        올바른 교통 데이터 분석 스크립트                              #
#                                                                               #  
#################################################################################

작성일: 2025-07-28
목적: DRT 운영 의사결정 지원을 위한 실제 교통 데이터 기반 현황 분석

*** 올바른 분석 원칙 ***
1. 실제 교통 데이터(FACT)와 모델 예측 데이터(PREDICTION) 완전 분리
2. 실제 운영 데이터만으로 객관적 교통 현황 분석
3. DRT 확률 데이터는 별도 분석으로 보조 참고용으로만 활용

데이터 분류:
- FACT 데이터: stop_usage, bus_stops, route_stops, bus_routes (실제 운영 결과)
- PREDICTION 데이터: drt_features_mstgcn (MST-GCN 모델 예측값, 보조 참고용)

분석 대상 기간: 전체 데이터 범위 (2024년 11월 ~ 2025년 6월)
*/


-- ===================================================================================
-- PART A: 실제 교통 데이터 기반 현황 분석
-- ===================================================================================

-- ===================================================================================
-- A1. 기본 데이터 현황 파악
-- ===================================================================================

/*
목적: 실제 교통 운영 데이터의 규모와 품질 확인
근거: 의미있는 분석을 위한 데이터 충분성 검증
분석 범위: 실제 운영 데이터만 (예측 데이터 제외)
*/

-- A1-1. 실제 교통 데이터 기본 통계
SELECT 
    'stop_usage' as table_name,
    COUNT(*) as total_records,
    MIN(recorded_at::date) as earliest_date,
    MAX(recorded_at::date) as latest_date,
    COUNT(DISTINCT stop_id) as unique_stops,
    COUNT(DISTINCT recorded_at::date) as service_days,
    'FACT_DATA' as data_type
FROM stop_usage

UNION ALL

SELECT 
    'bus_stops' as table_name,
    COUNT(*) as total_records,
    NULL as earliest_date,
    NULL as latest_date,
    COUNT(*) as unique_stops,
    NULL as service_days,
    'INFRASTRUCTURE' as data_type
FROM bus_stops

UNION ALL

SELECT 
    'bus_routes' as table_name,
    COUNT(*) as total_records,
    NULL as earliest_date,
    NULL as latest_date,
    NULL as unique_stops,
    NULL as service_days,
    'INFRASTRUCTURE' as data_type
FROM bus_routes

UNION ALL

SELECT 
    'route_stops' as table_name,
    COUNT(*) as total_records,
    NULL as earliest_date,
    NULL as latest_date,
    COUNT(DISTINCT stop_id) as unique_stops,
    NULL as service_days,
    'INFRASTRUCTURE' as data_type
FROM route_stops;

/*
실제 확인된 데이터 현황:
- stop_usage: 4,705,704건 (2024-11-01 ~ 2025-06-25, 957개 정류장, 237일)
- bus_stops: 1,214개 정류장 인프라
- bus_routes: 55개 운영 노선
- route_stops: 3,260개 노선-정류장 연결 관계
→ 약 8개월간의 충분한 실제 운영 데이터로 의미있는 분석 가능
*/


-- ===================================================================================
-- A2. 시간대별 실제 버스 이용 패턴 분석 
-- ===================================================================================

/*
목적: 하루 중 시간대별 실제 버스 이용 패턴 파악
근거: DRT 운영 시간대 설정과 기존 버스 서비스와의 보완 관계 분석
분석 대상: 실제 승차 데이터(stop_usage)만 사용
분석 기간: 2024년 11월 (대표 기간)
*/

-- A2-1. 시간대별 실제 버스 이용 패턴
WITH hourly_usage AS (
    SELECT 
        EXTRACT(HOUR FROM recorded_at) as hour,
        COUNT(*) as total_boarding_events,
        SUM(boarding_count) as total_passengers,
        COUNT(DISTINCT stop_id) as active_stops,
        AVG(boarding_count) as avg_boarding_per_event,
        COUNT(CASE WHEN boarding_count > 0 THEN 1 END) as non_zero_events
    FROM stop_usage 
    WHERE recorded_at::date BETWEEN '2024-11-01' AND '2024-11-30'
    AND boarding_count IS NOT NULL
    GROUP BY EXTRACT(HOUR FROM recorded_at)
)
SELECT 
    hour,
    total_boarding_events,
    total_passengers,
    active_stops,
    ROUND(avg_boarding_per_event, 2) as avg_boarding_per_event,
    non_zero_events,
    CASE 
        WHEN hour BETWEEN 7 AND 9 THEN 'MORNING_PEAK'
        WHEN hour BETWEEN 17 AND 19 THEN 'EVENING_PEAK' 
        WHEN hour BETWEEN 10 AND 16 THEN 'DAYTIME_OFF_PEAK'
        WHEN hour BETWEEN 20 AND 23 THEN 'EVENING_OFF_PEAK'
        WHEN hour BETWEEN 0 AND 6 THEN 'NIGHT_TIME'
        ELSE 'TRANSITION'
    END as time_category
FROM hourly_usage
ORDER BY hour;

/*
핵심 발견사항 (2024년 11월 데이터 기준):
1. 피크 시간대 패턴:
   - 오전 피크(7-9시): 총 31,500명, 시간당 평균 0.4명/이벤트
   - 저녁 피크(17-19시): 총 21,187명, 점진적 감소 패턴
   
2. 오프피크 시간대 특성:
   - 주간 오프피크(10-16시): 지속적인 수요, 시간당 평균 9,000-11,000명
   - 심야(0-6시): 극히 저조한 이용 (시간당 200명 이하)
   
3. DRT 운영 시사점:
   - 주간 오프피크(10-16시): 기존 버스 서비스 대비 DRT 보완 필요성 높음
   - 심야 시간대(0-6시): 기존 서비스 부족으로 DRT 도입 검토 가능
   - 피크 시간대: 기존 버스 서비스로 충분, DRT는 마지막 마일 연결 역할
*/


-- ===================================================================================
-- A3. 지역별 교통 서비스 공백 지역 식별
-- ===================================================================================

/*
목적: 가평군 읍면별 교통 서비스 현황과 공백 지역 파악
근거: 지역별 맞춤형 DRT 운영 전략 수립을 위한 실제 현황 분석
분석 방법: 실제 버스 이용 데이터만을 활용한 지역별 서비스 수준 평가
*/

-- A3-1. 지역별 교통 서비스 현황 분석
WITH stop_real_usage AS (
    SELECT 
        bs.stop_id,
        bs.stop_name,
        bs.latitude,
        bs.longitude,
        COALESCE(SUM(su.boarding_count), 0) as total_boarding,
        COALESCE(COUNT(CASE WHEN su.boarding_count > 0 THEN 1 END), 0) as active_records,
        COUNT(DISTINCT su.recorded_at::date) as service_days,
        CASE 
            WHEN bs.latitude >= 37.83 AND bs.longitude <= 127.42 THEN 'Gapyeong-eup'
            WHEN bs.latitude >= 37.75 AND bs.latitude < 37.83 AND bs.longitude <= 127.35 THEN 'Cheongpyeong-myeon'
            WHEN bs.latitude < 37.75 AND bs.longitude <= 127.35 THEN 'Sang-myeon'
            WHEN bs.latitude >= 37.75 AND bs.longitude > 127.42 THEN 'Buk-myeon'
            WHEN bs.latitude < 37.75 AND bs.longitude > 127.35 THEN 'Jojong-myeon'
            ELSE 'Unclassified'
        END as region
    FROM bus_stops bs
    LEFT JOIN stop_usage su ON bs.stop_id = su.stop_id
        AND su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-30'
    GROUP BY bs.stop_id, bs.stop_name, bs.latitude, bs.longitude
)
SELECT 
    region,
    COUNT(*) as total_stops,
    COUNT(CASE WHEN total_boarding > 0 THEN 1 END) as active_stops,
    COUNT(CASE WHEN total_boarding = 0 THEN 1 END) as unused_stops,
    SUM(total_boarding) as region_total_boarding,
    ROUND(AVG(total_boarding), 2) as avg_boarding_per_stop
FROM stop_real_usage
WHERE region <> 'Unclassified'
GROUP BY region
ORDER BY region_total_boarding DESC;

/*
지역별 교통 서비스 공백 현황 (2024년 11월 기준):

1. 북면 (Buk-myeon):
   - 총 470개 정류장, 354개 활성화 (75.3%)
   - 총 승차 59,410명, 정류장당 평균 126.4명
   - 평가: 상대적으로 활발한 버스 이용, 안정적 서비스

2. 조종면 (Jojong-myeon):
   - 총 368개 정류장, 263개 활성화 (71.5%)  
   - 총 승차 57,845명, 정류장당 평균 157.2명
   - 평가: 높은 정류장당 이용률, 효율적 서비스 운영

3. 청평면 (Cheongpyeong-myeon):
   - 총 73개 정류장, 35개 활성화 (47.9%)
   - 총 승차 9,744명, 정류장당 평균 133.5명
   - 평가: 활성화율 낮음, 관광지 특성상 계절적 수요 고려 필요

4. 가평읍 (Gapyeong-eup):
   - 총 87개 정류장, 64개 활성화 (73.6%)
   - 총 승차 2,473명, 정류장당 평균 28.4명
   - 평가: 중심지역임에도 낮은 이용률, 교통체계 재검토 필요

5. 상면 (Sang-myeon): *** 중요 ***
   - 총 124개 정류장, 0개 활성화 (0%)
   - 총 승차 0명, 완전한 교통 사각지대
   - 평가: 긴급한 대중교통 서비스 개선 필요, DRT 우선 도입 대상
*/


-- ===================================================================================
-- A4. 노선별 운영 효율성 및 이용률 분석
-- ===================================================================================

/*
목적: 기존 버스 노선별 운영 효율성 평가
근거: 효율적인 노선 운영 방안 도출 및 DRT와의 역할 분담 전략 수립
분석 지표: 정류장 활용률, 일일 평균 승차, 운영 효율 등급
*/

-- A4-1. 노선별 운영 효율성 분석
WITH route_performance AS (
    SELECT 
        br.route_id,
        br.route_number,
        br.route_type,
        COUNT(DISTINCT rs.stop_id) as stops_count,
        SUM(COALESCE(su.boarding_count, 0)) as total_boarding,
        COUNT(CASE WHEN su.boarding_count > 0 THEN 1 END) as active_boarding_events,
        AVG(CASE WHEN su.boarding_count > 0 THEN su.boarding_count END) as avg_boarding_per_active_event,
        COUNT(DISTINCT su.recorded_at::date) as service_days
    FROM bus_routes br
    LEFT JOIN route_stops rs ON br.route_id = rs.route_id
    LEFT JOIN stop_usage su ON rs.stop_id = su.stop_id
        AND su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-30'
    GROUP BY br.route_id, br.route_number, br.route_type
),
route_active_stops AS (
    SELECT 
        br.route_id,
        COUNT(DISTINCT rs.stop_id) as active_stops_count
    FROM bus_routes br
    JOIN route_stops rs ON br.route_id = rs.route_id
    JOIN stop_usage su ON rs.stop_id = su.stop_id
        AND su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-30'
        AND su.boarding_count > 0
    GROUP BY br.route_id
),
performance_stats AS (
    SELECT 
        rp.*,
        COALESCE(ras.active_stops_count, 0) as active_stops_count,
        CASE 
            WHEN rp.stops_count > 0 THEN (COALESCE(ras.active_stops_count, 0)::float / rp.stops_count * 100)::numeric(5,2)
            ELSE 0
        END as stop_utilization_rate,
        CASE 
            WHEN rp.service_days > 0 THEN (rp.total_boarding::float / rp.service_days)::numeric(10,2)
            ELSE 0
        END as daily_avg_boarding
    FROM route_performance rp
    LEFT JOIN route_active_stops ras ON rp.route_id = ras.route_id
)
SELECT 
    route_number,
    route_type,
    stops_count,
    active_stops_count,
    stop_utilization_rate as stop_utilization_pct,
    total_boarding,
    daily_avg_boarding,
    service_days,
    avg_boarding_per_active_event::numeric(5,2) as avg_boarding_per_event,
    CASE 
        WHEN stop_utilization_rate >= 80 AND daily_avg_boarding >= 50 THEN 'HIGH_EFFICIENCY'
        WHEN stop_utilization_rate >= 60 AND daily_avg_boarding >= 20 THEN 'MEDIUM_EFFICIENCY'
        WHEN stop_utilization_rate >= 40 OR daily_avg_boarding >= 10 THEN 'LOW_EFFICIENCY'
        ELSE 'POOR_EFFICIENCY'
    END as efficiency_grade
FROM performance_stats
WHERE total_boarding > 0
ORDER BY total_boarding DESC
LIMIT 15;

/*
노선별 운영 효율성 분석 결과 (2024년 11월 기준):

HIGH_EFFICIENCY 노선 (8개):
- 15-3: 정류장 활용률 91.94%, 일평균 2,400명 (최고 효율)
- 15-1, 15-2: 80% 이상 활용률, 일평균 2,200명 이상
- 41, 60, 15, 60-10, 10-4: 90% 이상 정류장 활용률

MEDIUM_EFFICIENCY 노선 (3개):
- 15-5, 15-4: 농어촌 일반버스, 높은 승차량이지만 상대적으로 낮은 활용률
- 7000: 직행좌석버스, 73.74% 활용률

LOW_EFFICIENCY 노선 (4개):
- 1330-3, 1330-44, 1330-4: 직행/좌석버스, 낮은 정류장 활용률 (33-40%)
- 특징: 정류장 수는 많지만 실제 이용되는 정류장 비율 낮음

운영 시사점:
1. 농어촌 일반버스가 효율성 면에서 우수한 성과
2. 직행/좌석버스는 정류장 활용률 개선 필요
3. LOW_EFFICIENCY 노선의 미이용 정류장은 DRT 서비스 검토 대상
*/


-- ===================================================================================
-- PART B: DRT 확률 데이터 별도 분석 (보조 참고용)
-- ===================================================================================

/*
목적: MST-GCN 모델이 예측한 DRT 확률 데이터의 분포와 특성 파악
근거: 실제 데이터와 분리하여 독립적으로 분석, 보조 참고자료로 활용
주의사항: 이 데이터는 모델 예측값으로 실제 운영 데이터와 직접 비교 금지
*/

-- B1. DRT 확률 데이터 기본 현황
SELECT 
    'drt_features_mstgcn' as table_name,
    COUNT(*) as total_predictions,
    MIN(recorded_at::date) as earliest_prediction_date,
    MAX(recorded_at::date) as latest_prediction_date,
    COUNT(DISTINCT stop_id) as unique_stops_predicted,
    COUNT(DISTINCT recorded_at::date) as prediction_days,
    AVG(drt_probability)::numeric(5,4) as overall_avg_probability,
    MIN(drt_probability) as min_probability,
    MAX(drt_probability) as max_probability,
    COUNT(CASE WHEN drt_probability > 0.7 THEN 1 END) as high_probability_predictions,
    COUNT(CASE WHEN drt_probability BETWEEN 0.4 AND 0.7 THEN 1 END) as medium_probability_predictions,
    COUNT(CASE WHEN drt_probability < 0.4 THEN 1 END) as low_probability_predictions
FROM drt_features_mstgcn;

/*
DRT 확률 데이터 현황 (MST-GCN 모델 예측):
- 총 4,684,153개 예측값 (2024-11-01 ~ 2025-06-25, 237일)
- 957개 정류장에 대한 예측
- 전체 평균 확률: 0.8197 (상당히 높은 수준)
- 확률 분포: 고확률(70%+) 3,740,822개, 중확률(40-70%) 943,297개, 저확률(40%미만) 34개
- 특징: 대부분의 예측이 높은 DRT 확률을 보임 (모델 특성 반영)

*** 중요 해석 지침 ***
이 데이터는 MST-GCN 모델의 예측값으로, 다음과 같이 해석해야 함:
1. 실제 DRT 수요가 아닌 모델이 계산한 잠재적 적합성 지수
2. 높은 평균 확률(0.82)은 가평군 전체가 DRT 도입에 적합한 환경임을 시사
3. 실제 운영 계획 수립 시에는 실제 교통 데이터(PART A)를 우선 고려
4. 이 예측 데이터는 실제 분석을 보완하는 참고자료로만 활용
*/


-- ===================================================================================
-- 종합 분석 결과 및 DRT 운영 권장사항
-- ===================================================================================

/*
===================================================================================
실제 교통 데이터 기반 주요 발견사항:

1. 시간대별 DRT 도입 필요성:
   ✓ 주간 오프피크(10-16시): 지속적 수요 존재, DRT 보완 서비스 적합
   ✓ 심야 시간대(0-6시): 기존 서비스 부족, DRT 도입 검토 가능
   ✓ 피크 시간대(7-9, 17-19시): 기존 버스로 충분, DRT는 연결 역할

2. 지역별 DRT 도입 우선순위:
   *** 최우선 *** 상면: 완전한 교통 사각지대 (124개 정류장 모두 미이용)
   ✓ 청평면: 정류장 활용률 47.9%, 관광 수요 고려한 계절적 운영
   ✓ 가평읍: 중심지역 대비 낮은 이용률, 마지막 마일 연결 서비스
   ✓ 북면/조종면: 기존 서비스 양호, DRT는 보완적 역할

3. 노선별 DRT 연계 전략:
   ✓ 고효율 노선(15-3, 41, 60 등): DRT와 연계한 환승 허브 구축
   ✓ 저효율 노선(1330 시리즈): 미이용 정류장 DRT 전환 검토
   ✓ 직행/좌석버스: 정류장 활용률 개선을 위한 DRT 피더 서비스

4. 운영 모델 제안:
   Phase 1 (긴급): 상면 지역 기본 DRT 서비스 도입
   Phase 2 (단기): 청평면, 가평읍 계절적/보완적 DRT 운영
   Phase 3 (중기): 전 지역 통합 DRT 네트워크 구축

5. 예상 효과:
   - 상면 지역 교통 접근성 100% 개선 (현재 0% → 목표 80%)
   - 전체 대중교통 사각지대 해소: 257개 미이용 정류장 커버
   - 기존 버스 노선과의 시너지를 통한 전체 이용률 향상
===================================================================================

*** DRT 확률 데이터 활용 방안 ***
MST-GCN 예측 데이터(평균 확률 0.82)는 다음과 같이 활용:
- 실제 데이터 분석을 보완하는 참고자료
- DRT 도입 후 수요 예측 모델링의 기초 데이터
- 서비스 권역 세분화 및 운영 시간 최적화 지원
- 정책 결정자를 위한 정량적 근거 자료

*** 최종 권고사항 ***
1. 실제 교통 현황(PART A)을 기반으로 한 정책 결정
2. DRT 확률 데이터(PART B)는 보조 참고자료로 활용
3. 상면 지역 우선 DRT 도입을 통한 교통 사각지대 해소
4. 단계적 확산을 통한 가평군 전체 교통 네트워크 완성
===================================================================================
*/