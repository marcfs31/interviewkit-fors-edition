### Security

- Google and GitHub sign-in now only use an email address the provider has verified; an unverified address can no longer be used to reach or take over an existing account.
- The sign-in exchange code can now be used only once, so a leaked code cannot be replayed to obtain new access tokens.

### Fixed

- Emails are now treated case-insensitively at registration, login and social sign-in, so `A@x.com` and `a@x.com` are the same account.
