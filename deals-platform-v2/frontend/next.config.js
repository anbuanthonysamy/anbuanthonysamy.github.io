/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig = {
  reactStrictMode: true,
  experimental: { typedRoutes: false },
  typescript: {
    ignoreBuildErrors: true,
  },
  ...(staticExport
    ? {
        output: "export",
        basePath: "/deals-platform",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
};

module.exports = nextConfig;
