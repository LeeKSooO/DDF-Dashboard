-- ==============================================
-- PostgreSQL 데이터 검증 쿼리 모음
-- ==============================================

-- ============ 1. 기본 데이터 현황 확인 ============

-- 전체 테이블 레코드 수
SELECT 
    'bus_routes' as table_name, COUNT(*) as record_count FROM bus_routes
UNION ALL
SELECT 
    'bus_stops' as table_name, COUNT(*) as record_count FROM bus_stops
UNION ALL
SELECT 
    'route_stops' as table_name, COUNT(*) as record_count FROM route_stops
UNION ALL
SELECT 
    'stop_usage' as table_name, COUNT(*) as record_count FROM stop_usage;

-- 수집 기간 확인
SELECT 
    MIN(recorded_at::date) as start_date,
    MAX(recorded_at::date) as end_date,
    COUNT(DISTINCT recorded_at::date) as total_days
FROM stop_usage;

-- 운행/미운행 데이터 분포
SELECT 
    is_operational,
    COUNT(*) as record_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM stop_usage 
GROUP BY is_operational;

-- ============ 2. 특정 정류장의 특정일 승하차 데이터 ============

-- 특정 정류장의 특정일 24시간 승하차 데이터
SELECT 
    s.stop_name,
    s.stop_number,
    su.recorded_at,
    EXTRACT(hour FROM su.recorded_at) as hour,
    su.boarding_count,
    su.alighting_count,
    su.boarding_count + su.alighting_count as total_passengers,
    su.is_operational,
    su.is_weekend
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE s.stop_name = '가평터미널'  -- 정류장명 변경 가능
  AND su.recorded_at::date = '2024-11-15'  -- 날짜 변경 가능
ORDER BY su.recorded_at;

-- 특정 정류장번호로 조회
SELECT 
    s.stop_name,
    s.stop_number,
    su.recorded_at,
    EXTRACT(hour FROM su.recorded_at) as hour,
    su.boarding_count,
    su.alighting_count,
    su.is_operational
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE s.stop_number = '44001'  -- 정류장번호 변경 가능
  AND su.recorded_at::date = '2024-11-15'  -- 날짜 변경 가능
ORDER BY su.recorded_at;

-- ============ 3. 기간별 승하차 인원 및 운행 현황 ============

-- 기간별 일일 승하차 통계
SELECT 
    su.recorded_at::date as date,
    COUNT(DISTINCT su.stop_id) as active_stops,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting,
    SUM(su.boarding_count + su.alighting_count) as total_passengers,
    COUNT(CASE WHEN su.is_operational = true THEN 1 END) as operational_records,
    COUNT(CASE WHEN su.is_operational = false THEN 1 END) as non_operational_records
FROM stop_usage su
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
GROUP BY su.recorded_at::date
ORDER BY su.recorded_at::date;

-- 기간별 시간대별 승하차 패턴
SELECT 
    EXTRACT(hour FROM su.recorded_at) as hour,
    AVG(su.boarding_count) as avg_boarding,
    AVG(su.alighting_count) as avg_alighting,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting
FROM stop_usage su
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY EXTRACT(hour FROM su.recorded_at)
ORDER BY hour;

-- ============ 4. 가장 바쁜 정류장 순위 ============

-- 기간별 승차 인원이 가장 많은 정류장 TOP 10
SELECT 
    s.stop_name,
    s.stop_number,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting,
    SUM(su.boarding_count + su.alighting_count) as total_passengers,
    COUNT(CASE WHEN su.is_operational = true THEN 1 END) as operational_hours,
    ROUND(AVG(su.boarding_count + su.alighting_count), 2) as avg_passengers_per_hour
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY s.stop_id, s.stop_name, s.stop_number
ORDER BY total_boarding DESC
LIMIT 10;

-- 시간대별 가장 바쁜 정류장 (예: 출근시간 07-09시)
SELECT 
    s.stop_name,
    s.stop_number,
    EXTRACT(hour FROM su.recorded_at) as hour,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE EXTRACT(hour FROM su.recorded_at) BETWEEN 7 AND 9  -- 시간대 변경 가능
  AND su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY s.stop_id, s.stop_name, s.stop_number, EXTRACT(hour FROM su.recorded_at)
ORDER BY total_boarding DESC
LIMIT 10;

-- ============ 5. 노선별 분석 (노선-정류장 조인) ============

-- 노선별 총 승하차 인원
SELECT 
    br.route_number,
    br.route_type,
    br.start_point,
    br.end_point,
    COUNT(DISTINCT rs.stop_id) as total_stops,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting,
    ROUND(AVG(su.boarding_count + su.alighting_count), 2) as avg_passengers_per_hour
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN stop_usage su ON rs.stop_id = su.stop_id
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY br.route_id, br.route_number, br.route_type, br.start_point, br.end_point
ORDER BY total_boarding DESC;

