-- ==============================================
-- 위도/경도 기반 GIS 쿼리 모음
-- ==============================================

-- ============ 1. 기본 위치 데이터 확인 ============

-- 정류장 위치 데이터 현황
SELECT 
    COUNT(*) as total_stops,
    COUNT(latitude) as stops_with_coords,
    COUNT(*) - COUNT(latitude) as stops_without_coords,
    MIN(latitude) as min_lat, MAX(latitude) as max_lat,
    MIN(longitude) as min_lng, MAX(longitude) as max_lng
FROM bus_stops;

-- 좌표가 있는 정류장들 (샘플)
SELECT 
    stop_name,
    stop_number,
    latitude,
    longitude,
    CASE 
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL 
        THEN 'Has Coordinates' 
        ELSE 'No Coordinates' 
    END as coord_status
FROM bus_stops 
WHERE latitude IS NOT NULL AND longitude IS NOT NULL
ORDER BY stop_name
LIMIT 10;

-- ============ 2. 노선별 정류장 위치 정보 ============

-- 특정 노선의 정류장 위치 정보 (순서대로)
SELECT 
    br.route_number,
    rs.stop_sequence,
    s.stop_name,
    s.stop_number,
    s.latitude,
    s.longitude,
    s.district
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops s ON rs.stop_id = s.stop_id
WHERE br.route_number = '30-5'  -- 노선번호 변경 가능
  AND s.latitude IS NOT NULL 
  AND s.longitude IS NOT NULL
ORDER BY rs.stop_sequence;

-- 모든 노선의 위치 정보가 있는 정류장 수
SELECT 
    br.route_number,
    br.start_point,
    br.end_point,
    COUNT(*) as total_stops,
    COUNT(s.latitude) as stops_with_coords,
    ROUND(COUNT(s.latitude) * 100.0 / COUNT(*), 2) as coord_coverage_percent
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops s ON rs.stop_id = s.stop_id
GROUP BY br.route_number, br.start_point, br.end_point
ORDER BY coord_coverage_percent DESC;

-- ============ 3. 거리 기반 쿼리 (PostGIS 함수 사용) ============

-- 특정 지점에서 가장 가까운 정류장들 (1km 이내)
-- 예: 가평터미널 근처 정류장들
WITH reference_point AS (
    SELECT latitude, longitude 
    FROM bus_stops 
    WHERE stop_name = '가평터미널'  -- 기준점 변경 가능
    LIMIT 1
)
SELECT 
    s.stop_name,
    s.stop_number,
    s.latitude,
    s.longitude,
    ROUND(
        ST_Distance(
            ST_GeomFromText('POINT(' || rp.longitude || ' ' || rp.latitude || ')', 4326),
            ST_GeomFromText('POINT(' || s.longitude || ' ' || s.latitude || ')', 4326)
        ) * 111139  -- 도 단위를 미터로 변환 (근사값)
    ) as distance_meters
FROM bus_stops s, reference_point rp
WHERE s.latitude IS NOT NULL 
  AND s.longitude IS NOT NULL
  AND s.stop_name != '가평터미널'  -- 자기 자신 제외
ORDER BY distance_meters
LIMIT 10;

-- 두 정류장 간 직선거리 계산
SELECT 
    s1.stop_name as stop1,
    s2.stop_name as stop2,
    s1.latitude as lat1, s1.longitude as lng1,
    s2.latitude as lat2, s2.longitude as lng2,
    ROUND(
        ST_Distance(
            ST_GeomFromText('POINT(' || s1.longitude || ' ' || s1.latitude || ')', 4326),
            ST_GeomFromText('POINT(' || s2.longitude || ' ' || s2.latitude || ')', 4326)
        ) * 111139  -- 미터 단위
    ) as distance_meters
FROM bus_stops s1, bus_stops s2
WHERE s1.stop_name = '가평터미널'  -- 첫 번째 정류장 변경 가능
  AND s2.stop_name = '청평터미널'  -- 두 번째 정류장 변경 가능
  AND s1.latitude IS NOT NULL AND s1.longitude IS NOT NULL
  AND s2.latitude IS NOT NULL AND s2.longitude IS NOT NULL;

-- ============ 4. 노선 경로 분석 ============

