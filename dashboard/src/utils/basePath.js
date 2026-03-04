/**
 * Base path utilities for the TAXSIM dashboard.
 *
 * The app is deployed standalone on Vercel and also embedded at
 * policyengine.org/us/taxsim/ via a Vercel rewrite. We detect the
 * context at runtime so asset URLs and internal links work in both.
 */

const APP_PREFIX = '/us/taxsim';

let cachedBasePath = null;

function getBasePath() {
  if (cachedBasePath !== null) return cachedBasePath;
  if (typeof window !== 'undefined') {
    cachedBasePath = window.location.pathname.startsWith(APP_PREFIX)
      ? APP_PREFIX
      : '';
  } else {
    return '';
  }
  return cachedBasePath;
}

/** Prefix a path with the runtime base path (assets or internal routes) */
export function prefixPath(path) {
  const base = getBasePath();
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${base}${clean}`;
}

/** Prefix a public asset path (e.g. /data/2024/results.csv) */
export const assetUrl = prefixPath;

/** Prefix an internal route path for Link href (e.g. /documentation) */
export const linkUrl = prefixPath;
