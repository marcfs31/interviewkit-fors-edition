# InterviewKit — AGENTS.md

Flask + SQLAlchemy + Alembic API (`backend/`) and Next.js 15 App Router client (`frontend/`).
UI copy and API error messages are Spanish; code comments are English. Setup, env vars and API
table: `README.md`. Workflow and PR rules: `CONTRIBUTING.md`. Every rule below names the incident
that created it (PR numbers and short SHAs are in `git log`).

## Non-negotiables

1. **The frontend authenticates with a Bearer token in `localStorage` (`access_token`); no flow may
   depend on the API-domain cookie.** OAuth broke under third-party-cookie blocking (#84), so the
   callback redirects with a signed 60 s one-time code in the URL fragment and the frontend swaps it at
   `POST /auth/oauth/exchange`. The token itself never goes in a URL.
2. **Groq is called only through `_call_groq` in `services/ai_service.py`**, which raises typed errors
   and writes one `ai_call` row per real call (#88, #89). A Groq failure propagates as
   `AIUnavailableError`; never return a fake correction or fabricated questions (#88).
3. **`ai_call` stores metadata only**: never question text, answers or feedback (GDPR). `session_id`
   is deliberately not a foreign key (`create_session` deletes the session when the AI fails).
4. **User answers reach the model only inside the `###ANSWER_START###` / `###ANSWER_END###` delimiters**,
   neutralised and length-capped (#88).
5. **`typescript` and `@types/*` stay in `dependencies`**: Vercel skips devDependencies in the build
   (9283c34).
6. **`frontend/package-lock.json` comes from Node 22 / npm 10** (`.nvmrc`); a lockfile from another
   npm fails CI (90a4f60, e3b0f11).
7. **A schema change ships with its Alembic migration**; `fly deploy` runs `flask db upgrade` as the
   `release_command`.
8. **`/health` is public, exempt from rate limits and reveals no internals** (#89). It does return the
   deployed `version`.
9. **No secrets in the tree**; new env vars go into the `.env.example` of that side.

## Gate (identical to `.github/workflows/ci.yml`)

```bash
cd backend && ruff check . && pytest --cov=app --cov-report=term-missing --cov-fail-under=85
cd frontend && npm ci && npx tsc --noEmit && npm run lint && npm test
```

Backend tests use in-memory SQLite and a mocked Groq client; no keys needed. Coverage is 95 % today
and only ratchets up. Do not run `ruff format` on whole files (a separate PR formats the codebase).
Merge method and required checks: read them with `gh api repos/marcfs31/interviewkit-fors-edition`.

## Release

SemVer. One version, identical in `backend/app/version.py` and `frontend/package.json` (plus the top
of `package-lock.json`). Each PR adds one fragment `changelog.d/<branch-slug>.md` (Keep a Changelog
headings); the `chore(release): X.Y.Z` commit compiles the fragments into `CHANGELOG.md`, deletes
them and bumps both versions. Pre-1.0 a breaking change bumps the minor, a fix the patch. Tag
`vX.Y.Z` on the merged main commit.

## Where to edit

| Need | Place | Not |
|---|---|---|
| A new endpoint | `backend/app/routes/<area>.py`, registered in `create_app` | logic inside `create_app` |
| Business rules, XP, stacks | `backend/app/services/`, `backend/app/constants/` | route handlers |
| A Groq prompt or call | `backend/app/services/ai_service.py` | a second `groq` client elsewhere |
| A column or table | `backend/app/models/` + `flask db migrate` + committed `migrations/versions/` | editing an applied migration |
| An env var | `backend/app/config.py` + `backend/.env.example` + README table | reading `os.environ` in routes |
| An API call from the UI | `frontend/src/services/*Service.ts` on top of `httpClient.ts` | `fetch` in components |
| Auth headers, 401 handling | `frontend/src/services/httpClient.ts` | per-service copies |
| Session flow state | `frontend/src/reducers/sessionReducer.ts` | ad-hoc `useState` chains |
| Pages and routes | `frontend/app/(app)/` | `frontend/src/` |
| Components and colours | `frontend/src/components/`, theme tokens | hardcoded hex (breaks light/dark) |

## Out of scope unless asked

- Framework majors, changing the AI provider or model, or schema changes outside the item at hand.
- `.github/**`, `fly.toml` and deploys (`fly deploy`, Vercel) from a session.
- Documenting env vars or endpoints that do not exist yet.

## Before you finish

- [ ] Gate ran; the command and its real output are in the PR body.
- [ ] Bug fix: a test that failed on the old code and passes now, at the narrowest layer.
- [ ] Every validation or heuristic has a negative test.
- [ ] Behaviour changed: `changelog.d/<branch-slug>.md` added; README/CONTRIBUTING updated if affected.
- [ ] User-facing strings and API errors in Spanish; no new runtime dependency without a reason.
- [ ] This file updated if the session revealed a rule a future session would otherwise relearn.
