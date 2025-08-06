from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, JSON, ForeignKey, DECIMAL, UniqueConstraint, Date, Text, TIME
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class BusStop(Base):
    __tablename__ = "bus_stops"
    
    stop_id = Column(String(50), primary_key=True)
    stop_number = Column(String(20))
    stop_name = Column(String(100), nullable=False)
    location = Column(Geography('POINT', srid=4326))
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    district = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BusRoute(Base):
    __tablename__ = "bus_routes"
    
    route_id = Column(String(50), primary_key=True)
    route_number = Column(String(20), nullable=False)
    route_type = Column(String(50))
    start_point = Column(String(100))
    end_point = Column(String(100))
    first_bus_time = Column(TIME)
    last_bus_time = Column(TIME)
    weekday_interval = Column(Integer)
    saturday_interval = Column(Integer)
    sunday_interval = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RouteStop(Base):
    __tablename__ = "route_stops"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String(50), ForeignKey("bus_routes.route_id"))
    stop_id = Column(String(50), ForeignKey("bus_stops.stop_id"))
    stop_sequence = Column(Integer, nullable=False)
    distance_from_prev = Column(DECIMAL(10, 2))
    travel_time_from_prev = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('route_id', 'stop_sequence', name='_route_sequence_uc'),
    )

class POI(Base):
    __tablename__ = "pois"
    
    poi_id = Column(Integer, primary_key=True, autoincrement=True)
    poi_name = Column(String(200), nullable=False)
    poi_type = Column(String(50), nullable=False)
    poi_category = Column(String(50))
    location = Column(Geography('POINT', srid=4326))
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    address = Column(String(500))
    operating_hours = Column(JSONB)
    poi_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StopUsage(Base):
    __tablename__ = "stop_usage"
    
    stop_id = Column(String(50), ForeignKey("bus_stops.stop_id"), primary_key=True)
    recorded_at = Column(DateTime, primary_key=True)
    boarding_count = Column(Integer, default=0)
    alighting_count = Column(Integer, default=0)
    is_operational = Column(Boolean, default=True)
    weather_condition = Column(String(50))
    temperature = Column(DECIMAL(5, 2))
    is_holiday = Column(Boolean, default=False)
    is_weekend = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class DRTFeature(Base):
    __tablename__ = "drt_features"
    
    feature_id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(String(50), ForeignKey("bus_stops.stop_id"))
    route_id = Column(String(50), ForeignKey("bus_routes.route_id"))
    recorded_at = Column(DateTime, nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    is_weekend = Column(Boolean, nullable=False)
    is_holiday = Column(Boolean, default=False)
    
    # 원본 데이터
    boarding_count = Column(Integer, nullable=False)
    alighting_count = Column(Integer, nullable=False)
    is_operational = Column(Boolean, nullable=False)
    
    # 배차간격 정보
    original_weekday_interval = Column(Integer)
    original_saturday_interval = Column(Integer)
    original_sunday_interval = Column(Integer)
    corrected_weekday_interval = Column(Integer, nullable=False)
    corrected_saturday_interval = Column(Integer, nullable=False)
    corrected_sunday_interval = Column(Integer, nullable=False)
    
    # 계산된 Feature
    applicable_interval = Column(Integer, nullable=False)
    drt_prob = Column(DECIMAL(10, 4), nullable=False)
    drt_prob_normalized = Column(DECIMAL(10, 4))
    boarding_count_normalized = Column(DECIMAL(10, 4))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('stop_id', 'recorded_at', name='_stop_time_uc'),
    )

