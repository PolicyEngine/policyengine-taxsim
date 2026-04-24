const configuredBasePath = process.env.NEXT_PUBLIC_BASE_PATH;
const basePath =
  configuredBasePath === '' ? undefined : configuredBasePath || '/us/taxsim';
const publicBasePath = configuredBasePath === '' ? '' : basePath || '';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  ...(basePath ? { basePath } : {}),
  env: {
    NEXT_PUBLIC_BASE_PATH: publicBasePath,
  },
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
};

export default nextConfig;
