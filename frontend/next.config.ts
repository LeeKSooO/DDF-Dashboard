import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  
  // 환경변수를 클라이언트에서 사용 가능하도록 설정
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  
  // 이미지 도메인 허용 (필요시)
  images: {
    domains: ['localhost'],
  },
  
  // 프로덕션 빌드 최적화
  swcMinify: true,
  
  // CORS 및 헤더 설정
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Access-Control-Allow-Credentials', value: 'true' },
          { key: 'Access-Control-Allow-Origin', value: '*' },
          { key: 'Access-Control-Allow-Methods', value: 'GET,OPTIONS,PATCH,DELETE,POST,PUT' },
          { key: 'Access-Control-Allow-Headers', value: 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version' },
        ],
      },
    ];
  },
};

export default nextConfig;
