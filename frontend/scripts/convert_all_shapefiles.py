#!/usr/bin/env python3
"""
모든 행정구역 Shapefile을 서울시 데이터로 변환하는 스크립트
- CTPRVN: 시도 단위 (서울특별시)
- SIG: 시군구 단위 (서울시 25개 구)  
- EMD: 읍면동 단위 (서울시 467개 동)
"""

import geopandas as gpd
import json
import pandas as pd
import os

def process_shapefile(input_path, output_path, filter_condition, simplify_tolerance=0.0001):
    """Shapefile을 처리하여 서울시 데이터만 추출하고 GeoJSON으로 변환"""
    try:
        print(f"\n📁 Processing: {input_path}")
        
        # Shapefile 읽기
        gdf = gpd.read_file(input_path)
        print(f"  Total features: {len(gdf)}")
        print(f"  Columns: {list(gdf.columns)}")
        
        # 서울시 데이터 필터링
        if filter_condition:
            seoul_gdf = gdf[filter_condition(gdf)]
        else:
            seoul_gdf = gdf
            
        print(f"  Seoul features: {len(seoul_gdf)}")
        
        if len(seoul_gdf) == 0:
            print("  ⚠️ No Seoul data found")
            return False
        
        # 샘플 데이터 출력
        if len(seoul_gdf) > 0:
            print("  📋 Sample records:")
            for col in seoul_gdf.columns:
                if col != 'geometry' and seoul_gdf[col].dtype == 'object':
                    sample_values = seoul_gdf[col].head(3).tolist()
                    print(f"    {col}: {sample_values}")
                    break
        
        # 좌표계 설정 및 변환
        if seoul_gdf.crs is None:
            print("  🔄 Setting CRS to Korean coordinate system (EPSG:5179)")
            seoul_gdf = seoul_gdf.set_crs('EPSG:5179')
            
        if seoul_gdf.crs != 'EPSG:4326':
            print("  🌐 Converting to WGS84 (EPSG:4326)")
            seoul_gdf = seoul_gdf.to_crs('EPSG:4326')
        
        # 기하 단순화 (성능 향상)
        print(f"  ✂️ Simplifying geometry (tolerance: {simplify_tolerance})")
        seoul_gdf['geometry'] = seoul_gdf['geometry'].simplify(simplify_tolerance)
        
        # GeoJSON 변환 및 저장
        geojson = seoul_gdf.to_json(ensure_ascii=False)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(geojson)
        
        size_mb = len(geojson) / 1024 / 1024
        print(f"  ✅ Saved to: {output_path}")
        print(f"  📦 File size: {size_mb:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error processing {input_path}: {e}")
        return False

def main():
    base_path = '/home/pak3430/Workspace/DDF-MSTGCN/frontend'
    reference_path = f'{base_path}/reference'
    output_path = f'{base_path}/public/reference'
    
    print("🗺️ Converting Korean Administrative Shapefiles to Seoul GeoJSON")
    print("=" * 60)
    
    # 1. 시도 단위 (CTPRVN) - 서울특별시
    ctprvn_success = process_shapefile(
        input_path=f'{reference_path}/ctprvn_20230729/ctprvn.shp',
        output_path=f'{output_path}/seoul_ctprvn.json',
        filter_condition=lambda gdf: gdf['CTPRVN_CD'].str.startswith('11') if 'CTPRVN_CD' in gdf.columns else gdf.iloc[:0],
        simplify_tolerance=0.001  # 시도 단위는 덜 단순화
    )
    
    # 2. 시군구 단위 (SIG) - 서울시 25개 구
    sig_success = process_shapefile(
        input_path=f'{reference_path}/sig_20230729/sig.shp',
        output_path=f'{output_path}/seoul_sig.json',
        filter_condition=lambda gdf: gdf['SIG_CD'].str.startswith('11') if 'SIG_CD' in gdf.columns else gdf.iloc[:0],
        simplify_tolerance=0.0005  # 구 단위는 적당히 단순화
    )
    
    # 3. 읍면동 단위 (EMD) - 이미 생성되었지만 다시 생성 (일관성을 위해)
    emd_success = process_shapefile(
        input_path=f'{reference_path}/emd_20230729/emd.shp',
        output_path=f'{output_path}/seoul_emd_v2.json',  # 새 버전
        filter_condition=lambda gdf: gdf['EMD_CD'].str.startswith('11') if 'EMD_CD' in gdf.columns else gdf.iloc[:0],
        simplify_tolerance=0.0001  # 동 단위는 많이 단순화
    )
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"✅ 시도 (CTPRVN): {'Success' if ctprvn_success else 'Failed'}")
    print(f"✅ 시군구 (SIG): {'Success' if sig_success else 'Failed'}")  
    print(f"✅ 읍면동 (EMD): {'Success' if emd_success else 'Failed'}")
    
    if all([ctprvn_success, sig_success, emd_success]):
        print("\n🎉 All shapefiles converted successfully!")
        print("📁 Files available at: /public/reference/")
        print("  - seoul_ctprvn.json (시도)")
        print("  - seoul_sig.json (구)")
        print("  - seoul_emd_v2.json (동)")
        
        # 통계 정보 생성
        try:
            print("\n📈 STATISTICS")
            print("-" * 30)
            
            # SIG 통계 (구별 정보)
            if sig_success:
                sig_gdf = gpd.read_file(f'{output_path}/seoul_sig.json')
                print(f"서울시 구 개수: {len(sig_gdf)}개")
                if len(sig_gdf) > 0 and 'SIG_KOR_NM' in sig_gdf.columns:
                    gu_list = sorted(sig_gdf['SIG_KOR_NM'].tolist())
                    print("구 목록:")
                    for i in range(0, len(gu_list), 5):
                        row = gu_list[i:i+5]
                        print(f"  {', '.join(row)}")
                        
        except Exception as e:
            print(f"Statistics error: {e}")
    else:
        print("\n❌ Some conversions failed. Check the logs above.")

if __name__ == "__main__":
    main()