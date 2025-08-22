-- ===============================================
-- database/init/04-system-schema.sql (시스템 관리용)
-- ===============================================

-- 시스템 로그 테이블
CREATE TABLE system_logs (
    log_id SERIAL PRIMARY KEY,
    log_level VARCHAR(20),
    service_name VARCHAR(50),
    message TEXT,
    log_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 로그 인덱스
CREATE INDEX idx_system_logs_created ON system_logs (created_at DESC);

-- 사용자 세션 및 활동 추적
CREATE TABLE user_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_ip VARCHAR(45),
    user_agent TEXT,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    actions_count INTEGER DEFAULT 0,
    predictions_requested INTEGER DEFAULT 0
);