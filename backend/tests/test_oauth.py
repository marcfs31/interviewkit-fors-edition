"""
Tests for app/routes/oauth.py: the _get_or_create_user helper (the core
account-linking logic for Google/GitHub login), _build_login_response, and
the four HTTP routes (/auth/google, /auth/google/callback, /auth/github,
/auth/github/callback).

The real oauth.google / oauth.github clients are never hit: the Authlib
`oauth` object is patched with unittest.mock so these tests run offline and
deterministically.
"""
from unittest.mock import patch, MagicMock

from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.routes.oauth import _get_or_create_user, _build_login_response


class TestGetOrCreateUser:
    def test_creates_new_user_and_link(self, app, db):
        with app.app_context():
            user = _get_or_create_user(
                provider="google", provider_user_id="12345",
                email="new@example.com", name="New User",
            )
            assert user is not None
            assert user.name == "New User"
            assert user.email == "new@example.com"

            link = OAuthAccount.query.filter_by(provider="google", provider_user_id="12345").first()
            assert link is not None
            assert link.user_id == user.user_id

    def test_returns_existing_user_by_oauth_link(self, app, db):
        with app.app_context():
            first = _get_or_create_user("google", "abc", "first@example.com", "First")
            second = _get_or_create_user("google", "abc", "different@example.com", "Different")
            assert second.user_id == first.user_id

    def test_does_not_auto_link_existing_email_without_prior_oauth_link(self, app, db):
        """Security: an email that already has a password account must NOT
        be silently linked to a new OAuth login without a prior OAuthAccount
        row -- otherwise anyone could take over an existing account just by
        knowing its email and signing in with Google/GitHub."""
        with app.app_context():
            existing = User(name="Existing", email="existing@example.com")
            db.session.add(existing)
            db.session.commit()

            user = _get_or_create_user(
                provider="github", provider_user_id="gh_123",
                email="existing@example.com", name="Should Not Change",
            )
            assert user is None

            link = OAuthAccount.query.filter_by(provider="github", provider_user_id="gh_123").first()
            assert link is None

    def test_handles_orphan_oauth_account(self, app, db):
        """An OAuthAccount whose user_id no longer points to a real User
        (e.g. the user row was deleted) must be cleaned up and a fresh user
        created, instead of crashing on User.query.get(None-ish)."""
        with app.app_context():
            orphan = OAuthAccount(provider="google", provider_user_id="orphan", user_id=9999)
            db.session.add(orphan)
            db.session.commit()

            user = _get_or_create_user(
                provider="google", provider_user_id="orphan",
                email="orphan@example.com", name="Orphan User",
            )
            assert user is not None
            assert user.email == "orphan@example.com"

    def test_provider_user_id_unique_per_provider(self, app, db):
        """The same provider_user_id string can exist once for google and
        once for github without colliding (they're scoped per-provider)."""
        with app.app_context():
            _get_or_create_user("google", "same_id", "a@example.com", "A")
            _get_or_create_user("github", "same_id", "b@example.com", "B")

            assert OAuthAccount.query.filter_by(provider="google", provider_user_id="same_id").count() == 1
            assert OAuthAccount.query.filter_by(provider="github", provider_user_id="same_id").count() == 1

    def test_calling_twice_with_same_identity_is_idempotent(self, app, db):
        with app.app_context():
            first = _get_or_create_user("google", "race", "race@example.com", "Race")
            second = _get_or_create_user("google", "race", "race@example.com", "Race")
            assert second.user_id == first.user_id

    def test_fallback_email_is_stored_as_is(self, app, db):
        with app.app_context():
            user = _get_or_create_user(
                provider="google", provider_user_id="no_email",
                email="google_no_email@users.noreply.google.com", name="No Email",
            )
            assert user.email == "google_no_email@users.noreply.google.com"

    def test_different_provider_user_id_creates_a_different_account(self, app, db):
        with app.app_context():
            fallback_email = "google_old@users.noreply.google.com"
            user1 = _get_or_create_user("google", "old_id", fallback_email, "Old")
            user2 = _get_or_create_user("google", "new_id", "real@example.com", "Real")
            assert user2.user_id != user1.user_id


