#!/usr/bin/env python3
"""
GeoJSON 파일의 한글 인코딩 문제를 수정하는 스크립트
"""

import json
import geopandas as gpd

def fix_geojson_encoding(input_path, output_path):
    """GeoJSON 파일의 한글 인코딩을 수정"""
    try:
        print(f"🔧 Fixing encoding for: {input_path}")
        
        # Shapefile을 다시 읽어서 올바른 인코딩으로 처리
        if 'sig' in input_path.lower():
            gdf = gpd.read_file('/home/pak3430/Workspace/DDF-MSTGCN/frontend/reference/sig_20230729/sig.shp', encoding='cp949')
            # 서울시 데이터만 필터링
            gdf = gdf[gdf['SIG_CD'].str.startswith('11')]
        elif 'emd' in input_path.lower():
            gdf = gpd.read_file('/home/pak3430/Workspace/DDF-MSTGCN/frontend/reference/emd_20230729/emd.shp', encoding='cp949')
            # 서울시 데이터만 필터링
            gdf = gdf[gdf['EMD_CD'].str.startswith('11')]
        elif 'ctprvn' in input_path.lower():
            gdf = gpd.read_file('/home/pak3430/Workspace/DDF-MSTGCN/frontend/reference/ctprvn_20230729/ctprvn.shp', encoding='cp949')
            # 서울시 데이터만 필터링
            gdf = gdf[gdf['CTPRVN_CD'].str.startswith('11')]
        else:
            print(f"Unknown file type: {input_path}")
            return False
        
        # 좌표계 설정 및 변환
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:5179')
        if gdf.crs != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        
        # 기하 단순화
        gdf['geometry'] = gdf['geometry'].simplify(0.0001)
        
        # UTF-8로 GeoJSON 저장
        geojson_str = gdf.to_json(ensure_ascii=False)
        
        # 파일로 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(geojson_str)
        
        # 한글이 제대로 저장되었는지 확인
        data = json.loads(geojson_str)
        if data['features']:
            sample_feature = data['features'][0]
            print(f"✅ Sample data: {sample_feature.get('properties', {})}")
        
        print(f"✅ Fixed and saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    base_path = '/home/pak3430/Workspace/DDF-MSTGCN/frontend/public/reference'
    
    print("🔧 Fixing Korean encoding in GeoJSON files")
    print("=" * 60)
    
    files_to_fix = [
        ('seoul_sig.json', 'seoul_sig_fixed.json'),
        ('seoul_emd_v2.json', 'seoul_emd_fixed.json'),
        ('seoul_ctprvn.json', 'seoul_ctprvn_fixed.json')
    ]
    
    for input_file, output_file in files_to_fix:
        input_path = f"{base_path}/{input_file}"
        output_path = f"{base_path}/{output_file}"
        fix_geojson_encoding(input_path, output_path)
        print()
    
    print("=" * 60)
    print("✅ All files have been fixed!")
    print("📁 Fixed files:")
    for _, output_file in files_to_fix:
        print(f"  - {output_file}")

if __name__ == "__main__":
    main()