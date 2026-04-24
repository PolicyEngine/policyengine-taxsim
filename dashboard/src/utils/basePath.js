/**
 * Base path utilities for the TAXSIM dashboard.
 *
 * The basePath is set in next.config.mjs and handles _next assets and
 * Link hrefs automatically. These helpers are for custom fetch calls
 * to public data files (e.g. /data/2024/results.csv).
 */

const BASE_PATH =
  process.env.NEXT_PUBLIC_BASE_PATH !== undefined
    ? process.env.NEXT_PUBLIC_BASE_PATH
    : '/us/taxsim';

/** Prefix a public asset path (e.g. /data/2024/results.csv) */
export function assetUrl(path) {
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${BASE_PATH}${clean}`;
}
