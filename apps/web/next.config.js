/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',           // Static export for GitHub Pages
  trailingSlash: true,
  images: { unoptimized: true },
  basePath: '/AEGIS',      // Required for GitHub Pages subfolder deployment
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL:  process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_GATEWAY_URL: process.env.NEXT_PUBLIC_GATEWAY_URL,
  },
};

module.exports = nextConfig;
