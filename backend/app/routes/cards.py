from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models.card import Card
from ..models.session import Session
from ..models.question import Question
from ..services.ai_service import fix_literal_escapes
from .. import db

cards = Blueprint("cards", __name__, url_prefix="/cards")

# Over a cap is a 400, never a silent truncation. concept and code_language
# are their column sizes; the rest are payload caps (the columns are Text).
TEXT_LIMITS = {
    "concept": 120,
    "definition": 2000,
    "explanation": 2000,
    "use_case": 2000,
    "avoid_when": 2000,
    "code": 10000,
    "code_language": 50,
}
MAX_TAGS = 10
MAX_TAG_LENGTH = 40


def _clean_tags(raw):
    """The stripped tags, or None when `raw` isn't a valid list of them."""
    if not isinstance(raw, list) or len(raw) > MAX_TAGS:
        return None
    tags = []
    for tag in raw:
        if not isinstance(tag, str):
            return None
        tag = tag.strip()
        if not tag or len(tag) > MAX_TAG_LENGTH:
            return None
        tags.append(tag)
    return tags


def _validate_card_fields(data):
    """Returns (clean, error). `clean` holds the stripped text of every text
    field present in `data` ("" when null) and the normalized tags (None
    when null); `error` is the Spanish 400 message or None."""
    clean = {}
    for field in (*TEXT_LIMITS, "mnemonic"):
        if field not in data:
            continue
        raw = data[field]
        if raw is None:
            clean[field] = ""
            continue
        if not isinstance(raw, str):
            return None, f"El campo {field} debe ser texto"
        value = raw.strip()
        limit = TEXT_LIMITS.get(field)
        if limit and len(value) > limit:
            return None, f"El campo {field} no puede superar los {limit} caracteres"
        clean[field] = value

    if "tags" in data:
        tags = None if data["tags"] is None else _clean_tags(data["tags"])
        if tags is None and data["tags"] is not None:
            return None, (
                f"El campo tags debe ser una lista de hasta {MAX_TAGS} textos "
                f"no vacios de maximo {MAX_TAG_LENGTH} caracteres"
            )
        clean["tags"] = tags
    return clean, None


@cards.route("/", methods=["GET"])
@jwt_required()
def get_cards():
    user = get_jwt_identity()
    cards = Card.query.filter_by(user_id=user).all()

    response = [card.serialize() for card in cards]

    return jsonify(response), 200


@cards.route("/<int:card_id>", methods=["PATCH"])
@jwt_required()
def update_card(card_id):
    user = get_jwt_identity()

    card = Card.query.filter_by(card_id=card_id, user_id=user).first()

    if card is None:
        return jsonify({"msg": "La card no existe"}), 404

    data = request.get_json() or {}
    clean, error = _validate_card_fields(data)
    if error:
        return jsonify({"msg": error}), 400

    if clean.get("concept"):
        card.concept = clean["concept"]

    if "definition" in clean:
        card.definition = clean["definition"] or None

    if clean.get("explanation"):
        card.explanation = clean["explanation"]

    if clean.get("use_case"):
        card.use_case = clean["use_case"]

    if "avoid_when" in clean:
        card.avoid_when = clean["avoid_when"] or None

    if "mnemonic" in clean:
        card.mnemonic = clean["mnemonic"][:200] or None

    if "tags" in clean:
        card.tags = clean["tags"]

    if "code" in clean:
        card.code = fix_literal_escapes(clean["code"]) or None

    if clean.get("code_language"):
        card.code_language = clean["code_language"]

    db.session.commit()

    return jsonify(card.serialize()), 200


@cards.route("/<int:card_id>", methods=["DELETE"])
@jwt_required()
def delete_card(card_id):
    user = get_jwt_identity()

    card_to_delete = Card.query.filter_by(card_id=card_id, user_id=user).first()

    if card_to_delete is None:
        return jsonify({"msg": "la card no existe"}), 404

    db.session.delete(card_to_delete)
    db.session.commit()

    return jsonify({"msg": "Card Eliminada Exitosamente"}), 200


# Maps the textual level to a numeric difficulty
LEVEL_TO_DIFFICULTY = {
    "Básico": 1,
    "Intermedio": 2,
    "Avanzado": 3,
}


@cards.route("/", methods=["POST"])
@jwt_required()
def create_card():
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    session_id = data.get("session_id")
    question_id = data.get("question_id")
    # bool is an int subclass, and anything else reaches the DB driver as a 500
    if not all(
        isinstance(v, int) and not isinstance(v, bool)
        for v in (session_id, question_id)
    ):
        return jsonify(
            {"error": "session_id y question_id deben ser números enteros"}
        ), 400

    # Ownership check: the session must belong to the authenticated user
    session = Session.query.filter_by(session_id=session_id, user_id=user_id).first()
    if not session:
        return jsonify({"msg": "La sesion no existe"}), 404

    # The question must belong to that same session, not just exist
    question = Question.query.filter_by(
        question_id=question_id, session_id=session_id
    ).first()
    if not question:
        return jsonify({"msg": "La pregunta no existe"}), 404

    clean, error = _validate_card_fields(data)
    if error:
        return jsonify({"msg": error}), 400

    concept = clean.get("concept", "")
    explanation = clean.get("explanation", "")
    use_case = clean.get("use_case", "")
    if not concept or not explanation or not use_case:
        return jsonify(
            {"msg": "Los campos concept, explanation y use_case son obligatorios"}
        ), 400

    # Difficulty is inherited from the session's level
    difficulty = LEVEL_TO_DIFFICULTY.get(session.level)

    new_card = Card(
        question_id=data.get("question_id"),
        session_id=data.get("session_id"),
        user_id=user_id,
        concept=concept,
        definition=clean.get("definition") or None,
        explanation=explanation,
        use_case=use_case,
        avoid_when=clean.get("avoid_when") or None,
        mnemonic=clean.get("mnemonic", "")[:200] or None,
        tags=clean.get("tags"),
        code=fix_literal_escapes(clean.get("code", "")) or None,
        code_language=clean.get("code_language") or "javascript",
        difficulty=difficulty,
    )
    db.session.add(new_card)
    db.session.commit()

    return jsonify(
        {
            "card_id": new_card.card_id,
            "concept": new_card.concept,
        }
    ), 201