class StopFeature(Base):
    __tablename__ = "stop_features"
    
    stop_id = Column(String(50), ForeignKey("bus_stops.stop_id"), primary_key=True)
    feature_date = Column(Date, primary_key=True)
    
    # 공간적 특징
    nearby_hospital_count = Column(Integer, default=0)
    nearest_hospital_distance = Column(DECIMAL(10, 2))
    nearby_school_count = Column(Integer, default=0)
    nearest_school_distance = Column(DECIMAL(10, 2))
    nearby_market_count = Column(Integer, default=0)
    nearest_market_distance = Column(DECIMAL(10, 2))
    nearby_tourist_count = Column(Integer, default=0)
    nearest_tourist_distance = Column(DECIMAL(10, 2))
    
    # 시간적 특징
    avg_daily_boarding = Column(DECIMAL(10, 2))
    avg_daily_alighting = Column(DECIMAL(10, 2))
    peak_hour_ratio = Column(DECIMAL(5, 4))
    weekend_ratio = Column(DECIMAL(5, 4))
    
    # 네트워크 특징
    connected_routes_count = Column(Integer)
    centrality_score = Column(DECIMAL(5, 4))
    
    # 추가 메타데이터
    features = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    
    model_id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    model_type = Column(String(50), default='ASTGCN')
    
    training_start = Column(DateTime)
    training_end = Column(DateTime)
    training_data_start = Column(DateTime)
    training_data_end = Column(DateTime)
    
    metrics = Column(JSON)
    hyperparameters = Column(JSON)
    model_architecture = Column(JSON)
    normalization_stats = Column(JSON)
    
    model_path = Column(String(500), nullable=False)
    stats_path = Column(String(500))
    graph_path = Column(String(500))
    
    is_active = Column(Boolean, default=False)
    is_validated = Column(Boolean, default=False)
    deployment_status = Column(String(50), default='inactive')
    
    description = Column(String)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('model_name', 'model_version', name='_model_version_uc'),
    )

class ModelDeploymentHistory(Base):
    __tablename__ = "model_deployment_history"
    
    deployment_id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("model_metadata.model_id"))
    action = Column(String(50), nullable=False)  # deploy, rollback, deactivate
    previous_model_id = Column(Integer, ForeignKey("model_metadata.model_id"))
    deployment_time = Column(DateTime, default=datetime.utcnow)
    deployed_by = Column(String(100))
    notes = Column(Text)

class ModelPerformanceMonitoring(Base):
    __tablename__ = "model_performance_monitoring"
    
    monitoring_id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("model_metadata.model_id"))
    monitoring_date = Column(Date, nullable=False)
    
    # 일별 집계 메트릭
    total_predictions = Column(Integer, default=0)
    avg_inference_time_ms = Column(DECIMAL(10, 2))
    max_inference_time_ms = Column(Integer)
    min_inference_time_ms = Column(Integer)
    
    # 실제 vs 예측 비교 (ground truth 확보 시)
    actual_vs_predicted = Column(JSONB)
    daily_rmse = Column(DECIMAL(10, 4))
    daily_mae = Column(DECIMAL(10, 4))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('model_id', 'monitoring_date', name='_model_monitoring_date_uc'),
    )

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    log_level = Column(String(20))
    service_name = Column(String(50))
    message = Column(Text)
    log_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_ip = Column(String(45))
    user_agent = Column(Text)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    actions_count = Column(Integer, default=0)
    predictions_requested = Column(Integer, default=0)

class Prediction(Base):
    __tablename__ = "predictions"
    
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    stop_id = Column(String(50), ForeignKey("bus_stops.stop_id"))
    route_id = Column(String(50), ForeignKey("bus_routes.route_id"))
    
    prediction_time = Column(DateTime, nullable=False)
    target_time = Column(DateTime, nullable=False)
    prediction_horizon = Column(Integer, nullable=False)
    
    drt_probability = Column(DECIMAL(10, 4), nullable=False)
    predicted_boarding_count = Column(DECIMAL(10, 2))
    predicted_alighting_count = Column(DECIMAL(10, 2))
    
    model_id = Column(Integer, ForeignKey("model_metadata.model_id"))
    model_version = Column(String(50), nullable=False)
    
    input_features = Column(JSON)
    confidence_interval = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class PredictionRequest(Base):
    __tablename__ = "prediction_requests"
    
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_datetime = Column(DateTime, nullable=False)
    requested_stops = Column(Integer, nullable=False)
    model_id = Column(Integer, ForeignKey("model_metadata.model_id"))
    
    preprocessing_time_ms = Column(Integer)
    inference_time_ms = Column(Integer)
    total_time_ms = Column(Integer)
    
    request_source = Column(String(50))
    user_ip = Column(String(45))
    
    created_at = Column(DateTime, default=datetime.utcnow)