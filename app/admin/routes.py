"""
SmartHire Admin Management Blueprint.
Provides platform-wide oversight, user role administration, job moderation,
and system analytics.
"""
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.admin import bp
from app.extensions import db
from app.models import User, Job, Application


def admin_required(f):
    """Decorator to enforce admin-only access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------
@bp.route("/")
@bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """Main platform analytics and activity overview."""
    total_users = User.query.count()
    recruiter_count = User.query.filter_by(role="recruiter").count()
    applicant_count = User.query.filter_by(role="applicant").count()
    admin_count = User.query.filter_by(role="admin").count()

    total_jobs = Job.query.count()
    open_jobs = Job.query.filter_by(status="open").count()
    closed_jobs = Job.query.filter_by(status="closed").count()

    total_apps = Application.query.count()
    shortlisted_apps = Application.query.filter_by(status="shortlisted").count()
    rejected_apps = Application.query.filter_by(status="rejected").count()
    on_hold_apps = Application.query.filter_by(status="on_hold").count()
    pending_apps = Application.query.filter_by(status="pending").count()

    # Platform average match score
    scored_apps = Application.query.filter(Application.match_score >= 0).all()
    avg_score = round(sum(a.match_score for a in scored_apps) / len(scored_apps), 1) if scored_apps else 0

    # Recent activity
    recent_applications = (
        Application.query.order_by(Application.applied_at.desc()).limit(8).all()
    )
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(6).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        recruiter_count=recruiter_count,
        applicant_count=applicant_count,
        admin_count=admin_count,
        total_jobs=total_jobs,
        open_jobs=open_jobs,
        closed_jobs=closed_jobs,
        total_apps=total_apps,
        shortlisted_apps=shortlisted_apps,
        rejected_apps=rejected_apps,
        on_hold_apps=on_hold_apps,
        pending_apps=pending_apps,
        avg_score=avg_score,
        recent_applications=recent_applications,
        recent_jobs=recent_jobs,
        recent_users=recent_users,
    )


# ---------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------
@bp.route("/users")
@login_required
@admin_required
def users():
    """Browse and manage all registered platform users."""
    search = request.args.get("search", "").strip().lower()
    role_filter = request.args.get("role", "").strip()

    query = User.query

    if role_filter in ["admin", "recruiter", "applicant"]:
        query = query.filter_by(role=role_filter)

    all_users = query.order_by(User.created_at.desc()).all()

    if search:
        all_users = [
            u for u in all_users
            if search in u.name.lower() or search in u.email.lower()
        ]

    return render_template(
        "admin/users.html",
        users=all_users,
        search=search,
        role_filter=role_filter,
    )


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
    """Change a user's role (admin, recruiter, applicant)."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    new_role = request.form.get("role")
    if new_role not in ["admin", "recruiter", "applicant"]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.users"))

    # Prevent demoting the current logged-in admin if they are the only admin
    if user.id == current_user.id and new_role != "admin":
        admin_count = User.query.filter_by(role="admin").count()
        if admin_count <= 1:
            flash("You cannot demote yourself because you are the only administrator on the platform.", "warning")
            return redirect(url_for("admin.users"))

    old_role = user.role
    user.role = new_role
    db.session.commit()

    flash(f"User '{user.name}' ({user.email}) role changed from {old_role} to {new_role}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user account and associated records."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    if user.id == current_user.id:
        flash("You cannot delete your own administrator account.", "danger")
        return redirect(url_for("admin.users"))

    user_name = user.name
    # Delete user's applications
    Application.query.filter_by(applicant_id=user.id).delete()
    # Delete user's jobs and their applications
    for job in user.jobs:
        Application.query.filter_by(job_id=job.id).delete()
        db.session.delete(job)

    db.session.delete(user)
    db.session.commit()

    flash(f"User account '{user_name}' and related records were deleted successfully.", "warning")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------
# Job Management
# ---------------------------------------------------------------------
@bp.route("/jobs")
@login_required
@admin_required
def jobs():
    """Browse and moderate all job postings across all recruiters."""
    search = request.args.get("search", "").strip().lower()
    status_filter = request.args.get("status", "").strip()

    query = Job.query
    if status_filter in ["open", "closed"]:
        query = query.filter_by(status=status_filter)

    all_jobs = query.order_by(Job.created_at.desc()).all()

    if search:
        all_jobs = [
            j for j in all_jobs
            if search in j.title.lower()
            or search in j.description.lower()
            or (j.recruiter and search in j.recruiter.name.lower())
        ]

    return render_template(
        "admin/jobs.html",
        jobs=all_jobs,
        search=search,
        status_filter=status_filter,
    )


@bp.route("/jobs/<int:job_id>/toggle-status", methods=["POST"])
@login_required
@admin_required
def toggle_job_status(job_id):
    """Toggle a job's status between open and closed."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    job.status = "closed" if job.status == "open" else "open"
    db.session.commit()

    flash(f'Job "{job.title}" status changed to {job.status}.', "info")
    return redirect(url_for("admin.jobs"))


@bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_job(job_id):
    """Delete a job posting and its applications."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    title = job.title
    db.session.delete(job)
    db.session.commit()

    flash(f'Job "{title}" and all associated applications have been permanently deleted.', "warning")
    return redirect(url_for("admin.jobs"))


# ---------------------------------------------------------------------
# Application Management
# ---------------------------------------------------------------------
@bp.route("/applications")
@login_required
@admin_required
def applications():
    """Platform-wide view of all submitted applications and screening results."""
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip().lower()

    query = Application.query
    if status_filter in ["pending", "shortlisted", "rejected", "on_hold"]:
        query = query.filter_by(status=status_filter)

    all_apps = query.order_by(Application.applied_at.desc()).all()

    if search:
        all_apps = [
            a for a in all_apps
            if (a.applicant and (search in a.applicant.name.lower() or search in a.applicant.email.lower()))
            or (a.job and search in a.job.title.lower())
            or (search in a.resume_text.lower())
        ]

    return render_template(
        "admin/applications.html",
        applications=all_apps,
        status_filter=status_filter,
        search=search,
    )


@bp.route("/applications/<int:app_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_application(app_id):
    """Delete an application record."""
    application = db.session.get(Application, app_id)
    if not application:
        abort(404)

    candidate_name = application.applicant.name if application.applicant else "Applicant"
    job_title = application.job.title if application.job else "Job"
    db.session.delete(application)
    db.session.commit()

    flash(f"Application for '{candidate_name}' ({job_title}) was removed.", "info")
    return redirect(url_for("admin.applications"))
