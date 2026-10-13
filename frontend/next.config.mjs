import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";
import { buildSecurityHeaders } from "./src/lib/securityHeaders.mjs";

/** @param {string} phase */
export default function nextConfig(phase) {
  const isDev = phase === PHASE_DEVELOPMENT_SERVER;
  // Evaluated at config load: a production build or start with a missing or
  // malformed NEXT_PUBLIC_API_URL fails here instead of shipping a bad policy.
  const securityHeaders = buildSecurityHeaders({ apiUrl: process.env.NEXT_PUBLIC_API_URL, isDev });

  return {
    reactStrictMode: true,
    async headers() {
      return [{ source: "/(.*)", headers: securityHeaders }];
    },
  };
}
