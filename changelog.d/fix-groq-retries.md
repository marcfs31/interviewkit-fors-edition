### Fixed
- Groq errors (rate limit, 5xx, connection) are no longer retried silently by the SDK, so a failing request now answers in at most 40 s instead of risking the 120 s worker timeout.
- Creating a session and grading an answer no longer hold a database transaction open while waiting for the AI.
