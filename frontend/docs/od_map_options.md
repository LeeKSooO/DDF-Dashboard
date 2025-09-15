# OD 분석 지도 타일 옵션

## 현재 사용 중: CartoDB Positron (밝은 스타일)
```javascript
data: [
  'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
  'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
]
```

## 다른 옵션들

### CartoDB Dark Matter (어두운 스타일)
```javascript
data: [
  'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
]
```

### CartoDB Voyager (컬러풀한 스타일)
```javascript
data: [
  'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
  'https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
  'https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
  'https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'
]
```

### OpenStreetMap (표준)
```javascript
data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
```

### Stamen Toner (흑백 스타일)
```javascript
data: [
  'https://stamen-tiles-a.a.ssl.fastly.net/toner/{z}/{x}/{y}.png',
  'https://stamen-tiles-b.a.ssl.fastly.net/toner/{z}/{x}/{y}.png',
  'https://stamen-tiles-c.a.ssl.fastly.net/toner/{z}/{x}/{y}.png',
  'https://stamen-tiles-d.a.ssl.fastly.net/toner/{z}/{x}/{y}.png'
]
```

### Mapbox (API 키 필요)
```javascript
data: `https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`
```

## 구현된 기능

✅ **CartoDB Positron 타일 맵**
- 밝고 깔끔한 스타일로 OD 플로우와 잘 어울림
- 4개 서버 로드 밸런싱으로 빠른 로딩

✅ **투명도 조정된 경계 레이어**
- 시도: 투명도 30
- 구: 투명도 20, 호버시 80
- 동: 선만 표시, 투명 배경

✅ **레이어 순서 최적화**
1. CartoDB 타일 (최하단)
2. 서울시 경계
3. 구 경계
4. 동 경계
5. 정류장
6. OD 플로우 (최상단)

이제 Leaflet과 동일한 수준의 상세한 지도를 deck.gl에서도 볼 수 있습니다!