### Security
- The frontend now sends a Content-Security-Policy (`default-src 'self'`, `connect-src` limited to itself and the API origin, no `unsafe-eval` in production, `object-src` and `frame-ancestors` set to `'none'`) plus `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy` and HSTS on every page. `'unsafe-inline'` scripts are kept so that pages stay statically prerendered.
- A production build or start now fails with a clear message when `NEXT_PUBLIC_API_URL` is missing or not an absolute http(s) URL, instead of shipping an unusable or permissive policy.
- Every API response now carries `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, `X-Frame-Options` and a closed `Content-Security-Policy`, and `Strict-Transport-Security` in production.
