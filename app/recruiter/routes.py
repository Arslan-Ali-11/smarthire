import os
import json
from functools import wraps
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    Response,
    send_file,
    current_app,
)
from flask_login import login_required, current_user
from app.recruiter import bp
from app.recruiter.forms import JobForm
from app.models import Job, Application
from app.extensions import db
from app.reports import generate_applicants_csv, generate_applicants_pdf
from app.mailer import (
    send_application_shortlisted,
    send_application_rejected,
    send_application_on_hold,
)
from app.ai import (
    parse_resume,
    score_candidate,
    generate_resume_feedback,
    generate_interview_questions,
    process_application_insights,
)
import io


def recruiter_required(f):
    """Decorator to restrict access to recruiter-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_recruiter():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------
@bp.route("/dashboard")
@login_required
@recruiter_required
def dashboard():
    jobs = (
        Job.query.filter_by(recruiter_id=current_user.id)
        .order_by(Job.created_at.desc())
        .all()
    )

    total_jobs = len(jobs)
    active_jobs = sum(1 for j in jobs if j.status == "open")

    # Aggregate applications across all recruiter's jobs
    job_ids = [j.id for j in jobs]
    all_apps = (
        Application.query.filter(Application.job_id.in_(job_ids)).all()
        if job_ids
        else []
    )
    total_applications = len(all_apps)
    shortlisted_count = sum(1 for a in all_apps if a.status == "shortlisted")

    scored_scores = [a.match_score for a in all_apps if a.match_score >= 0]
    avg_score = (
        round(sum(scored_scores) / len(scored_scores), 1) if scored_scores else None
    )

    # Group shortlisted candidates by job for popup modal
    shortlisted_apps = [a for a in all_apps if a.status == "shortlisted"]
    shortlisted_jobs_data = []
    for j in jobs:
        j_shortlisted = [a for a in shortlisted_apps if a.job_id == j.id]
        if j_shortlisted:
            shortlisted_jobs_data.append({
                "job": j,
                "candidates": j_shortlisted,
                "count": len(j_shortlisted),
            })

    return render_template(
        "recruiter/dashboard.html",
        jobs=jobs,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_applications=total_applications,
        shortlisted_count=shortlisted_count,
        shortlisted_apps=shortlisted_apps,
        shortlisted_jobs_data=shortlisted_jobs_data,
        avg_score=avg_score,
    )


@bp.route("/send-daily-digest", methods=["POST"])
@login_required
@recruiter_required
def send_daily_digest():
    """Trigger daily application summary email to current recruiter for immediate review."""
    from app.mailer import send_recruiter_daily_summary

    result = send_recruiter_daily_summary(current_user, since_hours=24)
    count = result.get("count", 0)
    flash(
        f"Daily application summary email sent to {current_user.email}! "
        f"Summary contains {count} candidate{'s' if count != 1 else ''} from the last 24 hours.",
        "success",
    )
    return redirect(url_for("recruiter.dashboard"))


# ---------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------
@bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
@recruiter_required
def create_job():
    form = JobForm()
    if form.validate_on_submit():
        skills_raw = form.required_skills.data or ""
        skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]

        job = Job(
            recruiter_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            required_skills=json.dumps(skills_list),
            min_experience_years=form.min_experience_years.data or 0,
            status=form.status.data,
        )
        db.session.add(job)
        db.session.commit()
        flash(f'Job "{job.title}" has been posted successfully!', "success")
        return redirect(url_for("recruiter.dashboard"))

    return render_template("recruiter/job_form.html", form=form, title="Post a New Job", is_edit=False)


@bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@recruiter_required
def edit_job(job_id):
    job = db.session.get(Job, job_id)
    if not job or job.recruiter_id != current_user.id:
        abort(404)

    form = JobForm(obj=job)
    if request.method == "GET":
        form.required_skills.data = ", ".join(job.get_skills_list())

    if form.validate_on_submit():
        skills_raw = form.required_skills.data or ""
        skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]

        job.title = form.title.data.strip()
        job.description = form.description.data.strip()
        job.required_skills = json.dumps(skills_list)
        job.min_experience_years = form.min_experience_years.data or 0
        job.status = form.status.data

        db.session.commit()
        flash(f'Job "{job.title}" updated successfully!', "success")
        return redirect(url_for("recruiter.dashboard"))

    return render_template("recruiter/job_form.html", form=form, title=f"Edit Job: {job.title}", job=job, is_edit=True)


@bp.route("/jobs/<int:job_id>/toggle-status", methods=["POST"])
@login_required
@recruiter_required
def toggle_job_status(job_id):
    job = db.session.get(Job, job_id)
    if not job or job.recruiter_id != current_user.id:
        abort(404)

    job.status = "closed" if job.status == "open" else "open"
    db.session.commit()
    flash(f'Job "{job.title}" is now {job.status}.', "info")
    return redirect(url_for("recruiter.dashboard"))


@bp.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@recruiter_required
def delete_job(job_id):
    job = db.session.get(Job, job_id)
    if not job or job.recruiter_id != current_user.id:
        abort(404)

    title = job.title
    db.session.delete(job)
    db.session.commit()
    flash(f'Job "{title}" and all its applications were deleted.', "warning")
    return redirect(url_for("recruiter.dashboard"))


# ---------------------------------------------------------------------
# Ranked Applicant List & Filters
# ---------------------------------------------------------------------
@bp.route("/jobs/<int:job_id>/applicants")
@login_required
@recruiter_required
def job_applicants(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)
    if job.recruiter_id != current_user.id:
        abort(403)

    # Filtering parameters from query string
    status_filter = request.args.get("status", "").strip()
    min_score = request.args.get("min_score", "").strip()
    search = request.args.get("search", "").strip().lower()

    query = Application.query.filter_by(job_id=job.id)

    if status_filter in ["pending", "shortlisted", "rejected", "on_hold"]:
        query = query.filter_by(status=status_filter)

    if min_score.isdigit():
        query = query.filter(Application.match_score >= int(min_score))

    # Order ranked: highest match score first, then earliest applied
    applications = query.order_by(Application.match_score.desc(), Application.applied_at.asc()).all()

    # Search filter on candidate name, email, or resume skills
    if search:
        applications = [
            app
            for app in applications
            if (app.applicant and (search in app.applicant.name.lower() or search in app.applicant.email.lower()))
            or (search in app.resume_text.lower())
        ]

    # Quick metrics for this job
    total_for_job = len(job.applications)
    shortlisted_for_job = sum(1 for a in job.applications if a.status == "shortlisted")
    rejected_for_job = sum(1 for a in job.applications if a.status == "rejected")
    on_hold_for_job = sum(1 for a in job.applications if a.status == "on_hold")

    return render_template(
        "recruiter/job_applicants.html",
        job=job,
        applications=applications,
        status_filter=status_filter,
        min_score=min_score,
        search=search,
        total_for_job=total_for_job,
        shortlisted_for_job=shortlisted_for_job,
        rejected_for_job=rejected_for_job,
        on_hold_for_job=on_hold_for_job,
    )


# ---------------------------------------------------------------------
# Recruiter Actions: Shortlist, Reject, Hold, Reset
# ---------------------------------------------------------------------
@bp.route("/applications/<int:app_id>/status", methods=["POST"])
@login_required
@recruiter_required
def update_application_status(app_id):
    application = db.session.get(Application, app_id)
    if not application:
        abort(404)

    # Ensure current recruiter owns the job
    if application.job.recruiter_id != current_user.id:
        abort(403)

    new_status = request.form.get("status")
    allowed_statuses = {"pending", "shortlisted", "rejected", "on_hold"}
    if new_status not in allowed_statuses:
        flash("Invalid status choice.", "danger")
        return redirect(url_for("recruiter.job_applicants", job_id=application.job_id))

    application.status = new_status

    # If shortlisted, automatically ensure tailored interview questions are generated
    if new_status == "shortlisted":
        if not application.interview_questions:
            try:
                process_application_insights(application)
            except Exception as e:
                print(f"[SmartHire] Insights generation error: {type(e).__name__}")

    db.session.commit()

    # Trigger email notifications to applicant
    if application.applicant and application.applicant.email:
        recruiter_name = current_user.name if current_user.is_authenticated else "The Hiring Team"
        if new_status == "shortlisted":
            send_application_shortlisted(
                application.applicant.email,
                application.applicant.name,
                application.job.title,
                recruiter_name,
            )
        elif new_status == "rejected":
            send_application_rejected(
                application.applicant.email,
                application.applicant.name,
                application.job.title,
            )
        elif new_status == "on_hold":
            send_application_on_hold(
                application.applicant.email,
                application.applicant.name,
                application.job.title,
            )

    candidate_name = application.applicant.name if application.applicant else "Applicant"
    status_labels = {
        "shortlisted": "shortlisted and tailored interview questions generated",
        "rejected": "rejected",
        "on_hold": "placed on hold",
        "pending": "reset to pending",
    }
    flash(f"{candidate_name} has been {status_labels.get(new_status, new_status)}.", "success")
    return redirect(url_for("recruiter.job_applicants", job_id=application.job_id))


@bp.route("/applications/<int:app_id>/rescore", methods=["POST"])
@login_required
@recruiter_required
def rescore_application(app_id):
    """Re-run AI parser and match scorer for an application."""
    application = db.session.get(Application, app_id)
    if not application:
        abort(404)
    if application.job.recruiter_id != current_user.id:
        abort(403)

    parsed_info = parse_resume(application.resume_text)
    scoring = score_candidate(application.job, application.resume_text, parsed_info)

    application.parsed_data = json.dumps(parsed_info)
    application.match_score = scoring.get("match_score", 0)
    application.score_explanation = scoring.get("explanation", "")
    db.session.commit()

    # Generate unified insights (interview questions + resume feedback) in ONE AI call
    try:
        process_application_insights(application)
    except Exception as e:
        print(f"[SmartHire] Insights generation error: {type(e).__name__}")
    source = scoring.get("_ai_source", "AI Engine")
    flash(
        f"Application re-analyzed via {source}! New Match Score: {application.match_score}%.",
        "success",
    )
    return redirect(url_for("recruiter.job_applicants", job_id=application.job_id))


# ---------------------------------------------------------------------
# Export Reports (CSV / PDF)
# ---------------------------------------------------------------------
@bp.route("/jobs/<int:job_id>/export/csv")
@login_required
@recruiter_required
def export_csv(job_id):
    job = db.session.get(Job, job_id)
    if not job or job.recruiter_id != current_user.id:
        abort(404)

    applications = (
        Application.query.filter_by(job_id=job.id)
        .order_by(Application.match_score.desc(), Application.applied_at.asc())
        .all()
    )

    csv_data = generate_applicants_csv(job, applications)
    filename = f"candidates_{job.title.replace(' ', '_').lower()}_{job.id}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/jobs/<int:job_id>/export/pdf")
@login_required
@recruiter_required
def export_pdf(job_id):
    job = db.session.get(Job, job_id)
    if not job or job.recruiter_id != current_user.id:
        abort(404)

    applications = (
        Application.query.filter_by(job_id=job.id)
        .order_by(Application.match_score.desc(), Application.applied_at.asc())
        .all()
    )

    pdf_bytes = generate_applicants_pdf(job, applications)
    filename = f"candidates_{job.title.replace(' ', '_').lower()}_{job.id}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------
# View / Download Candidate Resume (CV)
# ---------------------------------------------------------------------
@bp.route("/applications/<int:app_id>/resume")
@login_required
@recruiter_required
def view_resume(app_id):
    """View or download candidate resume file (PDF or DOCX)."""
    application = db.session.get(Application, app_id)
    if not application:
        abort(404)

    # Ensure this recruiter owns the job posting
    if application.job.recruiter_id != current_user.id:
        abort(403)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    resume_path = os.path.join(upload_folder, application.resume_filename)

    # Fallback pattern match if filename was saved differently
    if not os.path.exists(resume_path) and os.path.exists(upload_folder):
        prefix = f"user_{application.applicant_id}_job_{application.job_id}_"
        for f in os.listdir(upload_folder):
            if f.startswith(prefix) or f == application.resume_filename or application.resume_filename in f:
                resume_path = os.path.join(upload_folder, f)
                break

    if not os.path.exists(resume_path):
        flash("Resume file could not be found on server storage.", "warning")
        return redirect(url_for("recruiter.job_applicants", job_id=application.job_id))

    display_name = application.get_display_filename()
    ext = application.get_resume_extension()

    # Allow query param ?download=1 to force attachment download
    force_download = request.args.get("download", "0") == "1"
    # PDF files can open directly in-browser tab; DOCX downloads
    as_attachment = force_download or (ext != "pdf")

    mimetype = (
        "application/pdf"
        if ext == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    return send_file(
        resume_path,
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=display_name,
    )
