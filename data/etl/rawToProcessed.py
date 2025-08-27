#!/usr/bin/env python3
"""
Raw to Processed Data Pipeline
서울시 인가 노선 기준으로 raw 데이터를 필터링하여 processed 데이터 생성
"""

import pandas as pd
import os
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RawToProcessed:
    def __init__(self, raw_dir, processed_dir):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        
        # processed 디렉토리 생성
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Raw directory: {self.raw_dir}")
        logger.info(f"Processed directory: {self.processed_dir}")
    
    def load_authorized_route_names(self):
        """1. 202507_authorized_route.csv의 인가 노선명들을 모두 추출"""
        file_path = self.raw_dir / '202507_authorized_route.csv'
        logger.info(f"Loading authorized route names from {file_path}")
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 노선명 추출 및 정리
            authorized_routes = set(df['노선명'].str.strip().unique())
            
            logger.info(f"✅ Loaded {len(authorized_routes)} authorized route names")
            logger.info(f"   Sample routes: {list(authorized_routes)[:10]}")
            
            return authorized_routes
            
        except Exception as e:
            logger.error(f"❌ Error loading authorized route names: {e}")
            raise
    
    def filter_route_info(self, authorized_routes=None):
        """2. seoul_route_info.csv를 필터링 (Type 8만 제외)"""
        input_path = self.raw_dir / 'seoul_route_info.csv'
        output_path = self.processed_dir / 'seoul_route_info_filtered.csv'
        
        logger.info(f"Filtering route info from {input_path}")
        
        try:
            df = pd.read_csv(input_path, encoding='utf-8-sig')
            original_count = len(df)
            
            # Type 8 (기타) 제외 필터링
            df = df[df['노선유형'] != 8]
            
            # 노선 타입별 통계 로깅
            type_counts = df['노선유형'].value_counts().sort_index()
            type_mapping = {
                1: '간선버스', 2: '지선버스', 3: '순환버스', 
                4: '광역버스', 5: '마을버스', 6: '공항버스', 7: '심야버스'
            }
            
            logger.info("📊 Route types included:")
            for route_type, count in type_counts.items():
                type_name = type_mapping.get(route_type, f'Type {route_type}')
                logger.info(f"   Type {route_type} ({type_name}): {count} routes")
            
            # 노선명 중복 제거 (첫 번째 것만 유지)
            df = df.drop_duplicates(subset=['노선명'], keep='first')
            
            filtered_count = len(df)
            unique_routes = df['노선명'].nunique()
            
            # 저장
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"✅ Filtered route info: {original_count} → {filtered_count} records")
            logger.info(f"   Unique route names: {unique_routes}")
            logger.info(f"   Saved to: {output_path}")
            
            # 필터링된 route_id 목록 반환
            return set(df['노선ID'].astype(str).unique())
            
        except Exception as e:
            logger.error(f"❌ Error filtering route info: {e}")
            raise
    
    def filter_route_nodes(self, authorized_route_ids):
        """3. seoul_route_node.csv를 인가된 노선 기준으로 필터링"""
        input_path = self.raw_dir / 'seoul_route_node.csv'
        output_path = self.processed_dir / 'seoul_route_node_filtered.csv'
        
        logger.info(f"Filtering route-node mappings from {input_path}")
        
        try:
            df = pd.read_csv(input_path, encoding='utf-8-sig')
            original_count = len(df)
            
            # 노선ID로 필터링
            df['노선ID_str'] = df['노선ID'].astype(str)
            df = df[df['노선ID_str'].isin(authorized_route_ids)]
            df = df.drop(columns=['노선ID_str'])
            
            filtered_count = len(df)
            unique_nodes = df['노드ID'].nunique()
            unique_routes = df['노선ID'].nunique()
            
            # 저장
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"✅ Filtered route-node mappings: {original_count} → {filtered_count} records")
            logger.info(f"   Unique routes: {unique_routes}")
            logger.info(f"   Unique nodes: {unique_nodes}")
            logger.info(f"   Saved to: {output_path}")
            
            # 필터링된 node_id 목록 반환
            return set(df['노드ID'].astype(str).unique())
            
        except Exception as e:
            logger.error(f"❌ Error filtering route nodes: {e}")
            raise
    
    def filter_node_info(self, used_node_ids):
        """4. seoul_node_info.csv를 사용되는 노드만 필터링"""
        input_path = self.raw_dir / 'seoul_node_info.csv'
        output_path = self.processed_dir / 'seoul_node_info_filtered.csv'
        
        logger.info(f"Filtering node info from {input_path}")
        
        try:
            df = pd.read_csv(input_path, encoding='utf-8-sig')
            original_count = len(df)
            
            # 노드ID로 필터링
            df['노드ID_str'] = df['노드ID'].astype(str)
            df = df[df['노드ID_str'].isin(used_node_ids)]
            df = df.drop(columns=['노드ID_str'])
            
            filtered_count = len(df)
            node_types = df['노드유형'].value_counts().to_dict()
            
            # 저장
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            logger.info(f"✅ Filtered node info: {original_count} → {filtered_count} records")
            logger.info(f"   Node type distribution: {node_types}")
            logger.info(f"   Saved to: {output_path}")
            
            return filtered_count
            
        except Exception as e:
            logger.error(f"❌ Error filtering node info: {e}")
            raise
    
    def copy_other_files(self):
        """나머지 파일들 그대로 복사"""
        files_to_copy = [
            'HangJeongDong_ver20250401.geojson'
        ]
        
        for filename in files_to_copy:
            input_path = self.raw_dir / filename
            output_path = self.processed_dir / filename
            
            if input_path.exists():
                # 파일 복사 (pandas 대신 직접 복사)
                import shutil
                shutil.copy2(input_path, output_path)
                logger.info(f"✅ Copied {filename}")
            else:
                logger.warning(f"⚠️  File not found: {filename}")
    
    def print_summary(self, authorized_routes, route_ids, node_ids):
        """처리 결과 요약 출력"""
        logger.info("=" * 60)
        logger.info("PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📋 Authorized route names: {len(authorized_routes)}")
        logger.info(f"🚌 Filtered route IDs: {len(route_ids)}")
        logger.info(f"🚏 Filtered node IDs: {len(node_ids)}")
        logger.info("=" * 60)
        
        # 통계 정보를 파일로 저장
        summary = {
            'authorized_routes_count': len(authorized_routes),
            'filtered_route_ids_count': len(route_ids),
            'filtered_node_ids_count': len(node_ids),
            'authorized_routes_sample': list(authorized_routes)[:20]
        }
        
        import json
        summary_path = self.processed_dir / 'filter_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"📊 Summary saved to: {summary_path}")
    
    def print_summary_v2(self, route_ids, node_ids):
        """처리 결과 요약 출력 (Type 8 제외 방식)"""
        logger.info("=" * 60)
        logger.info("PROCESSING SUMMARY (Type 8 excluded)")
        logger.info("=" * 60)
        logger.info(f"🚌 Filtered route IDs: {len(route_ids)}")
        logger.info(f"🚏 Filtered node IDs: {len(node_ids)}")
        logger.info("=" * 60)
        
        # 통계 정보를 파일로 저장
        summary = {
            'filter_method': 'exclude_type_8',
            'filtered_route_ids_count': len(route_ids),
            'filtered_node_ids_count': len(node_ids)
        }
        
        import json
        summary_path = self.processed_dir / 'filter_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"📊 Summary saved to: {summary_path}")
    
    def run(self):
        """전체 파이프라인 실행 (Type 8 제외 필터링)"""
        logger.info("🚀 Starting Raw to Processed Pipeline (excluding Type 8 routes)...")
        
        try:
            # 1. seoul_route_info.csv 필터링 (Type 8 제외)
            authorized_route_ids = self.filter_route_info()
            
            # 2. seoul_route_node.csv 필터링
            used_node_ids = self.filter_route_nodes(authorized_route_ids)
            
            # 3. seoul_node_info.csv 필터링
            self.filter_node_info(used_node_ids)
            
            # 4. 나머지 파일 복사
            self.copy_other_files()
            
            # 5. 요약 출력
            self.print_summary_v2(authorized_route_ids, used_node_ids)
            
            logger.info("✅ Raw to Processed Pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            raise


def main():
    """메인 실행 함수"""
    import sys
    
    # 기본 경로 설정
    base_dir = sys.argv[1] if len(sys.argv) > 1 else '/Users/leekyoungsoo/teamProject/DDF-ASTGCN/data'
    
    raw_dir = os.path.join(base_dir, 'raw/busInfra')
    processed_dir = os.path.join(base_dir, 'processed/busInfra')
    
    # 파이프라인 실행
    pipeline = RawToProcessed(raw_dir, processed_dir)
    pipeline.run()


if __name__ == "__main__":
    main()