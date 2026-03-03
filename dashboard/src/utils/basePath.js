/**
 * Returns the base path for the app. In Next.js this comes from the config.
 * Used by data loaders to construct URLs for public/ assets.
 */
export const BASE_PATH = '/us/taxsim';

export function assetUrl(path) {
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${BASE_PATH}${clean}`;
}
