/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath: '/us/taxsim',
  output: 'export',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
};

export default nextConfig;
