### Security
- Rate-limit `POST /auth/login` (10/min, 50/h), `POST /auth/register` (5/h) and `POST /auth/oauth/exchange` (20/min) per client IP, to slow down credential stuffing and mass sign-ups.
- Cap each account at 20 AI requests per day (session creation and answers combined), so one user can no longer exhaust the shared 40-per-day Groq budget.

### Added
- `RATELIMIT_STORAGE_URI` setting for the rate limiter storage (defaults to `memory://`; production logs a warning that limits are then per process and reset on restart).
