import os
from flask import Flask, render_template
from config import Config
from app.extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.recruiter import bp as recruiter_bp
    app.register_blueprint(recruiter_bp, url_prefix="/recruiter")

    from app.applicant import bp as applicant_bp
    app.register_blueprint(applicant_bp, url_prefix="/applicant")

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def file_too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html"), 500

    # Create database tables and seed default admin account
    with app.app_context():
        from app.models import User, Job, Application  # noqa: F401
        db.create_all()

        # Seed default platform admin if no admin exists
        admin_exists = User.query.filter_by(role="admin").first()
        if not admin_exists:
            default_admin = User(
                name="Platform Admin",
                email="admin@smarthire.com",
                role="admin",
            )
            default_admin.set_password("admin123")
            db.session.add(default_admin)
            db.session.commit()

    # CLI command to seed/create custom admin
    @app.cli.command("init-admin")
    def init_admin():
        """Ensure an admin account is available."""
        from app.models import User
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(
                name="Platform Admin",
                email="admin@smarthire.com",
                role="admin",
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin@smarthire.com / admin123")
        else:
            print(f"Admin already exists: {admin.email}")

    # CLI command to run daily recruiter summary immediately
    @app.cli.command("send-daily-digest")
    def cli_send_daily_digest():
        """Send daily recruiter application summaries via scheduled mailer."""
        from app.mailer import send_all_recruiter_daily_summaries
        print("[SmartHire] Executing recruiter daily summary job...")
        results = send_all_recruiter_daily_summaries(since_hours=24)
        for r in results:
            if isinstance(r, dict) and "thread" in r and r["thread"]:
                r["thread"].join(timeout=10)
        print(f"[SmartHire] Done! Sent summaries to {len(results)} recruiter(s).")

    # Initialize automated background scheduler
    from app.scheduler import init_scheduler
    init_scheduler(app)

    return app
