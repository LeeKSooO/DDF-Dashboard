#!/usr/bin/env python3
"""
TorchServe 모델 자동 등록 스크립트
시작 시 .mar 파일들을 스캔하여 DB에 모델 메타데이터 등록
"""
import os
import sys
import time
import json
import logging
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelRegistration:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST', 'postgres'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'ddf_db'),
            'user': os.getenv('DB_USER', 'ddf_user'),
            'password': os.getenv('DB_PASSWORD', 'ddf_password')
        }
        self.model_store_path = Path('/home/model-server/model-store')
        self.torchserve_host = os.getenv('TORCHSERVE_HOST', 'torchserve')
        self.torchserve_port = int(os.getenv('TORCHSERVE_MANAGEMENT_PORT', 8081))
        self.torchserve_url = f'http://{self.torchserve_host}:{self.torchserve_port}'
        
    def wait_for_db(self, max_retries=30, retry_interval=2):
        """PostgreSQL 연결 대기"""
        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(**self.db_config)
                conn.close()
                logger.info("✅ PostgreSQL connection established")
                return True
            except psycopg2.OperationalError as e:
                logger.info(f"⏳ Waiting for PostgreSQL... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_interval)
        
        logger.error("❌ Failed to connect to PostgreSQL after maximum retries")
        return False
    
    def wait_for_torchserve(self, max_retries=30, retry_interval=2):
        """TorchServe 연결 대기"""
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.torchserve_url}/ping", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ TorchServe connection established")
                    return True
            except requests.RequestException:
                logger.info(f"⏳ Waiting for TorchServe... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_interval)
        
        logger.error("❌ Failed to connect to TorchServe after maximum retries")
        return False
    
    def get_torchserve_models(self):
        """TorchServe Management API에서 모델 정보 조회"""
        try:
            response = requests.get(f"{self.torchserve_url}/models", timeout=10)
            if response.status_code == 200:
                models = response.json()
                logger.info(f"📋 Found {len(models)} models in TorchServe")
                return models
            else:
                logger.warning(f"⚠️ TorchServe models API returned status {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"❌ Failed to fetch models from TorchServe: {e}")
            return []
    
    def get_model_details(self, model_name):
        """특정 모델의 상세 정보 조회"""
        try:
            response = requests.get(f"{self.torchserve_url}/models/{model_name}", timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get model details for {model_name}: {e}")
            return None
    
    def get_existing_models(self):
        """DB에서 기존 모델 정보 조회"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT model_name, model_version, is_active 
                        FROM model_metadata 
                        ORDER BY created_at DESC
                    """)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch existing models: {e}")
            return []
    
    def register_model_from_torchserve(self, model_name, model_version="1.0"):
        """TorchServe에서 실제 모델 정보를 가져와 DB에 등록"""
        try:
            # TorchServe에서 모델 상세 정보 조회
            model_details = self.get_model_details(model_name)
            
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    # 기존 모델 존재 확인
                    cur.execute("""
                        SELECT model_id FROM model_metadata 
                        WHERE model_name = %s AND model_version = %s
                    """, (model_name, model_version))
                    
                    if cur.fetchone():
                        logger.info(f"⚠️  Model {model_name} v{model_version} already exists - updating...")
                        # 기존 모델 업데이트
                        cur.execute("""
                            UPDATE model_metadata SET
                                deployment_status = %s,
                                updated_at = %s,
                                description = %s
                            WHERE model_name = %s AND model_version = %s
                        """, (
                            'active',
                            datetime.now(),
                            f'Updated from TorchServe at {datetime.now()}',
                            model_name, model_version
                        ))
                        logger.info(f"✅ Model {model_name} v{model_version} updated")
                        return True
                    
                    # 새 모델 등록 (TorchServe 정보 + 기본값 조합)
                    cur.execute("""
                        INSERT INTO model_metadata (
                            model_name, model_version, model_type,
                            model_architecture, hyperparameters, normalization_stats,
                            model_path, stats_path, graph_path,
                            is_active, is_validated, deployment_status,
                            description, created_by
                        ) VALUES (
                            %s, %s, 'MST-GCN',
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, true, 'active',
                            %s, 'torchserve-api'
                        )
                    """, (
                        model_name, model_version,
                        json.dumps({
                            "name": "Multi-Scale Temporal Graph Convolutional Network",
                            "num_of_vertices": 957,
                            "in_channels": 4,
                            "features": ["normalized_log_boarding_count", "service_availability", "is_rest_day", "normalized_interval"],
                            "torchserve_details": model_details if model_details else "API query failed"
                        }),
                        json.dumps({
                            "K": 3, "nb_block": 2, "nb_chev_filter": 64,
                            "nb_time_filter": 64, "learning_rate": 0.001
                        }),
                        json.dumps({"mean": 0.1110, "std": 1.1544, "method": "z-score"}),
                        f'/app/ddf_model/{model_name}_model_v1.pt',
                        '/app/ddf_model/stats.npz',
                        '/app/ddf_model/adj_mx.npy',
                        True,  # 첫 번째 모델은 활성화
                        f'{model_name.upper()} model registered from TorchServe at {datetime.now()}'
                    ))
                    
                    logger.info(f"✅ Model {model_name} v{model_version} registered from TorchServe")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to register model {model_name} from TorchServe: {e}")
            return False
    
    def scan_and_register_models(self):
        """TorchServe에서 실제 로드된 모델들을 스캔하여 등록"""
        # 1. TorchServe에서 실제 로드된 모델들 조회
        torchserve_models = self.get_torchserve_models()
        
        if not torchserve_models:
            # TorchServe에서 모델을 못 가져오면 fallback으로 .mar 파일 스캔
            logger.warning("No models found in TorchServe, falling back to .mar file scan")
            return self.scan_mar_files()
        
        registered_count = 0
        for model_info in torchserve_models:
            model_name = model_info.get('modelName', 'unknown')
            model_version = model_info.get('modelVersion', '1.0')
            
            logger.info(f"🔍 Processing model: {model_name} (version: {model_version})")
            
            if self.register_model_from_torchserve(model_name, model_version):
                registered_count += 1
        
        logger.info(f"📊 Model registration summary: {registered_count} models processed from TorchServe")
        return registered_count > 0
    
    def scan_mar_files(self):
        """Fallback: .mar 파일들을 스캔하여 등록"""
        if not self.model_store_path.exists():
            logger.warning(f"Model store path not found: {self.model_store_path}")
            return False
        
        mar_files = list(self.model_store_path.glob("*.mar"))
        if not mar_files:
            logger.warning("No .mar files found in model store")
            return False
        
        registered_count = 0
        for mar_file in mar_files:
            model_name = mar_file.stem  # 파일명에서 확장자 제거
            
            if self.register_model_from_torchserve(model_name):
                registered_count += 1
        
        logger.info(f"📊 Fallback registration summary: {registered_count} models from .mar files")
        return registered_count > 0
    
    def create_ready_signal(self):
        """모델 등록 완료 신호 파일 생성"""
        ready_file = Path('/tmp/models_registered')
        ready_file.touch()
        logger.info("🚀 Model registration completed - ready signal created")

def main():
    logger.info("🔄 Starting enhanced TorchServe model registration...")
    
    registrar = ModelRegistration()
    
    # 1. DB 연결 대기
    if not registrar.wait_for_db():
        sys.exit(1)
    
    # 2. TorchServe 연결 대기
    if not registrar.wait_for_torchserve():
        logger.warning("⚠️  TorchServe not available, will try fallback registration")
    
    # 3. 모델 스캔 및 등록 (TorchServe API 우선, .mar 파일 fallback)
    if not registrar.scan_and_register_models():
        logger.warning("⚠️  No models registered, but continuing...")
    
    # 4. 완료 신호 생성
    registrar.create_ready_signal()
    
    logger.info("✅ Enhanced model registration process completed successfully")

if __name__ == "__main__":
    main()