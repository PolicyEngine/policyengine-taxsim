/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath: '/us/taxsim',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
};

export default nextConfig;
