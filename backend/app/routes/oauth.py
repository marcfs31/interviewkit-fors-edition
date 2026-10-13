import secrets

from flask import Blueprint, redirect, url_for, current_app, request, jsonify
from flask_jwt_extended import create_access_token
from authlib.integrations.flask_client import OAuth
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from ..models.user import User
from ..models.oauth_account import OAuthAccount
from .. import db, limiter
from flask_limiter.util import get_remote_address

oauth_bp = Blueprint("oauth", __name__, url_prefix="/auth")

oauth = OAuth()

# After a successful provider login the browser is redirected to the frontend
# with a short-lived exchange code. The frontend trades it for an access token
# it can keep in localStorage, exactly like an email/password login. The API
# lives on another site than the frontend and only accepts the Authorization
# header, so no auth cookie is ever set.
OAUTH_CODE_MAX_AGE_SECONDS = 60
_OAUTH_CODE_SALT = "oauth-login-exchange"


def _code_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_OAUTH_CODE_SALT)


def _normalize_email(email):
    return email.strip().lower()


def _user_by_email(email):
    # func.lower so rows stored before emails were lowercased still match.
    return User.query.filter(func.lower(User.email) == email).first()


def _get_or_create_user(provider, provider_user_id, email, name):
    # The caller passes a provider-verified address or a synthetic noreply one,
    # never an unverified claim: this function links accounts by email.
    email = _normalize_email(email)
    existing = OAuthAccount.query.filter_by(
        provider=provider, provider_user_id=provider_user_id
    ).first()

    if existing:
        user = db.session.get(User, existing.user_id)
        if user is None:
            db.session.delete(existing)
            db.session.commit()
        else:
            return user

    user_by_email = _user_by_email(email)

    if user_by_email:
        existing_link = OAuthAccount.query.filter_by(
            user_id=user_by_email.user_id, provider=provider
        ).first()

        if not existing_link:
            return None
        return user_by_email

    new_user = User(name=name, email=email)
    db.session.add(new_user)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        user_by_email = _user_by_email(email)
        if user_by_email:
            return _get_or_create_user(provider, provider_user_id, email, name)
        raise

    link = OAuthAccount(
        user_id=new_user.user_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    db.session.add(link)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        User.query.filter_by(user_id=new_user.user_id).delete()
        db.session.commit()
        linked = OAuthAccount.query.filter_by(
            provider=provider, provider_user_id=provider_user_id
        ).first()
        if linked:
            user = db.session.get(User, linked.user_id)
            if user:
                return user
        return _get_or_create_user(provider, provider_user_id, email, name)

    return new_user


def _build_login_response(user):
    frontend_url = current_app.config["FRONTEND_URL"]
    # The code goes in the URL fragment: browsers never send fragments to a
    # server, so it stays out of access logs and Referer headers.
    # Single use: only the latest nonce stored on the user can be redeemed, and
    # redeeming it clears it. A newer login supersedes an unredeemed code.
    nonce = secrets.token_urlsafe(32)
    user.oauth_code_nonce = nonce
    db.session.commit()
    code = _code_serializer().dumps({"uid": user.user_id, "nonce": nonce})
    return redirect(f"{frontend_url}/auth/callback#code={code}")


@oauth_bp.route("/oauth/exchange", methods=["POST"])
@limiter.limit("20 per minute", key_func=get_remote_address)
def exchange_code():
    data = request.get_json(silent=True) or {}
    code = data.get("code")
    if not code or not isinstance(code, str):
        return jsonify({"error": "Falta el codigo de acceso"}), 400

    try:
        payload = _code_serializer().loads(code, max_age=OAUTH_CODE_MAX_AGE_SECONDS)
    except (SignatureExpired, BadSignature):
        return jsonify({"error": "Codigo invalido o caducado"}), 401

    uid = payload.get("uid") if isinstance(payload, dict) else None
    nonce = payload.get("nonce") if isinstance(payload, dict) else None
    if not isinstance(uid, int) or not isinstance(nonce, str) or not nonce:
        return jsonify({"error": "Codigo invalido o caducado"}), 401

    consumed = db.session.execute(
        update(User)
        .where(User.user_id == uid, User.oauth_code_nonce == nonce)
        .values(oauth_code_nonce=None)
    )
    db.session.commit()
    if consumed.rowcount != 1:
        return jsonify({"error": "Codigo invalido o caducado"}), 401

    user = db.session.get(User, uid)

    expires_delta = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    access_token = create_access_token(identity=str(user.user_id), expires_delta=expires_delta)
    response = jsonify({"user_id": user.user_id, "name": user.name, "token": access_token})
    return response, 200


@oauth_bp.route("/google")
def google_login():
    try:
        redirect_uri = url_for("oauth.google_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception:
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")


@oauth_bp.route("/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        current_app.logger.warning("google authorize_access_token failed: %s", e)
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")

    try:
        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                # Pass the token explicitly: in some Authlib versions the token
                # stored after authorize_access_token isn't attached automatically
                # to the userinfo() call, and the endpoint responds with 401.
                userinfo = oauth.google.userinfo(token=token)
            except Exception as e:
                current_app.logger.warning("google userinfo fallback failed: %s", e)
                frontend_url = current_app.config["FRONTEND_URL"]
                return redirect(f"{frontend_url}/login?error=oauth_failed")

        google_id = str(userinfo["sub"])
        # `is True`: only an explicit boolean from Google vouches for the address.
        email = userinfo.get("email") if userinfo.get("email_verified") is True else None
        if not email:
            email = f"google_{google_id}@users.noreply.google.com"
        name = userinfo.get("name", email.split("@")[0]) or f"Google User {google_id}"

        user = _get_or_create_user(
            provider="google",
            provider_user_id=google_id,
            email=email,
            name=name,
        )

        if user is None:
            frontend_url = current_app.config["FRONTEND_URL"]
            return redirect(f"{frontend_url}/login?error=email_exists")
        
        return _build_login_response(user)
    
    except Exception as e:
        current_app.logger.exception("google callback unhandled error: %s", e)
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")


@oauth_bp.route("/github")
def github_login():
    try:
        redirect_uri = url_for("oauth.github_callback", _external=True)
        return oauth.github.authorize_redirect(redirect_uri)
    except Exception as e:
        current_app.logger.warning("github authorize_redirect failed: %s", e)
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")


@oauth_bp.route("/github/callback")
def github_callback():
    try:
        token = oauth.github.authorize_access_token()
    except Exception as e:
        current_app.logger.warning("github authorize_access_token failed: %s", e)
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")

    try:
        resp = oauth.github.get("user", token=token)
        profile = resp.json()

        github_id = str(profile["id"])
        name = profile.get("name") or profile.get("login", "") or f"GitHub User {github_id}"
        verified_emails = []
        primary_email = None

        emails_resp = oauth.github.get("user/emails", token=token)
        if emails_resp.ok:
            for e in emails_resp.json():
                address = e.get("email")
                if not address or e.get("verified") is not True:
                    continue
                verified_emails.append(_normalize_email(address))
                if e.get("primary") and primary_email is None:
                    primary_email = address

        # The profile email is a free-text claim: trust it only if GitHub also
        # lists it as a verified address.
        profile_email = profile.get("email")
        if not primary_email and profile_email and _normalize_email(profile_email) in verified_emails:
            primary_email = profile_email

        email = primary_email
        if not email:
            email = f"github_{github_id}@users.noreply.github.com"

        user = _get_or_create_user(
            provider="github",
            provider_user_id=github_id,
            email=email,
            name=name,
        )

        if user is None:
            frontend_url = current_app.config["FRONTEND_URL"]
            return redirect(f"{frontend_url}/login?error=email_exists")

        return _build_login_response(user)
    
    except Exception as e:
        current_app.logger.exception("github callback unhandled error: %s", e)
        frontend_url = current_app.config["FRONTEND_URL"]
        return redirect(f"{frontend_url}/login?error=oauth_failed")