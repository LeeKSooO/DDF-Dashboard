-- ===============================================
-- DRT Feature 테스트 쿼리 모음
-- ===============================================

-- 1. 기본 통계 조회
SELECT 
    'Total Records' as metric,
    COUNT(*) as value
FROM drt_features
UNION ALL
SELECT 
    'Date Range',
    CONCAT(MIN(recorded_at::date), ' ~ ', MAX(recorded_at::date))
FROM drt_features
UNION ALL
SELECT 
    'Unique Stops',
    COUNT(DISTINCT stop_id)::text
FROM drt_features
UNION ALL
SELECT 
    'Avg DRT Probability',
    ROUND(AVG(drt_prob), 4)::text
FROM drt_features;

-- 2. 운행 상태별 DRT 확률 분포
SELECT 
    is_operational,
    boarding_count,
    COUNT(*) as record_count,
    AVG(drt_prob) as avg_drt_prob,
    MIN(drt_prob) as min_drt_prob,
    MAX(drt_prob) as max_drt_prob,
    STDDEV(drt_prob) as stddev_drt_prob
FROM drt_features
WHERE boarding_count IN (0, 1, 2, 3, 4, 5)
GROUP BY is_operational, boarding_count
ORDER BY is_operational, boarding_count;

-- 3. 배차간격별 DRT 확률 분석
SELECT 
    CASE 
        WHEN applicable_interval <= 30 THEN '30분 이하'
        WHEN applicable_interval <= 60 THEN '30-60분'
        WHEN applicable_interval <= 120 THEN '1-2시간'
        WHEN applicable_interval <= 240 THEN '2-4시간'
        WHEN applicable_interval <= 480 THEN '4-8시간'
        WHEN applicable_interval <= 1440 THEN '8-24시간'
        ELSE '24시간 이상'
    END as interval_range,
    COUNT(*) as record_count,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    AVG(CASE WHEN boarding_count = 0 THEN drt_prob END) as avg_drt_prob_zero_boarding
FROM drt_features
GROUP BY 
    CASE 
        WHEN applicable_interval <= 30 THEN '30분 이하'
        WHEN applicable_interval <= 60 THEN '30-60분'
        WHEN applicable_interval <= 120 THEN '1-2시간'
        WHEN applicable_interval <= 240 THEN '2-4시간'
        WHEN applicable_interval <= 480 THEN '4-8시간'
        WHEN applicable_interval <= 1440 THEN '8-24시간'
        ELSE '24시간 이상'
    END
ORDER BY 
    CASE 
        WHEN applicable_interval <= 30 THEN 1
        WHEN applicable_interval <= 60 THEN 2
        WHEN applicable_interval <= 120 THEN 3
        WHEN applicable_interval <= 240 THEN 4
        WHEN applicable_interval <= 480 THEN 5
        WHEN applicable_interval <= 1440 THEN 6
        ELSE 7
    END;

-- 4. 시간대별 DRT 패턴 분석
SELECT 
    hour_of_day,
    COUNT(*) as total_records,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    COUNT(CASE WHEN is_operational = false THEN 1 END) as non_operational_count,
    COUNT(CASE WHEN boarding_count = 0 AND is_operational = true THEN 1 END) as zero_boarding_count,
    COUNT(CASE WHEN boarding_count > 0 THEN 1 END) as positive_boarding_count
FROM drt_features
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- 5. 요일별 DRT 패턴 분석
SELECT 
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
GROUP BY day_of_week
ORDER BY day_of_week;

-- 6. 배차간격 보정 효과 분석
SELECT 
    'Weekday Corrections' as interval_type,
    COUNT(CASE WHEN original_weekday_interval = 0 THEN 1 END) as zero_count,
    COUNT(CASE WHEN corrected_weekday_interval = 1440 THEN 1 END) as corrected_count,
    ROUND(COUNT(CASE WHEN original_weekday_interval = 0 THEN 1 END) * 100.0 / COUNT(*), 2) as zero_percentage
FROM drt_features
UNION ALL
SELECT 
    'Saturday Corrections',
    COUNT(CASE WHEN original_saturday_interval = 0 THEN 1 END),
    COUNT(CASE WHEN corrected_saturday_interval = 1440 THEN 1 END),
    ROUND(COUNT(CASE WHEN original_saturday_interval = 0 THEN 1 END) * 100.0 / COUNT(*), 2)
FROM drt_features
UNION ALL
SELECT 
    'Sunday Corrections',
    COUNT(CASE WHEN original_sunday_interval = 0 THEN 1 END),
    COUNT(CASE WHEN corrected_sunday_interval = 1440 THEN 1 END),
    ROUND(COUNT(CASE WHEN original_sunday_interval = 0 THEN 1 END) * 100.0 / COUNT(*), 2)
FROM drt_features;

-- 7. 높은 DRT 확률 케이스 분석
SELECT 
    stop_id,
    recorded_at,
    hour_of_day,
    day_of_week,
    boarding_count,
    applicable_interval,
    drt_prob,
    is_operational,
    CASE 
        WHEN boarding_count > 0 THEN 'Normal Calculation'
        WHEN boarding_count = 0 AND is_operational = true THEN 'Zero Boarding'
        ELSE 'Non-operational'
    END as feature_type