-- 특정 노선의 경로 길이 및 방향 분석
SELECT 
    br.route_number,
    COUNT(*) as total_stops,
    MIN(s.latitude) as min_lat, MAX(s.latitude) as max_lat,
    MIN(s.longitude) as min_lng, MAX(s.longitude) as max_lng,
    ROUND(MAX(s.latitude) - MIN(s.latitude), 6) as lat_span,
    ROUND(MAX(s.longitude) - MIN(s.longitude), 6) as lng_span,
    CASE 
        WHEN (MAX(s.latitude) - MIN(s.latitude)) > (MAX(s.longitude) - MIN(s.longitude))
        THEN '남북 방향'
        ELSE '동서 방향'
    END as route_direction
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops s ON rs.stop_id = s.stop_id
WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
GROUP BY br.route_number
ORDER BY br.route_number;

-- 노선별 시작점과 종점의 직선거리
SELECT 
    br.route_number,
    br.start_point,
    br.end_point,
    start_stop.latitude as start_lat,
    start_stop.longitude as start_lng,
    end_stop.latitude as end_lat,
    end_stop.longitude as end_lng,
    ROUND(
        ST_Distance(
            ST_GeomFromText('POINT(' || start_stop.longitude || ' ' || start_stop.latitude || ')', 4326),
            ST_GeomFromText('POINT(' || end_stop.longitude || ' ' || end_stop.latitude || ')', 4326)
        ) * 111139
    ) as straight_distance_meters
FROM bus_routes br
JOIN route_stops rs1 ON br.route_id = rs1.route_id
JOIN bus_stops start_stop ON rs1.stop_id = start_stop.stop_id
JOIN route_stops rs2 ON br.route_id = rs2.route_id  
JOIN bus_stops end_stop ON rs2.stop_id = end_stop.stop_id
WHERE rs1.stop_sequence = (
    SELECT MIN(stop_sequence) FROM route_stops WHERE route_id = br.route_id
)
AND rs2.stop_sequence = (
    SELECT MAX(stop_sequence) FROM route_stops WHERE route_id = br.route_id
)
AND start_stop.latitude IS NOT NULL AND end_stop.latitude IS NOT NULL
ORDER BY straight_distance_meters DESC;

-- ============ 5. 지역별 정류장 분포 ============

-- 위도/경도 기준 지역별 정류장 분포
SELECT 
    CASE 
        WHEN latitude >= 37.8 THEN '북부'
        WHEN latitude >= 37.7 THEN '중부'
        ELSE '남부'
    END as latitude_zone,
    CASE 
        WHEN longitude >= 127.5 THEN '동부'
        ELSE '서부'
    END as longitude_zone,
    COUNT(*) as stop_count,
    ROUND(AVG(latitude), 6) as avg_latitude,
    ROUND(AVG(longitude), 6) as avg_longitude
FROM bus_stops
WHERE latitude IS NOT NULL AND longitude IS NOT NULL
GROUP BY 
    CASE 
        WHEN latitude >= 37.8 THEN '북부'
        WHEN latitude >= 37.7 THEN '중부'
        ELSE '남부'
    END,
    CASE 
        WHEN longitude >= 127.5 THEN '동부'
        ELSE '서부'
    END
ORDER BY latitude_zone, longitude_zone;

-- 구역별 정류장 밀도 (1km² 당 정류장 수 추정)
WITH bounds AS (
    SELECT 
        MIN(latitude) as min_lat, MAX(latitude) as max_lat,
        MIN(longitude) as min_lng, MAX(longitude) as max_lng,
        COUNT(*) as total_stops
    FROM bus_stops 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
)
SELECT 
    total_stops,
    ROUND(max_lat - min_lat, 6) as lat_range,
    ROUND(max_lng - min_lng, 6) as lng_range,
    ROUND((max_lat - min_lat) * (max_lng - min_lng) * 111139 * 111139 / 1000000, 2) as approx_area_km2,
    ROUND(total_stops / ((max_lat - min_lat) * (max_lng - min_lng) * 111139 * 111139 / 1000000), 2) as stops_per_km2
FROM bounds;

-- ============ 6. 정류장 이용량과 위치 결합 분석 ============

-- 위치별 정류장 이용량 TOP 10
SELECT 
    s.stop_name,
    s.stop_number,
    s.latitude,
    s.longitude,
    s.district,
    SUM(su.boarding_count + su.alighting_count) as total_passengers,
    CASE 
        WHEN s.latitude >= 37.8 THEN '북부'
        WHEN s.latitude >= 37.7 THEN '중부'
        ELSE '남부'
    END as location_zone
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
  AND s.latitude IS NOT NULL
GROUP BY s.stop_id, s.stop_name, s.stop_number, s.latitude, s.longitude, s.district
ORDER BY total_passengers DESC
LIMIT 10;