class TestBuildLoginResponse:
    def test_sets_no_auth_cookie(self, app, db):
        with app.app_context():
            user = User(name="Test", email="test@example.com")
            db.session.add(user)
            db.session.commit()

            resp = _build_login_response(user)
            assert resp.status_code == 302
            assert "access_token_cookie" not in resp.headers.get("Set-Cookie", "")

    def test_redirect_carries_exchange_code_not_the_jwt(self, app, db):
        """The redirect URL must never contain the JWT itself (browser history,
        logs, Referer). It carries a short-lived, single-purpose exchange code
        in the URL *fragment*, which browsers do not send to any server."""
        with app.app_context():
            user = User(name="Test", email="test@example.com")
            db.session.add(user)
            db.session.commit()

            resp = _build_login_response(user)
            assert resp.location.startswith("http://localhost:3000/auth/callback#code=")
            assert "access_token" not in resp.location
            # Every PyJWT token starts with the base64 of '{"alg"'.
            assert "eyJhbGci" not in resp.location


def _code_from(resp):
    return resp.location.split("#code=", 1)[1]


class TestOAuthExchange:
    """The API only accepts the Authorization header, so the frontend trades
    the redirect's code for a token it keeps in localStorage."""

    def _make_user(self, db):
        user = User(name="Exchange User", email="exchange@example.com")
        db.session.add(user)
        db.session.commit()
        return user

    def test_valid_code_returns_a_working_token(self, app, client, db):
        with app.app_context():
            user = self._make_user(db)
            code = _code_from(_build_login_response(user))

        resp = client.post("/auth/oauth/exchange", json={"code": code})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["name"] == "Exchange User"
        assert body["token"]

        assert resp.headers.get("Set-Cookie") is None

        profile = client.get("/me/profile", headers={"Authorization": f"Bearer {body['token']}"})
        assert profile.status_code == 200
        assert profile.get_json()["email"] == "exchange@example.com"

    def test_garbage_code_is_rejected(self, client, db):
        resp = client.post("/auth/oauth/exchange", json={"code": "not-a-real-code"})
        assert resp.status_code == 401

    def test_missing_code_is_a_bad_request(self, client, db):
        assert client.post("/auth/oauth/exchange", json={}).status_code == 400
        assert client.post("/auth/oauth/exchange").status_code == 400

    def test_expired_code_is_rejected(self, app, client, db):
        with app.app_context():
            user = self._make_user(db)
            code = _code_from(_build_login_response(user))

        with patch("app.routes.oauth.OAUTH_CODE_MAX_AGE_SECONDS", -1):
            resp = client.post("/auth/oauth/exchange", json={"code": code})
        assert resp.status_code == 401

    def test_code_for_a_deleted_user_is_rejected(self, app, client, db):
        with app.app_context():
            user = self._make_user(db)
            code = _code_from(_build_login_response(user))
            db.session.delete(user)
            db.session.commit()

        assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 401

    def test_code_is_single_use(self, app, client, db):
        """A code leaked through history or a log must not mint tokens again."""
        with app.app_context():
            user = self._make_user(db)
            code = _code_from(_build_login_response(user))

        assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 200
        replay = client.post("/auth/oauth/exchange", json={"code": code})
        assert replay.status_code == 401
        assert "token" not in replay.get_json()

        with app.app_context():
            assert db.session.get(User, user.user_id).oauth_code_nonce is None

    def test_a_new_login_invalidates_the_previous_unused_code(self, app, client, db):
        with app.app_context():
            user = self._make_user(db)
            first = _code_from(_build_login_response(user))
            second = _code_from(_build_login_response(user))

        assert client.post("/auth/oauth/exchange", json={"code": first}).status_code == 401
        assert client.post("/auth/oauth/exchange", json={"code": second}).status_code == 200

    def test_an_expired_code_does_not_consume_the_nonce(self, app, client, db):
        with app.app_context():
            user = self._make_user(db)
            code = _code_from(_build_login_response(user))

        with patch("app.routes.oauth.OAUTH_CODE_MAX_AGE_SECONDS", -1):
            assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 401
        with app.app_context():
            assert db.session.get(User, user.user_id).oauth_code_nonce is not None

    def test_a_validly_signed_code_without_a_nonce_is_rejected(self, app, client, db):
        """Codes minted before single-use existed carry no nonce."""
        from app.routes.oauth import _code_serializer
        with app.app_context():
            user = self._make_user(db)
            code = _code_serializer().dumps({"uid": user.user_id})

        assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 401

    def test_a_validly_signed_code_with_a_wrong_nonce_is_rejected(self, app, client, db):
        from app.routes.oauth import _code_serializer
        with app.app_context():
            user = self._make_user(db)
            _build_login_response(user)
            code = _code_serializer().dumps({"uid": user.user_id, "nonce": "forged"})

        assert client.post("/auth/oauth/exchange", json={"code": code}).status_code == 401

    def test_a_jwt_cannot_be_used_as_an_exchange_code(self, app, client, db):
        """The code is signed with a dedicated salt, so an access token (or
        any other signed value) is not accepted in its place."""
        from flask_jwt_extended import create_access_token

        with app.app_context():
            user = self._make_user(db)
            jwt_value = create_access_token(identity=str(user.user_id))

        assert client.post("/auth/oauth/exchange", json={"code": jwt_value}).status_code == 401


