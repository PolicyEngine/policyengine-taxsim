/**
 * Base path utilities for the TAXSIM dashboard.
 *
 * The app is deployed standalone on Vercel and also embedded at
 * policyengine.org/us/taxsim/ via a Vercel rewrite. We detect the
 * context at runtime so asset URLs and internal links work in both.
 */

const APP_PREFIX = '/us/taxsim';

function getBasePath() {
  if (typeof window !== 'undefined') {
    if (window.location.pathname.startsWith(APP_PREFIX)) {
      return APP_PREFIX;
    }
  }
  return '';
}

/** Prefix a public asset path (e.g. /data/2024/results.csv) */
export function assetUrl(path) {
  const base = getBasePath();
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${base}${clean}`;
}

/** Prefix an internal route path for Link href (e.g. /documentation) */
export function linkUrl(path) {
  const base = getBasePath();
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${base}${clean}`;
}
