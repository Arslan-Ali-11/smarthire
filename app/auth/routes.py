from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.auth.forms import RegistrationForm, LoginForm
from app.models import User, Job
from app.extensions import db


@bp.route("/")
def home():
    latest_jobs = (
        Job.query.filter_by(status="open")
        .order_by(Job.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template("home.html", latest_jobs=latest_jobs)


@bp.route("/jobs")
def jobs_redirect():
    return redirect(url_for("applicant.browse_jobs"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.name}!", "success")
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            if user.is_admin():
                return redirect(url_for("admin.dashboard"))
            if user.is_recruiter():
                return redirect(url_for("recruiter.dashboard"))
            return redirect(url_for("applicant.dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.home"))


@bp.route("/notifications")
@login_required
def notifications():
    """View automated email notifications sent to the user."""
    from app.models import EmailLog
    from flask import current_app

    import os
    username = (current_app.config.get("MAIL_USERNAME") or os.environ.get("MAIL_USERNAME", "")).strip()
    password = (current_app.config.get("MAIL_PASSWORD") or os.environ.get("MAIL_PASSWORD", "")).strip()
    is_smtp_configured = bool(username and password)

    if current_user.is_admin():
        emails = EmailLog.query.order_by(EmailLog.sent_at.desc()).all()
    else:
        emails = (
            EmailLog.query.filter_by(recipient_email=current_user.email)
            .order_by(EmailLog.sent_at.desc())
            .all()
        )

    return render_template(
        "auth/notifications.html",
        emails=emails,
        is_smtp_configured=is_smtp_configured,
        smtp_sender=username,
    )
