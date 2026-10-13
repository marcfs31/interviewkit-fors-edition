### Security
- The backend container now runs as a non-root user, its base image is pinned by digest, and it no longer ships the test dependencies or the test suite.

### Changed
- The platform health check now calls `/health` every 30 s, so a machine that cannot reach the database stops receiving traffic.
