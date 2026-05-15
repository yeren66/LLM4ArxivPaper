/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // We don't need image optimisation; pictures come from arxiv directly.
  images: { unoptimized: true },
};
module.exports = nextConfig;
