#!/usr/bin/env python3
"""
SIG 데이터의 서울시 코드 패턴 확인
"""

import geopandas as gpd
import pandas as pd

def main():
    try:
        print("🔍 Checking SIG codes for Seoul...")
        
        # SIG Shapefile 읽기
        gdf = gpd.read_file('/home/pak3430/Workspace/DDF-MSTGCN/frontend/reference/sig_20230729/sig.shp')
        
        print(f"Total SIG features: {len(gdf)}")
        print(f"Columns: {list(gdf.columns)}")
        
        # 서울시 관련 코드들 찾기
        if 'SIG_CD' in gdf.columns:
            print("\n📋 All SIG codes starting with '11':")
            seoul_codes = gdf[gdf['SIG_CD'].str.startswith('11')]
            
            for idx, row in seoul_codes.iterrows():
                code = row['SIG_CD']
                kor_name = row.get('SIG_KOR_NM', 'N/A')
                eng_name = row.get('SIG_ENG_NM', 'N/A')
                print(f"  {code}: {kor_name} ({eng_name})")
            
            print(f"\nTotal Seoul SIG found: {len(seoul_codes)}")
            
            # 서울시 구 코드 패턴 분석
            print("\n🔍 Code pattern analysis:")
            all_11_codes = gdf[gdf['SIG_CD'].str.startswith('11')]['SIG_CD'].tolist()
            print(f"All codes starting with '11': {len(all_11_codes)}")
            
            # 5자리 코드 중 서울시는 111로 시작
            seoul_111_codes = gdf[gdf['SIG_CD'].str.startswith('111')]['SIG_CD'].tolist()
            print(f"Codes starting with '111': {len(seoul_111_codes)}")
            print(f"Sample '111' codes: {seoul_111_codes[:10]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()