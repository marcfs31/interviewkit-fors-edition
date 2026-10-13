# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Entries accumulate as fragments in [`changelog.d/`](changelog.d/README.md), one file per pull
request, until the next release. The `chore(release): X.Y.Z` commit compiles them into this file.

## [0.1.0] - 2026-10-13

First versioned release, summarising the app as of PR #89.

### Added

- Interview sessions: the AI generates 5 questions (2 theory + 3 code) for a role, technology, topic and level, and gives feedback on every answer.
- Study cards created from the questions, with a dashboard to search and filter them.
- XP and levels earned per session, and a statistics page with results, most practised stacks and recent sessions.
- Sign in with email and password, Google or GitHub (OAuth that works with third-party cookies blocked), plus light and dark themes.
- AI call observability: one metadata-only `ai_call` row per Groq call, configurable logging (`LOG_LEVEL`), opt-in Sentry (`SENTRY_DSN`) and a public `GET /health` liveness and database check.

[Unreleased]: https://github.com/marcfs31/interviewkit-fors-edition/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/marcfs31/interviewkit-fors-edition/releases/tag/v0.1.0
