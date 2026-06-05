from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ─────────────────────────────────────────
#  AUTH MODELS (stored in app.db)
# ─────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="viewer")  # admin | viewer
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"