-- 특정 노선의 정류장별 이용량
SELECT 
    br.route_number,
    rs.stop_sequence,
    s.stop_name,
    s.stop_number,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting,
    SUM(su.boarding_count + su.alighting_count) as total_passengers
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops s ON rs.stop_id = s.stop_id
JOIN stop_usage su ON s.stop_id = su.stop_id
WHERE br.route_number = '1'  -- 노선번호 변경 가능
  AND su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY br.route_number, rs.stop_sequence, s.stop_name, s.stop_number
ORDER BY rs.stop_sequence;

-- ============ 6. 요일별/주말 분석 ============

-- 요일별 승하차 패턴
SELECT 
    CASE EXTRACT(dow FROM su.recorded_at)
        WHEN 0 THEN '일요일'
        WHEN 1 THEN '월요일'
        WHEN 2 THEN '화요일'
        WHEN 3 THEN '수요일'
        WHEN 4 THEN '목요일'
        WHEN 5 THEN '금요일'
        WHEN 6 THEN '토요일'
    END as day_of_week,
    su.is_weekend,
    COUNT(*) as total_records,
    SUM(su.boarding_count) as total_boarding,
    SUM(su.alighting_count) as total_alighting,
    ROUND(AVG(su.boarding_count + su.alighting_count), 2) as avg_passengers
FROM stop_usage su
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
GROUP BY EXTRACT(dow FROM su.recorded_at), su.is_weekend
ORDER BY EXTRACT(dow FROM su.recorded_at);

-- ============ 7. 운행 패턴 분석 ============

-- 정류장별 운행률 (운행시간/전체시간)
SELECT 
    s.stop_name,
    s.stop_number,
    COUNT(*) as total_hours,
    COUNT(CASE WHEN su.is_operational = true THEN 1 END) as operational_hours,
    COUNT(CASE WHEN su.is_operational = false THEN 1 END) as non_operational_hours,
    ROUND(
        COUNT(CASE WHEN su.is_operational = true THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as operational_percentage
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
GROUP BY s.stop_id, s.stop_name, s.stop_number
HAVING COUNT(*) > 100  -- 충분한 데이터가 있는 정류장만
ORDER BY operational_percentage DESC;

-- 시간대별 운행률
SELECT 
    EXTRACT(hour FROM su.recorded_at) as hour,
    COUNT(*) as total_records,
    COUNT(CASE WHEN su.is_operational = true THEN 1 END) as operational_records,
    ROUND(
        COUNT(CASE WHEN su.is_operational = true THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as operational_percentage
FROM stop_usage su
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
GROUP BY EXTRACT(hour FROM su.recorded_at)
ORDER BY hour;

-- ============ 8. 데이터 품질 검증 ============

-- 정류장번호가 없는 정류장들 (UNKNOWN_으로 시작)
SELECT 
    s.stop_id,
    s.stop_name,
    s.stop_number,
    COUNT(su.stop_id) as usage_records
FROM bus_stops s
LEFT JOIN stop_usage su ON s.stop_id = su.stop_id
WHERE s.stop_id LIKE 'UNKNOWN_%'
GROUP BY s.stop_id, s.stop_name, s.stop_number
ORDER BY usage_records DESC;

-- 중복 데이터 확인 (있으면 안됨)
SELECT 
    stop_id,
    recorded_at,
    COUNT(*) as duplicate_count
FROM stop_usage
GROUP BY stop_id, recorded_at
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- 이상한 승하차 데이터 확인 (너무 큰 값들)
SELECT 
    s.stop_name,
    su.recorded_at,
    su.boarding_count,
    su.alighting_count,
    su.boarding_count + su.alighting_count as total
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE su.boarding_count > 1000 OR su.alighting_count > 1000  -- 임계값 조정 가능
ORDER BY (su.boarding_count + su.alighting_count) DESC;

-- ============ 9. 종합 대시보드 쿼리 ============

-- 전체 시스템 요약
SELECT 
    '총 노선 수' as metric, COUNT(*)::text as value FROM bus_routes
UNION ALL
SELECT 
    '총 정류장 수' as metric, COUNT(*)::text as value FROM bus_stops
UNION ALL
SELECT 
    '총 승하차 레코드' as metric, COUNT(*)::text as value FROM stop_usage
UNION ALL
SELECT 
    '수집 기간' as metric, 
    MIN(recorded_at::date)::text || ' ~ ' || MAX(recorded_at::date)::text as value 
FROM stop_usage
UNION ALL
SELECT 
    '총 승차 인원' as metric, 
    SUM(boarding_count)::text as value 
FROM stop_usage WHERE is_operational = true
UNION ALL
SELECT 
    '총 하차 인원' as metric, 
    SUM(alighting_count)::text as value 
FROM stop_usage WHERE is_operational = true
UNION ALL
SELECT 
    '일일 평균 승객' as metric, 
    ROUND(SUM(boarding_count + alighting_count) / COUNT(DISTINCT recorded_at::date))::text as value 
FROM stop_usage WHERE is_operational = true;