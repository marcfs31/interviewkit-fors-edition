# Changelog fragments

Every pull request that changes behaviour adds **one** file here, named after its branch:
`changelog.d/<branch-slug>.md` (for example `changelog.d/fix-cards-partial-patch.md`).

Write it with [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) headings and one to three
user-facing bullets in English:

```markdown
### Fixed

- Editing one field of a card no longer clears the others.
```

Allowed headings: `### Added`, `### Changed`, `### Fixed`, `### Security`, `### Removed`.
Put a breaking change under `### Changed` and prefix it with `**BREAKING:**`.

Fragments are not edited after merge. The `chore(release): X.Y.Z` commit compiles them into
`CHANGELOG.md` under the new version heading, deletes them (this README stays) and bumps the version
in `backend/app/version.py` and `frontend/package.json`.
