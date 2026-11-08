import os
import uuid
from functools import wraps
from datetime import datetime, timezone
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.applicant import bp
from app.models import Job, Application
from app.extensions import db
from app.parser import extract_resume_text
from app.ai import (
    parse_resume,
    score_candidate,
    generate_application_insights,
    process_application_insights,
)
from app.mailer import send_application_received, send_recruiter_new_applicant_alert
import json


def applicant_required(f):
    """Decorator to restrict access to applicant-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_applicant():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------
# Applicant Dashboard
# ---------------------------------------------------------------------
@bp.route("/dashboard")
@login_required
@applicant_required
def dashboard():
    # Fetch all applications submitted by this applicant
    applications = (
        Application.query.filter_by(applicant_id=current_user.id)
        .order_by(Application.applied_at.desc())
        .all()
    )

    total_applied = len(applications)
    shortlisted_count = sum(1 for a in applications if a.status == "shortlisted")

    scores = [a.match_score for a in applications if a.match_score >= 0]
    best_score = max(scores) if scores else None

    # Applied job IDs to exclude from "Recommended Jobs"
    applied_job_ids = {a.job_id for a in applications}

    # Available open jobs the applicant hasn't applied to yet
    available_jobs = (
        Job.query.filter(Job.status == "open", ~Job.id.in_(applied_job_ids))
        .order_by(Job.created_at.desc())
        .limit(6)
        .all()
        if applied_job_ids
        else Job.query.filter_by(status="open").order_by(Job.created_at.desc()).limit(6).all()
    )

    return render_template(
        "applicant/dashboard.html",
        applications=applications,
        total_applied=total_applied,
        shortlisted_count=shortlisted_count,
        best_score=best_score,
        available_jobs=available_jobs,
    )


# ---------------------------------------------------------------------
# Public Job Board & Details
# ---------------------------------------------------------------------
@bp.route("/jobs")
def browse_jobs():
    """Browse all open job postings (publicly accessible)."""
    search = request.args.get("search", "").strip().lower()
    exp_filter = request.args.get("exp", "").strip()

    query = Job.query.filter_by(status="open")

    if exp_filter.isdigit():
        query = query.filter(Job.min_experience_years <= int(exp_filter))

    jobs = query.order_by(Job.created_at.desc()).all()

    if search:
        jobs = [
            j
            for j in jobs
            if search in j.title.lower()
            or search in j.description.lower()
            or search in j.required_skills.lower()
        ]

    # Map of job_id -> status for authenticated applicant
    applied_map = {}
    if current_user.is_authenticated and current_user.is_applicant():
        applied_apps = Application.query.filter_by(applicant_id=current_user.id).all()
        applied_map = {a.job_id: a.status for a in applied_apps}

    return render_template(
        "applicant/jobs.html",
        jobs=jobs,
        search=search,
        exp_filter=exp_filter,
        applied_map=applied_map,
    )


@bp.route("/jobs/<int:job_id>")
def job_details(job_id):
    """View full details of an open job (publicly accessible)."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    user_application = None
    if current_user.is_authenticated and current_user.is_applicant():
        user_application = Application.query.filter_by(
            applicant_id=current_user.id, job_id=job.id
        ).first()

    return render_template(
        "applicant/job_details.html",
        job=job,
        user_application=user_application,
    )


