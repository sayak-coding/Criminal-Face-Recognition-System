from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO
from .models import db, User

login_manager = LoginManager()
socketio = SocketIO()


def create_app(config="config.DevelopmentConfig"):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=60,       # DeepFace can take 2-3s — give it plenty of room
    ping_interval=25,      # keep-alive every 25s
)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .recognize.routes import recognize_bp
    from .api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(recognize_bp, url_prefix="/recognize")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Root redirect
    from flask import redirect, url_for
    @app.route("/")
    def index():
        return redirect(url_for("recognize.upload"))

    with app.app_context():
        db.create_all()
        _seed_admin(app)

    return app


def _seed_admin(app):
    """Create default admin user if none exists."""
    from .models import User
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(role="admin").first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()
        print("✅  Default admin created — username: admin / password: admin123")