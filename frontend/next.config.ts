import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  
  // Standalone output for Docker deployment
  output: 'standalone',
  
  // 환경변수를 클라이언트에서 사용 가능하도록 설정
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  
  // 이미지 도메인 허용 (필요시)
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
  
  // 청크 로딩 문제 해결을 위한 webpack 설정
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }
    return config;
  },
  
  
  // CORS는 Nginx에서 처리하므로 Next.js에서는 불필요
};

export default nextConfig;
