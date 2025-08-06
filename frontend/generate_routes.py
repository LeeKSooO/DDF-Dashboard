#!/usr/bin/env python3
"""
가평군 버스 노선 데이터를 CSV에서 GeoJSON으로 변환하는 스크립트
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any

def create_routes_geojson():
    """CSV 파일들을 읽어서 GeoJSON 형태의 노선 데이터를 생성"""
    
    # 파일 경로 설정
    base_path = Path(__file__).parent.parent
    routes_csv = base_path / "data/raw/routes/routes.csv"
    route_stops_csv = base_path / "data/raw/routes/route_stops.csv"
    output_path = base_path / "frontend/public/data/bus_routes.json"
    
    print(f"노선 정보 파일: {routes_csv}")
    print(f"노선-정류장 매핑 파일: {route_stops_csv}")
    
    # CSV 파일 읽기
    routes_df = pd.read_csv(routes_csv)
    route_stops_df = pd.read_csv(route_stops_csv)
    
    print(f"총 노선 수: {len(routes_df)}")
    print(f"총 노선-정류장 매핑: {len(route_stops_df)}")
    
    # GeoJSON 구조 생성
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # 각 노선별로 처리
    for _, route in routes_df.iterrows():
        route_id = route['routeid']
        route_no = route['routeno']
        route_type = route['routetp']
        start_node = route['startnodenm']
        end_node = route['endnodenm']
        
        # 해당 노선의 정류장들을 순서대로 가져오기
        route_stops = route_stops_df[
            route_stops_df['routeid'] == route_id
        ].sort_values('nodeord')
        
        if len(route_stops) < 2:
            print(f"노선 {route_no} ({route_id}): 정류장이 부족함 (건너뜀)")
            continue
        
        # 좌표 배열 생성
        coordinates = []
        for _, stop in route_stops.iterrows():
            lng = float(stop['gpslong'])
            lat = float(stop['gpslati'])
            coordinates.append([lng, lat])
        
        # GeoJSON Feature 생성
        feature = {
            "type": "Feature",
            "properties": {
                "route_id": route_id,
                "route_no": route_no,
                "route_type": route_type,
                "start_node": start_node,
                "end_node": end_node,
                "stop_count": len(route_stops),
                "color": get_route_color(route_type)
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }
        
        geojson["features"].append(feature)
        print(f"노선 {route_no}: {len(coordinates)}개 정류장")
    
    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # JSON 파일 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    
    print(f"\nGeoJSON 파일 생성 완료: {output_path}")
    print(f"총 {len(geojson['features'])}개 노선 생성")
    
    return geojson

def get_route_color(route_type: str) -> str:
    """노선 유형에 따른 색상 반환"""
    color_map = {
        '농어촌(일반)버스': '#4CAF50',     # 초록색
        '농어촌(좌석)버스': '#2196F3',     # 파란색  
        '직행좌석버스': '#F44336',         # 빨간색
        '일반버스': '#FF9800',             # 주황색
    }
    return color_map.get(route_type, '#9E9E9E')  # 기본: 회색

if __name__ == "__main__":
    try:
        routes_data = create_routes_geojson()
        print("✅ 노선 데이터 변환 완료!")
        
        # 통계 출력
        route_types = {}
        for feature in routes_data["features"]:
            route_type = feature["properties"]["route_type"]
            route_types[route_type] = route_types.get(route_type, 0) + 1
        
        print("\n📊 노선 유형별 통계:")
        for route_type, count in route_types.items():
            print(f"  {route_type}: {count}개")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise