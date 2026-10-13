### Fixed

- Registering or logging in with a password over 72 bytes, or a name or email longer than its column, now returns a clear 400 instead of a server error.
- Cards with malformed tags (nested lists, objects, more than 10, or longer than 40 characters) or oversized text fields are rejected with a 400, and previously stored bad tags no longer break the stats page.
- Request bodies over 64 KiB, and JSON bodies that are not an object, now get a JSON 413 or 400 instead of an error page.
