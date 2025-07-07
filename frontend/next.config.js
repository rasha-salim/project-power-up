/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // Enable image optimization for server-side rendering
  images: {
    domains: ['localhost', 'project-power-up-production.up.railway.app'],
  }
  
  // Note: API rewrites removed - using direct API calls via NEXT_PUBLIC_API_URL
  // This prevents hardcoded localhost URLs that would cause Mixed Content errors in production
};

module.exports = nextConfig;
