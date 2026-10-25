/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    // Keep heavy markdown/highlight deps out of the client bundle where possible.
    optimizePackageImports: ['lucide-react', 'date-fns'],
    // Middleware runs on every route and buffers request bodies only up to
    // 10 MB by default, which would cut off larger PDF uploads to the admin
    // documents page. 64 MB matches the gateway's client_max_body_size.
    middlewareClientMaxBodySize: '64mb',
  },
  serverExternalPackages: ['bcryptjs', '@prisma/client'],
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'DENY' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ]
  },
}

export default nextConfig
