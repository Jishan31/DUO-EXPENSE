import os
from flask import Flask

from config import Config
from extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from utils.oauth import init_oauth
    init_oauth(app)

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.expense import expense_bp
    from routes.category import category_bp
    from routes.income import income_bp
    from routes.scanner import scanner_bp
    from routes.budget import budget_bp
    from routes.analytics import analytics_bp
    from routes.loan import loan_bp
    from routes.business import business_bp
    from routes.client import client_bp
    from routes.invoice import invoice_bp
    from routes.assistant import assistant_bp
    from routes.import_data import import_bp
    from routes.filing import filing_bp
    from routes.auditor import auditor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(income_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(budget_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(loan_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(invoice_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(filing_bp)
    app.register_blueprint(auditor_bp)

    @app.before_request
    def _restrict_auditor_accounts():
        # Auditor accounts are a distinct account type on this platform — keep them
        # scoped to their own area rather than the personal-finance features, which
        # don't apply to them.
        from flask import request, redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated and current_user.role == "auditor":
            allowed_prefixes = ("/auditor", "/static", "/logout", "/contact")
            if not any(request.path.startswith(p) for p in allowed_prefixes):
                return redirect(url_for("auditor.auditor_dashboard"))

    with app.app_context():
        db.create_all()
        from utils.migrate import upgrade_schema
        upgrade_schema(app, db)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
