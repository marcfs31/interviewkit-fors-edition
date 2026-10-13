from .. import db

class User(db.Model):
    __tablename__ = "user"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(250), unique=True)
    password = db.Column(db.String(250), nullable=True)
    total_xp = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1)
    # The one OAuth exchange code that may still be redeemed; cleared on use.
    oauth_code_nonce = db.Column(db.String(64), nullable=True)

    oauth_accounts = db.relationship("OAuthAccount", backref="user", lazy="dynamic")