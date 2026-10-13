### Security
- The backend now refuses to start unless `FLASK_ENV` is `development`, `test` or `production`, `SECRET_KEY` is set, and, in production, both secrets are distinct and at least 32 characters long and `FRONTEND_URL` is set.
- The `/debug` endpoints are only registered in development and test, and no longer return exception text to the client.

### Changed
- **BREAKING:** `SECRET_KEY` is now required in every environment (no fallback to `JWT_SECRET_KEY`); production deployments must set `SECRET_KEY` and `FRONTEND_URL`.