-- 지역별 평균 이용량
SELECT 
    CASE 
        WHEN s.latitude >= 37.8 THEN '북부'
        WHEN s.latitude >= 37.7 THEN '중부'
        ELSE '남부'
    END as latitude_zone,
    COUNT(DISTINCT s.stop_id) as stop_count,
    SUM(su.boarding_count + su.alighting_count) as total_passengers,
    ROUND(AVG(su.boarding_count + su.alighting_count), 2) as avg_passengers_per_hour,
    ROUND(SUM(su.boarding_count + su.alighting_count) / COUNT(DISTINCT s.stop_id), 2) as avg_passengers_per_stop
FROM stop_usage su
JOIN bus_stops s ON su.stop_id = s.stop_id
WHERE su.recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
  AND su.is_operational = true
  AND s.latitude IS NOT NULL
GROUP BY 
    CASE 
        WHEN s.latitude >= 37.8 THEN '북부'
        WHEN s.latitude >= 37.7 THEN '중부'
        ELSE '남부'
    END
ORDER BY avg_passengers_per_stop DESC;

-- ============ 7. 노선 경로 시각화용 데이터 ============

-- 특정 노선의 경로 좌표 (GIS 시각화용)
SELECT 
    br.route_number,
    rs.stop_sequence,
    s.stop_name,
    s.latitude,
    s.longitude,
    CONCAT(s.longitude, ',', s.latitude) as lng_lat_pair,
    LAG(s.latitude) OVER (ORDER BY rs.stop_sequence) as prev_lat,
    LAG(s.longitude) OVER (ORDER BY rs.stop_sequence) as prev_lng
FROM bus_routes br
JOIN route_stops rs ON br.route_id = rs.route_id
JOIN bus_stops s ON rs.stop_id = s.stop_id
WHERE br.route_number = '1'  -- 노선번호 변경 가능
  AND s.latitude IS NOT NULL 
  AND s.longitude IS NOT NULL
ORDER BY rs.stop_sequence;

-- 모든 정류장 좌표 (지도 표시용)
SELECT 
    s.stop_name,
    s.stop_number,
    s.latitude,
    s.longitude,
    s.district,
    COALESCE(passenger_data.total_passengers, 0) as total_passengers,
    CASE 
        WHEN COALESCE(passenger_data.total_passengers, 0) >= 10000 THEN 'High'
        WHEN COALESCE(passenger_data.total_passengers, 0) >= 1000 THEN 'Medium'
        ELSE 'Low'
    END as usage_level
FROM bus_stops s
LEFT JOIN (
    SELECT 
        stop_id,
        SUM(boarding_count + alighting_count) as total_passengers
    FROM stop_usage
    WHERE recorded_at::date BETWEEN '2024-11-01' AND '2024-11-14'  -- 기간 변경 가능
      AND is_operational = true
    GROUP BY stop_id
) passenger_data ON s.stop_id = passenger_data.stop_id
WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
ORDER BY s.stop_name;

-- ============ 8. 클러스터링 분석 ============

-- 정류장 클러스터링 (위도/경도 기준)
SELECT 
    ROUND(latitude, 2) as lat_cluster,
    ROUND(longitude, 2) as lng_cluster,
    COUNT(*) as stops_in_cluster,
    STRING_AGG(stop_name, ', ') as stops_list
FROM bus_stops
WHERE latitude IS NOT NULL AND longitude IS NOT NULL
GROUP BY ROUND(latitude, 2), ROUND(longitude, 2)
HAVING COUNT(*) > 1  -- 2개 이상 정류장이 있는 클러스터만
ORDER BY stops_in_cluster DESC;

-- ============ 9. 경계선 및 범위 분석 ============

-- 가평군 버스 서비스 커버리지 영역
SELECT 
    'Service Area' as description,
    MIN(latitude) as south_boundary,
    MAX(latitude) as north_boundary,
    MIN(longitude) as west_boundary,
    MAX(longitude) as east_boundary,
    ROUND(MAX(latitude) - MIN(latitude), 6) as latitude_span,
    ROUND(MAX(longitude) - MIN(longitude), 6) as longitude_span
FROM bus_stops
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- 중심점 계산
SELECT 
    'Service Center' as description,
    ROUND(AVG(latitude), 6) as center_latitude,
    ROUND(AVG(longitude), 6) as center_longitude,
    COUNT(*) as total_stops_with_coords
FROM bus_stops
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;