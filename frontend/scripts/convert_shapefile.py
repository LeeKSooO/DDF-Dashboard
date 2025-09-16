#!/usr/bin/env python3
"""
EMD Shapefile을 서울시 동 단위 GeoJSON으로 변환하는 스크립트
"""

import geopandas as gpd
import json
import pandas as pd

def main():
    try:
        # Shapefile 읽기
        print("Loading EMD Shapefile...")
        gdf = gpd.read_file('/home/pak3430/Workspace/DDF-MSTGCN/frontend/reference/emd_20230729/emd.shp')
        
        # 데이터 정보 출력
        print(f"Total features: {len(gdf)}")
        print(f"Columns: {list(gdf.columns)}")
        
        # 처음 몇 개 레코드의 속성 확인
        if len(gdf) > 0:
            print("\nFirst 3 records:")
            print(gdf.head(3)[['EMD_CD', 'EMD_ENG_NM', 'EMD_KOR_NM']].to_string() if 'EMD_CD' in gdf.columns else gdf.head(3).to_string())
        
        # 서울시 코드로 필터링 (서울시는 11로 시작)
        print("\nFiltering Seoul data...")
        if 'EMD_CD' in gdf.columns:
            seoul_gdf = gdf[gdf['EMD_CD'].str.startswith('11')]
        elif 'ADM_DR_CD' in gdf.columns:
            seoul_gdf = gdf[gdf['ADM_DR_CD'].str.startswith('11')]
        else:
            # 컬럼명이 다를 수 있으니 모든 컬럼 확인
            print("Available columns:", gdf.columns.tolist())
            code_cols = [col for col in gdf.columns if 'CD' in col.upper()]
            print("Code columns:", code_cols)
            if code_cols:
                seoul_gdf = gdf[gdf[code_cols[0]].astype(str).str.startswith('11')]
            else:
                print("Warning: Could not find Seoul data, using all data")
                seoul_gdf = gdf
        
        print(f"Seoul features: {len(seoul_gdf)}")
        
        # 좌표계 확인 및 WGS84로 변환
        print(f"Original CRS: {seoul_gdf.crs}")
        if seoul_gdf.crs is None:
            print("No CRS found, assuming Korean coordinate system (EPSG:5179)...")
            seoul_gdf = seoul_gdf.set_crs('EPSG:5179')  # Korean 2000 / Central Belt 2010
            print("Converting to WGS84 (EPSG:4326)...")
            seoul_gdf = seoul_gdf.to_crs('EPSG:4326')
        elif seoul_gdf.crs != 'EPSG:4326':
            print("Converting to WGS84 (EPSG:4326)...")
            seoul_gdf = seoul_gdf.to_crs('EPSG:4326')
        
        # 간소화 (성능 향상을 위해)
        print("Simplifying geometry...")
        seoul_gdf['geometry'] = seoul_gdf['geometry'].simplify(0.0001)
        
        # GeoJSON 변환
        geojson = seoul_gdf.to_json()
        
        # 파일 저장
        output_path = '/home/pak3430/Workspace/DDF-MSTGCN/frontend/public/reference/seoul_emd.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(geojson)
        
        print(f"\n✅ Seoul EMD GeoJSON saved to: {output_path}")
        print(f"File size: {len(geojson) / 1024 / 1024:.1f} MB")
        
        # 구별 통계
        if len(seoul_gdf) > 0:
            if 'EMD_CD' in seoul_gdf.columns:
                gu_codes = seoul_gdf['EMD_CD'].str[:5].value_counts()
                print(f"\n구별 동 개수:")
                for gu_code, count in gu_codes.head(10).items():
                    print(f"  {gu_code}: {count}개 동")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()