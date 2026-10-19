/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Lets a second build (e.g. the E2E build against another API URL) coexist with a running one.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  experimental: {
    serverActions: { allowedOrigins: ['localhost:3000'] },
  },
  images: {
    remotePatterns: [{ protocol: 'https', hostname: '**.gov.in' }],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV || 'development',
  },
}

module.exports = nextConfig
