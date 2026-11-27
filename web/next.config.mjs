/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Runtime copies only .next/standalone, not the whole node_modules.
  output: 'standalone',
  // next/image is never used (model output links to arbitrary hosts, which
  // it cannot optimise anyway; see components/markdown/markdown.tsx), but
  // Next still traces its optimizer and sharp's native binaries into the
  // standalone output unless told not to.
  outputFileTracingExcludes: {
    '*': ['node_modules/sharp/**', 'node_modules/@img/**'],
  },
  experimental: {
    // Keep heavy markdown/highlight deps out of the client bundle where possible.
    optimizePackageImports: ['lucide-react', 'date-fns'],
    // Proxy runs on every route and buffers request bodies only up to
    // 10 MB by default, which would cut off larger PDF uploads to the admin
    // documents page. 64 MB matches the gateway's client_max_body_size.
    proxyClientMaxBodySize: '64mb',
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
          // Sign-in providers redirect the whole page rather than opening a
          // popup, so no other window needs a handle on this one.
          { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
          { key: 'Cross-Origin-Resource-Policy', value: 'same-origin' },
          // No Cross-Origin-Embedder-Policy: require-corp would block GitHub
          // avatars, which send no CORP header, and nothing here needs
          // cross-origin isolation. The CSP is set per request in middleware.ts.
        ],
      },
    ]
  },
}

export default nextConfig
