# DRT 분석 지표

1. 히트맵용 구별 DRT 점수 조회

주요 기능:

히트맵 렌더링용 정류장별 DRT 점수 및 좌표 (stations 배열)
대시보드 Top 5 리스트 표시 (top_stations 배열)
모델 변경시 빠른 업데이트 지원
모델 타입:

commuter: 출퇴근형 (TC, PDR, RU, PCW 지표)
tourism: 관광특화형 (TC, TDR, RU, PCW 지표, 10-16시 가중치)
vulnerable: 교통취약지형 (VAR, SED, MDI, AVS 지표)
사용 예시:

/districts/강남구?model_type=commuter&analysis_month=2025-07-01
/districts/마포구?model_type=tourism&analysis_month=2025-07-01
응답 구조 (요구사항 완전 충족):

{
"district_name": "강남구",
"model_type": "commuter",
"analysis_month": "2025-07",
"stations": [
{
"station_id": "121000012",
"station_name": "지하철2호선강남역",
"coordinate": {"lat": 37.500785, "lng": 127.02637},
"drt_score": 87.5, // 최고점수 시간대 기준
"peak_hour": 8
}
// ... 구 내 모든 정류장
],
"top_stations": [
// 상위 5개 정류장만 (대시보드 Top 5 리스트용)
]
}
🚀 성능 최적화:

히트맵용 최고점수만 표시 (drt_score, peak_hour)
Top 5 미리 계산하여 제공 (top_stations)
모델 전환시 빠른 업데이트 보장

2.  정류장 상세 DRT 분석

주요 기능:

정류장 클릭시 피처 패널 업데이트용
24시간별 DRT 점수 차트 데이터 (hourly_scores)
세부 지표별 점수 분석 (feature_scores)
현재 선택 시간대 정보 (current_hour, current_score)
사용 예시:

/stations/121000012?model_type=commuter&analysis_month=2025-07-01
/stations/121000012?model_type=commuter&analysis_month=2025-07-01&hour=8
응답 구조 (요구사항 완전 충족):

{
"station": {
"station_id": "121000012",
"station_name": "지하철2호선강남역",
"latitude": 37.500785,
"longitude": 127.02637,
"district_name": "강남구",
"administrative_dong": "역삼1동"
},
"model_type": "commuter",
"analysis_month": "2025-07",
"current_hour": 8, // 현재 조회 중인 시간대
"current_score": 87.5, // 현재 시간대 DRT 점수
"peak_score": 87.5,
"peak_hour": 8,
"monthly_average": 65.2,
"feature_scores": { // 모델별 동적 변경
"tc_score": 0.95, // 출퇴근형: TC, PDR, RU, PCW
"pdr_score": 0.87, // 관광특화형: TC, TDR, RU, PCW  
 "ru_score": 0.75, // 교통취약지형: VAR, SED, MDI, AVS
"pcw_score": 1.0
},
"hourly_scores": [ // 차트용 24시간 데이터
{"hour": 0, "score": 45.2},
{"hour": 8, "score": 87.5}
// ... 24시간 전체
]
}
🎯 용도:

히트맵 정류장 클릭시 팝업 표시
시간대별 차트 렌더링 (hourly_scores)
세부 지표 분석 (feature_scores)
시간대 필터링 (hour 파라미터)

3.  모델별 특화 점수 조회 (옵션)

모델별 feature_scores 차이:

출퇴근형 (commuter):

"feature_scores": {
"tc_score": 0.95, // 시간 집중도
"pdr_score": 0.87, // 피크 수요 비율  
 "ru_score": 0.75, // 노선 활용도
"pcw_score": 1.0 // POI 카테고리 가중치
}
관광특화형 (tourism):

"feature_scores": {
"tc_score": 1.14, // 관광 집중도 (10-16시 가중치 1.2)
"tdr_score": 0.94, // 관광 수요 비율 (10-16시 가중치 1.1)
"ru_score": 0.75, // 구간 이용률
"pcw_score": 0.8 // POI 관광 가중치 (관광특구>고궁>상권>공원)
}
교통취약지형 (vulnerable):

"feature_scores": {
"var_score": 0.23, // 취약 접근성 비율
"sed_score": 0.18, // 사회 형평성 수요
"mdi_score": 0.65, // 이동성 불리 지수
"avs_score": 0.7 // 지역 취약성 점수
}
