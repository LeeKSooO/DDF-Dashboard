-- ===============================================
-- PostgreSQL 초기화 시 집계 테이블 생성
-- - Materialized Views (API 성능 최적화용)
-- - DRT Score 집계 테이블 (출퇴근형/관광특화형/교통취약지형)
-- 실행 순서: 기본 테이블 생성 후 실행됨
-- ===============================================

-- 1. 기본 Materialized Views 생성
\echo 'Creating basic materialized views...'
\i /docker-entrypoint-initdb.d/migrations/001_materialized_views.sql

-- 2. Anomaly Pattern 전용 MV 생성
\echo 'Creating anomaly pattern materialized views...'
\i /docker-entrypoint-initdb.d/migrations/002_station_hourly_patterns.sql

-- 3. DRT Score 집계 테이블 생성
\echo 'Creating DRT score aggregation tables...'
\i /docker-entrypoint-initdb.d/migrations/003_commuter_drt_aggregation.sql
\i /docker-entrypoint-initdb.d/migrations/004_tourism_drt_aggregation.sql
\i /docker-entrypoint-initdb.d/migrations/005_vulnerable_drt_aggregation.sql

\echo 'All materialized views and DRT aggregation tables created successfully!'