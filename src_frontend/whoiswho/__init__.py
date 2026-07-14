from pathlib import Path

from flask import Flask
from flask_wtf import CSRFProtect

from . import config
from . import avatar_storage as avatar_storage_module
from .seed import seed_demo_data
from .blueprints.auth import bp as auth_bp
from .blueprints.employees import bp as employees_bp
from .blueprints.game import bp as game_bp
from .blueprints.profile import bp as profile_bp

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    if config.AUTH_MODE != "mock" and not config.SECRET_KEY:
        raise RuntimeError(
            "WHOISWHO_SECRET_KEY must be set when WHOISWHO_AUTH_MODE is not 'mock'."
        )

    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
    app.secret_key = config.SECRET_KEY
    app.config["APPLICATION_ROOT"] = "/"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    # Derived from avatar_storage's own upload dir (not recomputed here) so the
    # serving path always matches the saving path, even when WHOISWHO_AVATAR_DIR
    # points somewhere other than this package's default.
    app.config["UPLOAD_FOLDER"] = str(avatar_storage_module.LOCAL_UPLOAD_DIR)
    CSRFProtect(app)

    seed_demo_data()

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(game_bp)

    return app
