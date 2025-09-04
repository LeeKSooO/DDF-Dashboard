# AWS 배포 단계별 가이드

## 배포 전 준비사항 체크리스트
- [ ] AWS 계정 준비
- [ ] 백엔드 API 서버 실행 중 (URL 확인)
- [ ] Git 저장소에 코드 푸시 완료

---

## 옵션 1: AWS Amplify (가장 쉬움) ⭐ 추천

### 장점: 
- Git 연동 자동 배포
- HTTPS 자동 설정
- 환경변수 관리 쉬움

### 배포 단계:

1. **AWS Amplify 콘솔 접속**
   ```
   https://console.aws.amazon.com/amplify/
   ```

2. **새 앱 생성**
   - "New app" → "Host web app" 클릭
   - GitHub/GitLab/Bitbucket 연결
   - Repository와 Branch 선택

3. **빌드 설정 확인**
   ```yaml
   version: 1
   frontend:
     phases:
       preBuild:
         commands:
           - npm ci
       build:
         commands:
           - npm run build
     artifacts:
       baseDirectory: .next
       files:
         - '**/*'
     cache:
       paths:
         - node_modules/**/*
   ```

4. **환경변수 설정**
   - App settings → Environment variables
   - 추가할 변수:
   ```
   NEXT_PUBLIC_API_URL = http://백엔드-서버-주소:8000/api/v1
   ```

5. **배포**
   - "Save and deploy" 클릭
   - 약 5-10분 대기

6. **도메인 확인**
   - 배포 완료 후 제공되는 URL로 접속
   - 예: `https://main.d1234567890abc.amplifyapp.com`

---

## 옵션 2: AWS EC2 (직접 제어)

### 배포 단계:

1. **EC2 인스턴스 생성**
   ```bash
   # AWS 콘솔에서
   - AMI: Amazon Linux 2 or Ubuntu 22.04
   - Instance type: t2.micro (프리티어) 또는 t3.medium
   - Security Group: 포트 3000, 22 열기
   ```

2. **EC2 접속 및 환경 설정**
   ```bash
   # SSH 접속
   ssh -i your-key.pem ec2-user@ec2-xx-xxx-xxx-xxx.compute.amazonaws.com
   
   # Node.js 설치
   curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
   sudo yum install -y nodejs
   
   # Git 설치
   sudo yum install -y git
   
   # PM2 설치 (프로세스 관리)
   sudo npm install -g pm2
   ```

3. **프로젝트 클론 및 설정**
   ```bash
   # 프로젝트 클론
   git clone https://github.com/your-repo/DDF-MSTGCN.git
   cd DDF-MSTGCN/frontend
   
   # 의존성 설치
   npm install
   
   # 환경변수 설정
   echo "NEXT_PUBLIC_API_URL=http://백엔드-서버:8000/api/v1" > .env.production
   ```

4. **빌드 및 실행**
   ```bash
   # 프로덕션 빌드
   npm run build
   
   # PM2로 실행
   pm2 start npm --name "ddf-frontend" -- start
   
   # PM2 자동 시작 설정
   pm2 startup
   pm2 save
   ```

5. **Nginx 설정 (선택사항 - 포트 80 사용시)**
   ```bash
   sudo yum install -y nginx
   
   # /etc/nginx/nginx.conf 수정
   sudo vi /etc/nginx/nginx.conf
   ```
   
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

---

## 옵션 3: AWS S3 + CloudFront (정적 배포)

### 주의: Next.js SSR 기능 사용 불가

1. **정적 빌드 설정**
   ```bash
   # package.json 수정
   "scripts": {
     "build": "next build",
     "export": "next export"
   }
   ```

2. **빌드 및 Export**
   ```bash
   npm run build
   npm run export
   ```

3. **S3 버킷 생성**
   - S3 콘솔에서 버킷 생성
   - Static website hosting 활성화
   - Bucket policy 설정 (public read)

4. **파일 업로드**
   ```bash
   aws s3 sync out/ s3://your-bucket-name --acl public-read
   ```

5. **CloudFront 설정**
   - Distribution 생성
   - Origin: S3 버킷
   - Default root object: index.html

---

## 옵션 4: Vercel (Next.js 공식 추천) 🚀

### 가장 쉽고 빠른 방법

1. **Vercel 가입**
   ```
   https://vercel.com
   ```

2. **GitHub 연동**
   - Import Git Repository
   - Repository 선택

3. **프로젝트 설정**
   - Framework Preset: Next.js (자동 감지)
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

4. **환경변수 설정**
   ```
   NEXT_PUBLIC_API_URL = https://your-backend-api.com/api/v1
   ```

5. **Deploy 클릭**

---

## 배포 후 확인사항

1. **기능 테스트**
   ```javascript
   // 브라우저 콘솔에서
   console.log(process.env.NEXT_PUBLIC_API_URL);
   // 올바른 API URL 출력되는지 확인
   ```

2. **네트워크 확인**
   - 개발자 도구 → Network 탭
   - API 호출이 올바른 주소로 가는지 확인

3. **CORS 에러 확인**
   - 에러 발생시 백엔드 CORS 설정 수정 필요

---

## 백엔드 서버 CORS 수정 (필수!)

백엔드 서버에서 다음 파일 수정:

```python
# backend/app/core/config.py

ALLOWED_HOSTS: List[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://main.d1234567890abc.amplifyapp.com",  # Amplify URL
    "https://your-app.vercel.app",  # Vercel URL
    "http://ec2-xx-xxx-xxx-xxx.compute.amazonaws.com:3000",  # EC2 URL
    # 배포한 프론트엔드 URL 추가
]
```

백엔드 서버 재시작:
```bash
# 백엔드 서버에서
sudo systemctl restart your-backend-service
# 또는
pm2 restart backend
```

---

## 문제 해결

### 1. "Failed to fetch" 에러
- 백엔드 서버 실행 확인
- Security Group/방화벽 포트 확인
- CORS 설정 확인

### 2. 환경변수 인식 안됨
- 변수명이 `NEXT_PUBLIC_`로 시작하는지 확인
- 빌드 시점에 환경변수 설정되었는지 확인
- 재빌드 필요: `npm run build`

### 3. 페이지 로딩 안됨
- 빌드 에러 확인: `npm run build`
- Node.js 버전 확인 (18.x 이상 권장)

---

## 추천 배포 순서

1. **초보자**: Vercel → AWS Amplify → EC2
2. **비용 효율**: EC2 (프리티어) → S3+CloudFront → Amplify
3. **속도**: Vercel → Amplify → S3+CloudFront

## 현재 상황에 맞는 추천

백엔드가 이미 AWS에 있다면:
→ **AWS Amplify** 사용 (같은 리전 선택)

빠르게 테스트하고 싶다면:
→ **Vercel** 사용 (5분 내 배포 완료)

비용을 최소화하고 싶다면:
→ **EC2 프리티어** 사용