# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Entries accumulate as fragments in [`changelog.d/`](changelog.d/README.md), one file per pull
request, until the next release. The `chore(release): X.Y.Z` commit compiles them into this file.

## [0.2.0] - 2026-10-13

Hardening release from the full-repo audit: security fixes, data-integrity fixes, accessibility, CI gates and supply chain.

### Added

- Automated axe accessibility checks run in the frontend test suite.
- `RATELIMIT_STORAGE_URI` setting for the rate limiter storage (defaults to `memory://`; production logs a warning that limits are then per process and reset on restart).

### Changed

- **BREAKING:** The frontend now runs on Next.js 16 (Turbopack builds, Node 20.9 or newer required); linting uses the ESLint CLI with a native flat config instead of `next lint`.
- **BREAKING:** `SECRET_KEY` is now required in every environment (no fallback to `JWT_SECRET_KEY`); production deployments must set `SECRET_KEY` and `FRONTEND_URL`.
- **BREAKING:** users whose only session is a pre-#84 auth cookie must log in again; the API ignores the access cookie. `POST /auth/logout` still returns 200 but only the client drops its token (no server-side revocation).
- The platform health check now calls `/health` every 30 s, so a machine that cannot reach the database stops receiving traffic.
- CI runs once per pull request and adds a single required `results` gate, a frontend build, `ruff format --check`, an Alembic upgrade/downgrade/check round trip on PostgreSQL 16 and a check that every manifest carries the same version.

### Fixed

- Keyboard and screen-reader users can now reach the main content from the skip link, leave the code editor with Esc then Tab, and hear form labels, tag fields, toggle states and username errors announced correctly.
- The navigation bar uses real links and marks the current page, and the session setup moves focus to each new step.
- A grading the AI returns without a valid result, feedback or card is now rejected with a retryable error instead of being saved as "partially correct" (50 XP) with canned feedback.
- A new session is no longer padded with generic "closures" or "array" questions when the AI returns too few: it fails and can be retried, so every question matches the chosen stack.
- Blank or non-text answers are rejected before reaching the AI, and resubmitting an answer clears its previous grade, so a failed re-grade can no longer earn XP for the old one.
- API requests now time out (15 s, 60 s for AI calls) instead of spinning forever when the server hangs.
- Timeouts and connection failures show a clear Spanish message instead of the raw browser error ("Failed to fetch").
- The stacks list now goes through the shared API client, so it gets the shared error handling and timeouts.
- Completing a session twice at once, or two sessions at the same time, can no longer award XP twice or lose one of the awards.
- Answering a question of an already completed session is now rejected with a 409.
- A failed or interrupted session creation no longer leaves an empty session that counts in your stats.
- Editing a card with a partial update no longer erases its code, code language or mnemonic when those fields are not sent.
- Typing in the code editor no longer reverts a recent edit to another card field (such as "Concepto") that had not been saved yet.
- Groq errors (rate limit, 5xx, connection) are no longer retried silently by the SDK, so a failing request now answers in at most 40 s instead of risking the 120 s worker timeout.
- Creating a session and grading an answer no longer hold a database transaction open while waiting for the AI.
- Registering or logging in with a password over 72 bytes, or a name or email longer than its column, now returns a clear 400 instead of a server error.
- Cards with malformed tags (nested lists, objects, more than 10, or longer than 40 characters) or oversized text fields are rejected with a 400, and previously stored bad tags no longer break the stats page.
- Request bodies over 64 KiB, and JSON bodies that are not an object, now get a JSON 413 or 400 instead of an error page.
- Emails are now treated case-insensitively at registration, login and social sign-in, so `A@x.com` and `a@x.com` are the same account.
- Database downgrades no longer fail with raw Postgres errors on real data: reverting the OAuth migration now stops with a clear message if OAuth-only users exist (nothing is changed or deleted), and reverting the card migration keeps question, answer and feedback as unlimited text instead of failing on values longer than 500 characters.
- Stats, Profile and the navbar XP chip no longer show invented numbers ("Nv 1 · 0 XP") when your stats cannot be loaded; they show a loading state, then an error with a "Reintentar" button.
- If a finished session cannot be scored, the completion screen now shows "No se pudo calcular tu XP." with a retry button instead of a made-up 0 XP result.
- A failed card save keeps you on the feedback screen with your edits and an error message, instead of sending you back to the question and re-running the AI correction.

### Security

- The backend container now runs as a non-root user, its base image is pinned by digest, and it no longer ships the test dependencies or the test suite.
- Upgrading Next.js clears every advisory reported by `npm audit --omit=dev` (Next.js, PostCSS, sharp, nanoid and source-map-js).
- The frontend now sends a Content-Security-Policy (`default-src 'self'`, `connect-src` limited to itself and the API origin, no `unsafe-eval` in production, `object-src` and `frame-ancestors` set to `'none'`) plus `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy` and HSTS on every page. `'unsafe-inline'` scripts are kept so that pages stay statically prerendered.
- A production build or start now fails with a clear message when `NEXT_PUBLIC_API_URL` is missing or not an absolute http(s) URL, instead of shipping an unusable or permissive policy.
- Every API response now carries `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, `X-Frame-Options` and a closed `Content-Security-Policy`, and `Strict-Transport-Security` in production.
- Rate-limit `POST /auth/login` (10/min, 50/h), `POST /auth/register` (5/h) and `POST /auth/oauth/exchange` (20/min) per client IP, to slow down credential stuffing and mass sign-ups.
- Cap each account at 20 AI requests per day (session creation and answers combined), so one user can no longer exhaust the shared 40-per-day Groq budget.
- Updated backend dependencies with known vulnerabilities: Authlib, PyJWT, cryptography, requests, urllib3, Werkzeug and anyio.
- The backend now refuses to start unless `FLASK_ENV` is `development`, `test` or `production`, `SECRET_KEY` is set, and, in production, both secrets are distinct and at least 32 characters long and `FRONTEND_URL` is set.
- The `/debug` endpoints are only registered in development and test, and no longer return exception text to the client.
- The API now accepts the access token only from the `Authorization` header and no longer sets an auth cookie, closing a CSRF hole where a cross-site form POST could, for example, force-complete a victim's session.
- Google and GitHub sign-in now only use an email address the provider has verified; an unverified address can no longer be used to reach or take over an existing account.
- The sign-in exchange code can now be used only once, so a leaked code cannot be replayed to obtain new access tokens.
- CI actions are pinned to full commit SHAs on their Node 24 majors; Dependabot (daily, with cooldowns), CodeQL and a gitleaks secret scan now run on the repository.

## [0.1.0] - 2026-10-13

First versioned release, summarising the app as of PR #89.

### Added

- Interview sessions: the AI generates 5 questions (2 theory + 3 code) for a role, technology, topic and level, and gives feedback on every answer.
- Study cards created from the questions, with a dashboard to search and filter them.
- XP and levels earned per session, and a statistics page with results, most practised stacks and recent sessions.
- Sign in with email and password, Google or GitHub (OAuth that works with third-party cookies blocked), plus light and dark themes.
- AI call observability: one metadata-only `ai_call` row per Groq call, configurable logging (`LOG_LEVEL`), opt-in Sentry (`SENTRY_DSN`) and a public `GET /health` liveness and database check.

[Unreleased]: https://github.com/marcfs31/interviewkit-fors-edition/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/marcfs31/interviewkit-fors-edition/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/marcfs31/interviewkit-fors-edition/releases/tag/v0.1.0
