### Fixed
- API requests now time out (15 s, 60 s for AI calls) instead of spinning forever when the server hangs.
- Timeouts and connection failures show a clear Spanish message instead of the raw browser error ("Failed to fetch").
- The stacks list now goes through the shared API client, so it sends credentials and gets the shared 401 handling.
