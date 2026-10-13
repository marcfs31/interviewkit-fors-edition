import re

from flask import Blueprint, request, jsonify, current_app
from ..models.user import User
import bcrypt
from sqlalchemy import func
from .. import db, limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import create_access_token


EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
MIN_PASSWORD_LENGTH = 8
# bcrypt only reads the first 72 bytes (bcrypt 5 raises past them).
MAX_PASSWORD_BYTES = 72
# Column sizes of User.name and User.email.
MAX_NAME_LENGTH = 80
MAX_EMAIL_LENGTH = 250

auth = Blueprint('auth', __name__, url_prefix='/auth')


def _password_too_long(password):
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


PASSWORD_TOO_LONG = (
    f"La contrasena no puede superar los {MAX_PASSWORD_BYTES} bytes "
    "(las tildes y los emojis ocupan mas de uno)"
)
EMAIL_TOO_LONG = f"El email no puede superar los {MAX_EMAIL_LENGTH} caracteres"
INVALID_FIELD_TYPES = "Los campos deben ser texto"


@auth.route('/register', methods=['POST'])
@limiter.limit("5 per hour", key_func=get_remote_address)
def register():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "El cuerpo de la peticion debe ser JSON"}), 400

    raw_name = data.get("name") or ""
    raw_email = data.get("email") or ""
    password = data.get("password") or ""
    if not all(isinstance(v, str) for v in (raw_name, raw_email, password)):
        return jsonify({"error": INVALID_FIELD_TYPES}), 400

    name = raw_name.strip()
    email = raw_email.strip().lower()

    if not name or not email or not password:
        return jsonify({"error": "Los campos no pueden estar vacios"}), 400

    if len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"El nombre no puede superar los {MAX_NAME_LENGTH} caracteres"}), 400

    if len(email) > MAX_EMAIL_LENGTH:
        return jsonify({"error": EMAIL_TOO_LONG}), 400

    if not re.match(EMAIL_REGEX, email):
        return jsonify({"error": "El formato del email no es valido"}), 400

    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"La contrasena debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"}), 400

    if _password_too_long(password):
        return jsonify({"error": PASSWORD_TOO_LONG}), 400

    if User.query.filter(func.lower(User.email) == email).first() is not None:
        return jsonify({"error": "Este email ya esta registrado"}), 409

    hashedPassword = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")

    new_user = User(name=name, email=email, password=hashedPassword)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": "Usuario creado correctamente"}), 201

@auth.route('/login', methods=['POST'])
@limiter.limit("10 per minute;50 per hour", key_func=get_remote_address)
def login():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "El cuerpo de la peticion debe ser JSON"}), 400

    email = data.get("email") or ""
    password = data.get("password") or ""
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": INVALID_FIELD_TYPES}), 400
    email = email.strip().lower()

    if not email or not password:
        return jsonify({"error": "Los campos no pueden estar vacios"}), 400

    if len(email) > MAX_EMAIL_LENGTH:
        return jsonify({"error": EMAIL_TOO_LONG}), 400

    if _password_too_long(password):
        return jsonify({"error": PASSWORD_TOO_LONG}), 400

    user = User.query.filter(func.lower(User.email) == email).first()

    if user is None:
        return jsonify({"error": "Credenciales incorrectas"}), 400

    if user.password is None:
        return jsonify({"error": "Credenciales incorrectas"}), 400

    encodedPassword = password.encode('utf-8')

    if bcrypt.checkpw(encodedPassword, user.password.encode('utf-8')) is False:
        return jsonify({"error": "Credenciales incorrectas"}), 400

    expires_delta = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    access_token = create_access_token(identity=str(user.user_id), expires_delta=expires_delta)

    response = jsonify({
        "user_id": user.user_id,
        "name": user.name,
        "token": access_token,
    })
    return response, 200


@auth.route('/logout', methods=['POST'])
def logout():
    # Stateless: the client drops its token. Server-side revocation is not implemented.
    return jsonify({"msg": "Sesion cerrada correctamente"}), 200