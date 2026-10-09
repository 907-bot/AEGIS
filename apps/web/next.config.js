/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',       // Standalone output for Docker
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL:  process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_GATEWAY_URL: process.env.NEXT_PUBLIC_GATEWAY_URL,
  },
};

module.exports = nextConfig;