FROM drt_features
WHERE drt_prob > 10
ORDER BY drt_prob DESC
LIMIT 20;

-- 8. 정류장별 DRT 확률 순위
SELECT 
    stop_id,
    COUNT(*) as total_records,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob,
    MAX(drt_prob) as max_drt_prob,
    COUNT(CASE WHEN boarding_count = 0 THEN 1 END) as zero_boarding_count,
    ROUND(COUNT(CASE WHEN boarding_count = 0 THEN 1 END) * 100.0 / COUNT(*), 2) as zero_boarding_percentage
FROM drt_features
GROUP BY stop_id
HAVING COUNT(*) > 100  -- 충분한 데이터가 있는 정류장만
ORDER BY avg_drt_prob DESC
LIMIT 15;

-- 9. DRT 확률 분포 히스토그램
SELECT 
    CASE 
        WHEN drt_prob = 0 THEN '0'
        WHEN drt_prob <= 1 THEN '0-1'
        WHEN drt_prob <= 2 THEN '1-2'
        WHEN drt_prob <= 5 THEN '2-5'
        WHEN drt_prob <= 10 THEN '5-10'
        WHEN drt_prob <= 20 THEN '10-20'
        WHEN drt_prob <= 50 THEN '20-50'
        ELSE '50+'
    END as drt_range,
    COUNT(*) as record_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM drt_features), 2) as percentage
FROM drt_features
GROUP BY 
    CASE 
        WHEN drt_prob = 0 THEN '0'
        WHEN drt_prob <= 1 THEN '0-1'
        WHEN drt_prob <= 2 THEN '1-2'
        WHEN drt_prob <= 5 THEN '2-5'
        WHEN drt_prob <= 10 THEN '5-10'
        WHEN drt_prob <= 20 THEN '10-20'
        WHEN drt_prob <= 50 THEN '20-50'
        ELSE '50+'
    END
ORDER BY 
    CASE 
        WHEN drt_prob = 0 THEN 1
        WHEN drt_prob <= 1 THEN 2
        WHEN drt_prob <= 2 THEN 3
        WHEN drt_prob <= 5 THEN 4
        WHEN drt_prob <= 10 THEN 5
        WHEN drt_prob <= 20 THEN 6
        WHEN drt_prob <= 50 THEN 7
        ELSE 8
    END;

-- 10. 특정 조건 조합 테스트
SELECT 
    'Peak Hours (7-9, 17-19)' as condition_name,
    COUNT(*) as record_count,
    AVG(boarding_count) as avg_boarding,
    AVG(drt_prob) as avg_drt_prob
FROM drt_features
WHERE hour_of_day IN (7, 8, 9, 17, 18, 19)
UNION ALL
SELECT 
    'Off-Peak Hours (10-16, 20-23)',
    COUNT(*),
    AVG(boarding_count),
    AVG(drt_prob)
FROM drt_features
WHERE hour_of_day IN (10, 11, 12, 13, 14, 15, 16, 20, 21, 22, 23)
UNION ALL
SELECT 
    'Late Night/Early Morning (0-6)',
    COUNT(*),
    AVG(boarding_count),
    AVG(drt_prob)
FROM drt_features
WHERE hour_of_day IN (0, 1, 2, 3, 4, 5, 6)
UNION ALL
SELECT 
    'Weekend',
    COUNT(*),
    AVG(boarding_count),
    AVG(drt_prob)
FROM drt_features
WHERE is_weekend = true
UNION ALL
SELECT 
    'Weekday',
    COUNT(*),
    AVG(boarding_count),
    AVG(drt_prob)
FROM drt_features
WHERE is_weekend = false;

-- 11. 승차 승객 수별 상세 분석
SELECT 
    boarding_count,
    COUNT(*) as record_count,
    AVG(drt_prob) as avg_drt_prob,
    MIN(drt_prob) as min_drt_prob,
    MAX(drt_prob) as max_drt_prob,
    AVG(applicable_interval) as avg_interval,
    COUNT(CASE WHEN is_operational = false THEN 1 END) as non_operational_count
FROM drt_features
WHERE boarding_count <= 10
GROUP BY boarding_count
ORDER BY boarding_count;

-- 12. 데이터 품질 체크
SELECT 
    'Records with NULL values' as check_name,
    COUNT(*) as count
FROM drt_features
WHERE stop_id IS NULL OR recorded_at IS NULL OR drt_prob IS NULL
UNION ALL
SELECT 
    'Records with negative DRT prob',
    COUNT(*)
FROM drt_features
WHERE drt_prob < 0
UNION ALL
SELECT 
    'Records with extreme DRT prob (>100)',
    COUNT(*)
FROM drt_features
WHERE drt_prob > 100
UNION ALL
SELECT 
    'Duplicates (stop_id, recorded_at)',
    COUNT(*) - COUNT(DISTINCT stop_id, recorded_at)
FROM drt_features;