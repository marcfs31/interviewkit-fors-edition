### Security
- The API now accepts the access token only from the `Authorization` header and no longer sets an auth cookie, closing a CSRF hole where a cross-site form POST could, for example, force-complete a victim's session.

### Changed
- **BREAKING:** users whose only session is a pre-#84 auth cookie must log in again; the API ignores the access cookie. `POST /auth/logout` still returns 200 but only the client drops its token (no server-side revocation).
