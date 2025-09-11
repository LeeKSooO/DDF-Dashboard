import type { Feature, FeatureCollection, Geometry, GeoJsonProperties } from "geojson";

function toFeature(f: any): Feature | null {
  // 이미 Feature라면 그대로
  if (f && f.type === "Feature") return f as Feature;

  // geometry만 있거나, 좌표 뭉치만 온 경우 처리
  if (f?.geometry?.type) {
    return {
      type: "Feature",
      geometry: f.geometry as Geometry,
      properties: f.properties ?? {},
    };
  }

  // f 자체가 geometry일 수 있음 (예: {type:"Polygon", coordinates:[...]})
  if (f?.type && f.coordinates) {
    return {
      type: "Feature",
      geometry: f as Geometry,
      properties: {},
    };
  }

  // 마지막 안전망: 알 수 없는 구조는 null 반환
  return null;
}

/**
 * 다양한 형태의 GeoJSON 데이터를 유효한 FeatureCollection으로 변환
 * deck.gl GeoJsonLayer에서 발생하는 type 필드 누락 에러를 방지
 */
export function ensureFeatureCollection(data: any): FeatureCollection {
  // 문자열이면 파싱
  if (typeof data === "string") {
    try { 
      data = JSON.parse(data); 
    } catch { 
      return { type: "FeatureCollection", features: [] };
    }
  }

  // 이미 올바른 FeatureCollection
  if (data?.type === "FeatureCollection" && Array.isArray(data.features)) {
    const cleaned = data.features
      .map(toFeature)
      .filter(Boolean)
      .filter((f: Feature) => f.geometry && f.geometry.type);
    return { type: "FeatureCollection", features: cleaned };
  }

  // Feature 하나만 온 경우
  if (data?.type === "Feature" && data.geometry?.type) {
    return { type: "FeatureCollection", features: [data] };
  }

  // Geometry 하나만 온 경우
  if (data?.type && data.coordinates) {
    const feature = toFeature(data);
    return { type: "FeatureCollection", features: feature ? [feature] : [] };
  }

  // 배열이 온 경우 (features 배열 혹은 feature/geometry 배열이라고 가정)
  if (Array.isArray(data)) {
    const features = data
      .map(toFeature)
      .filter(Boolean)
      .filter((f: Feature) => f.geometry && f.geometry.type);
    return { type: "FeatureCollection", features };
  }

  // {features:[...]} 형태인데 type이 없는 경우
  if (data?.features && Array.isArray(data.features)) {
    const features = data.features
      .map(toFeature)
      .filter(Boolean)
      .filter((f: Feature) => f.geometry && f.geometry.type);
    return { type: "FeatureCollection", features };
  }

  // 여기까지 왔다면 구조가 많이 어긋난 것
  console.warn("Unknown GeoJSON structure, returning empty FeatureCollection:", data);
  return { type: "FeatureCollection", features: [] };
}

/**
 * GeoJSON 데이터 유효성 검사
 */
export function validateGeoJSON(data: any): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  try {
    const fc = ensureFeatureCollection(data);
    
    if (!fc.features.length) {
      errors.push("No valid features found");
    }

    fc.features.forEach((feature, index) => {
      if (!feature.geometry) {
        errors.push(`Feature ${index}: Missing geometry`);
      } else if (!feature.geometry.type) {
        errors.push(`Feature ${index}: Missing geometry type`);
      } else if (!feature.geometry.coordinates) {
        errors.push(`Feature ${index}: Missing coordinates`);
      }
    });

    return {
      valid: errors.length === 0,
      errors
    };
  } catch (error) {
    errors.push(`Parsing error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    return { valid: false, errors };
  }
}