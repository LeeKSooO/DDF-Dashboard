# AWS 배포 가이드

## 프론트엔드 배포 체크리스트

### 1. 환경변수 설정
`.env.production` 파일을 수정하여 실제 백엔드 API URL을 설정합니다:

```bash
NEXT_PUBLIC_API_URL=https://your-backend-api.amazonaws.com/api/v1
```

### 2. 백엔드 CORS 설정 수정
백엔드 서버의 `backend/app/core/config.py` 파일에서 CORS 설정을 수정해야 합니다:

```python
# backend/app/core/config.py
ALLOWED_HOSTS: List[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://your-frontend-domain.com",  # 프론트엔드 배포 도메인 추가
    "https://your-cloudfront-id.cloudfront.net",  # CloudFront 사용시
    "*"  # 개발 단계에서만 임시로 사용 (프로덕션에서는 구체적인 도메인 명시)
]
```

또는 환경변수로 관리:
```python
import os

ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else [
    "http://localhost:3000",
    "http://localhost:8000",
]
```

### 3. 빌드 및 배포

#### 로컬 빌드 테스트
```bash
# 프로덕션 환경변수로 빌드
npm run build

# 프로덕션 모드로 실행
npm run start
```

#### AWS Amplify 배포시
1. AWS Amplify 콘솔에서 환경변수 설정
2. `NEXT_PUBLIC_API_URL` 추가

#### AWS EC2 배포시
```bash
# EC2 인스턴스에서
export NEXT_PUBLIC_API_URL=http://백엔드-서버-주소:8000/api/v1
npm run build
npm run start
```

#### Docker 배포시
```dockerfile
# Dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
```

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1 -t frontend .
```

### 4. 디버깅

#### 브라우저 콘솔에서 확인
```javascript
// 브라우저 개발자 도구 콘솔
console.log(process.env.NEXT_PUBLIC_API_URL)
```

#### 네트워크 탭에서 확인
- API 요청이 올바른 URL로 가는지 확인
- CORS 에러 메시지 확인

### 5. 일반적인 문제 해결

#### CORS 에러
```
Access to fetch at 'http://backend-api' from origin 'https://frontend' has been blocked by CORS policy
```
**해결**: 백엔드 CORS 설정에 프론트엔드 도메인 추가

#### API 연결 실패
```
Failed to fetch
```
**해결**: 
1. 백엔드 서버가 실행 중인지 확인
2. 보안 그룹/방화벽에서 포트 허용 확인
3. HTTPS/HTTP 프로토콜 일치 확인

#### 환경변수 인식 실패
**해결**:
1. 변수명이 `NEXT_PUBLIC_`으로 시작하는지 확인
2. `.env.production` 파일이 올바른 위치에 있는지 확인
3. 빌드 시점에 환경변수가 설정되었는지 확인

### 6. 보안 권장사항

1. 프로덕션에서는 CORS `*` 대신 구체적인 도메인 명시
2. HTTPS 사용 권장
3. API 키나 민감한 정보는 서버 사이드에서만 사용
4. Rate limiting 적용 고려

### 7. 성능 최적화

1. CDN 사용 (CloudFront)
2. 이미지 최적화 (Next.js Image 컴포넌트)
3. API 응답 캐싱
4. 정적 페이지 생성 (SSG) 활용