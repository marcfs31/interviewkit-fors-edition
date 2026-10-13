// Pure builder for the security headers next.config.mjs sends on every route.
// Plain .mjs because the config file is loaded by Node before any TS tooling runs.

/**
 * Reduces the configured API URL to its origin. Throws on anything that is not
 * an absolute http(s) URL: a CSP built from a bad value must never ship.
 * @param {string | undefined} apiUrl
 * @returns {string}
 */
function parseApiOrigin(apiUrl) {
  const fail = (detail) =>
    new Error(`NEXT_PUBLIC_API_URL ${detail}; it sets the CSP connect-src and has no safe fallback.`);
  if (typeof apiUrl !== "string" || apiUrl.trim() === "") throw fail("is missing or empty");
  let url;
  try {
    url = new URL(apiUrl.trim());
  } catch {
    throw fail(`is not an absolute URL (got "${apiUrl}")`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw fail(`must use http or https (got "${apiUrl}")`);
  }
  return url.origin;
}

/**
 * @param {{ apiUrl?: string, isDev?: boolean }} options
 * @returns {{ key: string, value: string }[]}
 */
export function buildSecurityHeaders({ apiUrl, isDev = false }) {
  // Missing is only tolerated in dev (connect-src then stays 'self'); a value
  // that is present but malformed always throws.
  const apiOrigin = isDev && (apiUrl === undefined || apiUrl.trim() === "") ? null : parseApiOrigin(apiUrl);

  const connectSrc = ["'self'", ...(apiOrigin ? [apiOrigin] : []), ...(isDev ? ["ws:"] : [])];
  // Pages are static, so Next's inline bootstrap scripts and the theme script
  // cannot carry a per-request nonce: 'unsafe-inline' is the price of that.
  const scriptSrc = ["'self'", "'unsafe-inline'", ...(isDev ? ["'unsafe-eval'"] : [])];

  const csp = [
    "default-src 'self'",
    `script-src ${scriptSrc.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src ${connectSrc.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  return [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]),
  ];
}
