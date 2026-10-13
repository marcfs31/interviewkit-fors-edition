### Changed
- **BREAKING:** The frontend now runs on Next.js 16 (Turbopack builds, Node 20.9 or newer required); linting uses the ESLint CLI with a native flat config instead of `next lint`.

### Security
- Upgrading Next.js clears every advisory reported by `npm audit --omit=dev` (Next.js, PostCSS, sharp, nanoid and source-map-js).
