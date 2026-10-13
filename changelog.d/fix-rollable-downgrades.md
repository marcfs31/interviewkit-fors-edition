### Fixed
- Database downgrades no longer fail with raw Postgres errors on real data: reverting the OAuth migration now stops with a clear message if OAuth-only users exist (nothing is changed or deleted), and reverting the card migration keeps question, answer and feedback as unlimited text instead of failing on values longer than 500 characters.
