from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from app.utils.timezone import set_process_timezone

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Debes iniciar sesión para acceder a esta página.'


def create_app(config_class=Config):
    set_process_timezone(getattr(config_class, 'APP_TIMEZONE', 'America/Bogota'))
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.routes.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp)
    
    from app.routes.inventario import inventario_bp
    app.register_blueprint(inventario_bp)
    
    from app.routes.ventas import ventas_bp
    app.register_blueprint(ventas_bp)
    
    from app.routes.gallinas import gallinas_bp
    app.register_blueprint(gallinas_bp)

    from app.permissions.service import (
        can_access_endpoint,
        enforce_permission_by_endpoint,
        sync_defined_permissions,
    )

    @app.before_request
    def _enforce_permissions():
        return enforce_permission_by_endpoint()

    @app.context_processor
    def _inject_permission_helpers():
        return {'can_access_endpoint': can_access_endpoint}

    with app.app_context():
        sync_defined_permissions()
        try:
            from app.routes.usuarios import ensure_rbac_seed
            ensure_rbac_seed()
        except Exception:
            # Evita bloquear el arranque si hay un problema temporal en el seed RBAC.
            pass

    return app


from app import models