class TestGoogleLogin:
    def test_google_login_redirects(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.authorize_redirect.return_value = MagicMock(status_code=302)
            mock_oauth.google = mock_google

            resp = client.get("/auth/google")
            assert resp.status_code in (200, 302)

    def test_google_login_error_redirects_to_frontend_with_error_flag(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_google = MagicMock()
            mock_google.authorize_redirect.side_effect = Exception("OAuth error")
            mock_oauth.google = mock_google

            resp = client.get("/auth/google")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location


class TestGoogleCallback:
    def test_authorize_access_token_failure_redirects_with_error(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.side_effect = Exception("Token error")
            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location

    def test_userinfo_fetch_failure_redirects_with_error(self, client, db):
        mock_token = {}  # no "userinfo" key -> forces the userinfo() fallback call
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token
            mock_oauth.google.userinfo.side_effect = Exception("Userinfo error")

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location

    def test_userinfo_fallback_passes_token_explicitly(self, client, db):
        """When authorize_access_token()'s response has no 'userinfo' key,
        the code falls back to oauth.google.userinfo(token=token) -- some
        Authlib versions don't attach the token to that call automatically,
        which causes a 401 unless it's passed explicitly."""
        mock_token = {"access_token": "ya29.fake-access-token"}
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token
            mock_oauth.google.userinfo.return_value = {
                "sub": "google_explicit", "email": "explicit@example.com", "email_verified": True,
                "name": "Explicit User",
            }

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302

            mock_oauth.google.userinfo.assert_called_once()
            _, kwargs = mock_oauth.google.userinfo.call_args
            assert kwargs.get("token") is mock_token

    def test_missing_sub_in_userinfo_redirects_with_error(self, client, db):
        """'sub' (the provider's stable user id) is required; without it we
        can't reliably identify the user across logins."""
        mock_token = {"userinfo": {"name": "No Sub"}}
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location

    def test_successful_full_flow_creates_user_and_link_and_redirects_to_the_callback(self, client, db):
        mock_token = {
            "userinfo": {"sub": "google_user_1", "email": "googleuser@example.com",
                         "email_verified": True, "name": "Google User"}
        }
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "/auth/callback" in resp.location
            assert "access_token_cookie" not in resp.headers.get("Set-Cookie", "")

        with client.application.app_context():
            user = User.query.filter_by(email="googleuser@example.com").first()
            assert user is not None
            assert user.name == "Google User"

            link = OAuthAccount.query.filter_by(provider="google", provider_user_id="google_user_1").first()
            assert link is not None
            assert link.user_id == user.user_id

    def test_missing_email_falls_back_to_a_synthetic_noreply_address(self, client, db):
        mock_token = {"userinfo": {"sub": "no_email_user", "name": "No Email User"}}
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "/auth/callback" in resp.location

        with client.application.app_context():
            user = User.query.filter_by(email="google_no_email_user@users.noreply.google.com").first()
            assert user is not None
            assert user.name == "No Email User"

    def test_missing_name_falls_back_to_email_local_part(self, client, db):
        mock_token = {"userinfo": {"sub": "no_name_user", "email": "noname@example.com", "email_verified": True}}
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302

        with client.application.app_context():
            user = User.query.filter_by(email="noname@example.com").first()
            assert user is not None
            assert user.name == "noname"

    def test_email_already_registered_with_password_redirects_with_email_exists(self, client, db):
        """Mirrors test_does_not_auto_link_existing_email_without_prior_oauth_link,
        but through the real HTTP callback instead of calling the helper directly."""
        with client.application.app_context():
            existing = User(name="Existing", email="taken@example.com")
            existing.password = "some_hash"
            db.session.add(existing)
            db.session.commit()

        mock_token = {"userinfo": {"sub": "google_new", "email": "taken@example.com", "email_verified": True,
                               "name": "New Google Login"}}
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = mock_token

            resp = client.get("/auth/google/callback")
            assert resp.status_code == 302
            assert "error=email_exists" in resp.location


class TestGoogleVerifiedEmail:
    """Linking by email is only safe when the provider vouches for it."""

    def _login(self, client, userinfo):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.google.authorize_access_token.return_value = {"userinfo": userinfo}
            return client.get("/auth/google/callback")

    def test_unverified_email_does_not_reach_a_password_account(self, client, db):
        with client.application.app_context():
            db.session.add(User(name="Victim", email="victim@example.com", password="hash"))
            db.session.commit()

        resp = self._login(client, {"sub": "g_attacker", "email": "victim@example.com",
                                    "email_verified": False, "name": "Attacker"})
        assert "/auth/callback" in resp.location
        assert "error=email_exists" not in resp.location

        with client.application.app_context():
            assert OAuthAccount.query.filter_by(provider="google", provider_user_id="g_attacker").one() \
                .user.email == "google_g_attacker@users.noreply.google.com"
            victim = User.query.filter_by(email="victim@example.com").one()
            assert victim.oauth_code_nonce is None
            assert OAuthAccount.query.filter_by(user_id=victim.user_id).count() == 0

    def test_unverified_email_does_not_return_an_account_that_has_a_google_link(self, client, db):
        """The existing-link branch used to hand the victim's account to any
        Google identity that merely claimed the same address."""
        with client.application.app_context():
            victim = User(name="Victim", email="victim@example.com")
            db.session.add(victim)
            db.session.flush()
            db.session.add(OAuthAccount(user_id=victim.user_id, provider="google", provider_user_id="g_victim"))
            db.session.commit()
            victim_id = victim.user_id

        self._login(client, {"sub": "g_attacker", "email": "victim@example.com",
                             "email_verified": False, "name": "Attacker"})

        with client.application.app_context():
            link = OAuthAccount.query.filter_by(provider="google", provider_user_id="g_attacker").one()
            assert link.user_id != victim_id
            assert db.session.get(User, victim_id).oauth_code_nonce is None

    def test_missing_email_verified_claim_counts_as_unverified(self, client, db):
        resp = self._login(client, {"sub": "g_noclaim", "email": "claim@example.com", "name": "No Claim"})
        assert "/auth/callback" in resp.location
        with client.application.app_context():
            assert User.query.filter_by(email="claim@example.com").first() is None
            assert User.query.filter_by(email="google_g_noclaim@users.noreply.google.com").first() is not None

    def test_string_true_is_not_a_verified_claim(self, client, db):
        self._login(client, {"sub": "g_str", "email": "str@example.com", "email_verified": "true", "name": "Str"})
        with client.application.app_context():
            assert User.query.filter_by(email="str@example.com").first() is None

    def test_verified_email_is_stored_lowercased_and_matches_a_legacy_mixed_case_row(self, client, db):
        resp = self._login(client, {"sub": "g_case", "email": " Mixed@Example.COM ",
                                    "email_verified": True, "name": "Case"})
        assert "/auth/callback" in resp.location
        with client.application.app_context():
            assert User.query.filter_by(email="mixed@example.com").count() == 1

    def test_verified_email_colliding_with_a_legacy_mixed_case_password_row_is_refused(self, client, db):
        with client.application.app_context():
            db.session.add(User(name="Legacy", email="Legacy@Example.com", password="hash"))
            db.session.commit()

        resp = self._login(client, {"sub": "g_legacy", "email": "legacy@example.com",
                                    "email_verified": True, "name": "Case"})
        assert "error=email_exists" in resp.location
        with client.application.app_context():
            assert User.query.count() == 1


class TestGitHubLogin:
    def test_github_login_error_redirects_to_frontend_with_error_flag(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_github = MagicMock()
            mock_github.authorize_redirect.side_effect = Exception("GitHub error")
            mock_oauth.github = mock_github

            resp = client.get("/auth/github")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location


class TestGitHubCallback:
    def test_authorize_access_token_failure_redirects_with_error(self, client, db):
        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.github.authorize_access_token.side_effect = Exception("Token error")
            resp = client.get("/auth/github/callback")
            assert resp.status_code == 302
            assert "error=oauth_failed" in resp.location

    def test_successful_callback_creates_user_and_link(self, client, db):
        mock_token = MagicMock()
        mock_profile = {"id": 12345, "login": "githubuser", "name": "GitHub User", "email": "github@example.com"}
        mock_emails = [{"email": "github@example.com", "primary": True, "verified": True}]

        def mock_get(url, **kwargs):
            resp = MagicMock()
            if url == "user/emails":
                resp.json.return_value = mock_emails
            else:
                resp.json.return_value = mock_profile
            resp.ok = True
            return resp

        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.github.authorize_access_token.return_value = mock_token
            mock_oauth.github.get.side_effect = mock_get

            resp = client.get("/auth/github/callback")
            assert resp.status_code == 302
            assert "/auth/callback" in resp.location
            assert "access_token_cookie" not in resp.headers.get("Set-Cookie", "")

        with client.application.app_context():
            user = User.query.filter_by(email="github@example.com").first()
            assert user is not None
            assert user.name == "GitHub User"

            link = OAuthAccount.query.filter_by(provider="github", provider_user_id="12345").first()
            assert link is not None

    def test_primary_email_is_preferred_over_secondary(self, client, db):
        """GitHub can return multiple emails; the primary one must win even
        if it isn't first in the list."""
        mock_token = MagicMock()
        mock_profile = {"id": 67890, "login": "ghuser", "name": "GH User"}
        mock_emails = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.json.return_value = mock_emails if url == "user/emails" else mock_profile
            resp.ok = True
            return resp

        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.github.authorize_access_token.return_value = mock_token
            mock_oauth.github.get.side_effect = mock_get

            resp = client.get("/auth/github/callback")
            assert resp.status_code == 302

        with client.application.app_context():
            user = User.query.filter_by(email="primary@example.com").first()
            assert user is not None

    def test_no_public_email_falls_back_to_synthetic_noreply_address(self, client, db):
        mock_token = MagicMock()
        mock_profile = {"id": 11111, "login": "noemail"}

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.json.return_value = [] if url == "user/emails" else mock_profile
            resp.ok = True
            return resp

        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.github.authorize_access_token.return_value = mock_token
            mock_oauth.github.get.side_effect = mock_get

            resp = client.get("/auth/github/callback")
            assert resp.status_code == 302

        with client.application.app_context():
            user = User.query.filter_by(email="github_11111@users.noreply.github.com").first()
            assert user is not None


class TestGitHubVerifiedEmail:
    def _login(self, client, profile, emails, emails_ok=True):
        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.json.return_value = emails if url == "user/emails" else profile
            resp.ok = emails_ok if url == "user/emails" else True
            return resp

        with patch("app.routes.oauth.oauth") as mock_oauth:
            mock_oauth.github.authorize_access_token.return_value = MagicMock()
            mock_oauth.github.get.side_effect = mock_get
            return client.get("/auth/github/callback")

    def _only_user_email(self, client, github_id):
        with client.application.app_context():
            link = OAuthAccount.query.filter_by(provider="github", provider_user_id=github_id).one()
            return link.user.email

    def test_unverified_primary_is_ignored(self, client, db):
        with client.application.app_context():
            db.session.add(User(name="Victim", email="victim@example.com", password="hash"))
            db.session.commit()

        resp = self._login(
            client, {"id": 501, "login": "attacker"},
            [{"email": "victim@example.com", "primary": True, "verified": False}],
        )
        assert "/auth/callback" in resp.location
        assert "error=email_exists" not in resp.location
        assert self._only_user_email(client, "501") == "github_501@users.noreply.github.com"

    def test_verified_non_primary_is_not_used(self, client, db):
        self._login(
            client, {"id": 502, "login": "x"},
            [{"email": "second@example.com", "primary": False, "verified": True}],
        )
        assert self._only_user_email(client, "502") == "github_502@users.noreply.github.com"

    def test_profile_email_is_ignored_when_it_is_not_a_verified_entry(self, client, db):
        self._login(
            client, {"id": 503, "login": "x", "email": "claimed@example.com"},
            [{"email": "claimed@example.com", "primary": False, "verified": False}],
        )
        assert self._only_user_email(client, "503") == "github_503@users.noreply.github.com"

    def test_profile_email_is_ignored_when_the_emails_endpoint_fails(self, client, db):
        self._login(client, {"id": 504, "login": "x", "email": "claimed@example.com"}, [], emails_ok=False)
        assert self._only_user_email(client, "504") == "github_504@users.noreply.github.com"

    def test_profile_email_matching_a_verified_entry_is_used_lowercased(self, client, db):
        self._login(
            client, {"id": 505, "login": "x", "email": "Public@Example.com"},
            [{"email": "public@example.com", "primary": False, "verified": True}],
        )
        assert self._only_user_email(client, "505") == "public@example.com"

    def test_verified_primary_is_stored_lowercased(self, client, db):
        self._login(
            client, {"id": 506, "login": "x"},
            [{"email": "Prime@Example.COM", "primary": True, "verified": True}],
        )
        assert self._only_user_email(client, "506") == "prime@example.com"
