-- ===============================================
-- 특정 정류장의 특정 기간/시간 DRT 확률 조회
-- ===============================================

-- 1. 특정 정류장의 특정 기간 전체 DRT 확률 조회
-- 사용법: stop_id, 시작날짜, 종료날짜 수정 후 실행
SELECT 
    stop_id,
    recorded_at::date as date,
    hour_of_day,
    CASE day_of_week 
        WHEN 0 THEN '월요일'
        WHEN 1 THEN '화요일'
        WHEN 2 THEN '수요일'
        WHEN 3 THEN '목요일'
        WHEN 4 THEN '금요일'
        WHEN 5 THEN '토요일'
        WHEN 6 THEN '일요일'
    END as day_name,
    boarding_count,
    alighting_count,
    is_operational,
    applicable_interval,
    drt_prob,
    CASE 
        WHEN boarding_count > 0 THEN 'Normal'
        WHEN boarding_count = 0 AND is_operational = true THEN 'Zero Boarding'
        ELSE 'Non-operational'
    END as feature_type
FROM drt_features
WHERE stop_id = 'STOP_44001'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
ORDER BY recorded_at;

-- 2. 특정 정류장의 특정 시간대 DRT 확률 조회
-- 사용법: stop_id, 시작날짜, 종료날짜, 시간 수정 후 실행
SELECT 
    stop_id,
    recorded_at::date as date,
    hour_of_day,
    CASE day_of_week 
        WHEN 0 THEN '월요일'
        WHEN 1 THEN '화요일'
        WHEN 2 THEN '수요일'
        WHEN 3 THEN '목요일'
        WHEN 4 THEN '금요일'
        WHEN 5 THEN '토요일'
        WHEN 6 THEN '일요일'
    END as day_name,
    boarding_count,
    drt_prob,
    applicable_interval,
    is_operational
FROM drt_features
WHERE stop_id = 'STOP_44613'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
  AND hour_of_day IN (7, 8, 9, 17, 18, 19)  -- 원하는 시간대 수정 (출퇴근 시간 예시)
ORDER BY recorded_at;

-- 3. 특정 정류장의 시간대별 DRT 확률 통계 (기간 내)
SELECT 
    stop_id,
    hour_of_day,
    COUNT(*) as total_records,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    MIN(drt_prob) as min_drt_prob,
    MAX(drt_prob) as max_drt_prob,
    STDDEV(drt_prob) as stddev_drt_prob,
    COUNT(CASE WHEN boarding_count = 0 THEN 1 END) as zero_boarding_count,
    COUNT(CASE WHEN is_operational = false THEN 1 END) as non_operational_count
FROM drt_features
WHERE stop_id = 'STOP_44613'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
GROUP BY stop_id, hour_of_day
ORDER BY hour_of_day;

-- 4. 특정 정류장의 요일별 DRT 확률 패턴 (특정 시간대)
SELECT 
    stop_id,
    day_of_week,
    CASE day_of_week 
        WHEN 0 THEN '월요일'
        WHEN 1 THEN '화요일'
        WHEN 2 THEN '수요일'
        WHEN 3 THEN '목요일'
        WHEN 4 THEN '금요일'
        WHEN 5 THEN '토요일'
        WHEN 6 THEN '일요일'
    END as day_name,
    COUNT(*) as total_records,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    AVG(applicable_interval) as avg_interval
FROM drt_features
WHERE stop_id = 'STOP_44613'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
  AND hour_of_day IN (8, 9, 17, 18)  -- 원하는 시간대 수정
GROUP BY stop_id, day_of_week
ORDER BY day_of_week;

-- 5. 특정 정류장의 높은 DRT 확률 케이스 (기간 내)
SELECT 
    stop_id,
    recorded_at,
    hour_of_day,
    CASE day_of_week 
        WHEN 0 THEN '월요일'
        WHEN 1 THEN '화요일'
        WHEN 2 THEN '수요일'
        WHEN 3 THEN '목요일'
        WHEN 4 THEN '금요일'
        WHEN 5 THEN '토요일'
        WHEN 6 THEN '일요일'
    END as day_name,
    boarding_count,
    applicable_interval,
    drt_prob,
    CASE 
        WHEN boarding_count > 0 THEN 'Normal Calculation'
        WHEN boarding_count = 0 AND is_operational = true THEN 'Zero Boarding'
        ELSE 'Non-operational'
    END as feature_type
FROM drt_features
WHERE stop_id = 'STOP_44613'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
  AND drt_prob > 5  -- DRT 확률 임계값 수정
ORDER BY drt_prob DESC;

-- 6. 사용 가능한 정류장 목록 조회 (참고용)
SELECT 
    stop_id,
    COUNT(*) as total_records,
    MIN(recorded_at::date) as first_date,
    MAX(recorded_at::date) as last_date,
    AVG(drt_prob) as avg_drt_prob
FROM drt_features
GROUP BY stop_id
ORDER BY total_records DESC
LIMIT 20;

-- 7. 특정 정류장의 일별 DRT 확률 트렌드
SELECT 
    stop_id,
    recorded_at::date as date,
    COUNT(*) as hourly_records,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    MAX(drt_prob) as max_drt_prob,
    COUNT(CASE WHEN boarding_count > 0 THEN 1 END) as positive_boarding_hours,
    COUNT(CASE WHEN boarding_count = 0 AND is_operational = true THEN 1 END) as zero_boarding_hours,
    COUNT(CASE WHEN is_operational = false THEN 1 END) as non_operational_hours
FROM drt_features
WHERE stop_id = 'STOP_44001'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
GROUP BY stop_id, recorded_at::date
ORDER BY recorded_at::date;

-- 8. 특정 정류장의 시간대별 승차 패턴과 DRT 확률 상관관계
SELECT 
    stop_id,
    hour_of_day,
    boarding_count,
    COUNT(*) as frequency,
    AVG(drt_prob) as avg_drt_prob,
    AVG(applicable_interval) as avg_interval
FROM drt_features
WHERE stop_id = 'STOP_44001'  -- 정류장 ID 수정
  AND recorded_at >= '2025-06-13'  -- 시작 날짜 수정
  AND recorded_at <= '2025-06-25'  -- 종료 날짜 수정
GROUP BY stop_id, hour_of_day, boarding_count
HAVING COUNT(*) > 1  -- 2회 이상 발생한 패턴만
ORDER BY hour_of_day, boarding_count;