# ---------------------------------------------------------------------
# Apply to Job
# ---------------------------------------------------------------------
@bp.route("/jobs/<int:job_id>/apply", methods=["POST"])
@login_required
@applicant_required
def apply_job(job_id):
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    if job.status != "open":
        flash("This job is currently closed and no longer accepting applications.", "warning")
        return redirect(url_for("applicant.browse_jobs"))

    # Check if already applied
    existing = Application.query.filter_by(
        applicant_id=current_user.id, job_id=job.id
    ).first()
    if existing:
        flash("You have already submitted an application for this position.", "info")
        return redirect(url_for("applicant.dashboard"))

    # Check file upload
    if "resume" not in request.files:
        flash("Please select a resume file to upload.", "danger")
        return redirect(url_for("applicant.job_details", job_id=job.id))

    file = request.files["resume"]
    if file.filename == "":
        flash("No file selected. Please choose a PDF or DOCX resume.", "danger")
        return redirect(url_for("applicant.job_details", job_id=job.id))

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        flash("Unsupported file format. Only PDF and DOCX files are accepted.", "danger")
        return redirect(url_for("applicant.job_details", job_id=job.id))

    # Save file with unique name
    unique_filename = f"user_{current_user.id}_job_{job.id}_{uuid.uuid4().hex[:8]}_{filename}"
    upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
    file.save(upload_path)

    # Extract raw resume text (PyMuPDF / python-docx)
    extracted_text = extract_resume_text(upload_path)

    # Run AI Screening Pipeline
    parsed_info = parse_resume(extracted_text)
    scoring_result = score_candidate(job, extracted_text, parsed_info)
    # ONE unified AI call per application: generates 10 interview questions and structured feedback
    insights = generate_application_insights(job, extracted_text, parsed_info)

    # Create Application record
    application = Application(
        applicant_id=current_user.id,
        job_id=job.id,
        resume_filename=unique_filename,
        resume_text=extracted_text,
        parsed_data=json.dumps(parsed_info),
        match_score=scoring_result.get("match_score", 0),
        score_explanation=scoring_result.get("explanation", ""),
        interview_questions=json.dumps([q.model_dump() for q in insights.interview_questions]),
        resume_feedback=json.dumps(insights.resume_feedback.model_dump()),
        status="pending",
    )
    db.session.add(application)
    db.session.commit()

    # Trigger email notifications (to candidate and recruiter)
    try:
        send_application_received(current_user.email, current_user.name, job.title)
        if job.recruiter and job.recruiter.email:
            send_recruiter_new_applicant_alert(
                job.recruiter.email,
                job.recruiter.name,
                current_user.name,
                job.title,
                application.match_score,
            )
    except Exception as e:
        print(f"[SmartHire] Email notification error: {e}")

    flash(
        f'Congratulations! Your application for "{job.title}" has been submitted and screened by AI. '
        f'Check your dashboard to view instant personalized feedback & interview prep!',
        "success",
    )
    return redirect(url_for("applicant.dashboard"))


# ---------------------------------------------------------------------
# Phase 6: Applicant AI Feedback & Interview Prep
# ---------------------------------------------------------------------
@bp.route("/applications/<int:app_id>/feedback")
@login_required
@applicant_required
def application_feedback(app_id):
    """View detailed AI screening breakdown and actionable resume improvement feedback."""
    application = db.session.get(Application, app_id)
    if not application:
        abort(404)
    if application.applicant_id != current_user.id:
        abort(403)

    parsed = application.get_parsed_dict()
    job_skills = application.job.get_skills_list()
    candidate_skills = parsed.get("skills", [])

    # Normalize skills for comparison
    candidate_skills_lower = {s.lower() for s in candidate_skills}
    matched_skills = [s for s in job_skills if s.lower() in candidate_skills_lower]
    missing_skills = [s for s in job_skills if s.lower() not in candidate_skills_lower]

    # Generate insights on-demand if empty (ONE unified AI call)
    if not application.resume_feedback or not application.interview_questions:
        try:
            process_application_insights(application)
        except Exception as e:
            print(f"[SmartHire] Insights generation error: {type(e).__name__}")

    # Structured resume feedback dictionary (never includes interview questions)
    feedback_data = application.get_resume_feedback_data()

    # Score status label & styling
    score = application.match_score if application.match_score >= 0 else 0
    if score >= 80:
        score_level = "Strong Match"
        score_theme = "success"
    elif score >= 55:
        score_level = "Good Match"
        score_theme = "primary"
    elif score >= 35:
        score_level = "Moderate Match"
        score_theme = "warning"
    else:
        score_level = "Needs Development"
        score_theme = "danger"

    return render_template(
        "applicant/feedback.html",
        application=application,
        job=application.job,
        parsed=parsed,
        job_skills=job_skills,
        candidate_skills=candidate_skills,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        feedback=feedback_data,
        score_level=score_level,
        score_theme=score_theme,
    )
