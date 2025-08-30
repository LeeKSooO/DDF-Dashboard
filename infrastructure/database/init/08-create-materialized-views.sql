-- ===============================================
-- PostgreSQL 초기화 시 Materialized Views 생성
-- 실행 순서: 기본 테이블 생성 후 실행됨
-- ===============================================

-- 1. 기본 Materialized Views 생성
\echo 'Creating basic materialized views...'
\i /docker-entrypoint-initdb.d/migrations/create_materialized_views.sql

-- 2. Anomaly Pattern 전용 MV 생성
\echo 'Creating anomaly pattern materialized views...'
\i /docker-entrypoint-initdb.d/migrations/create_station_hourly_patterns.sql

\echo 'All materialized views created successfully!'