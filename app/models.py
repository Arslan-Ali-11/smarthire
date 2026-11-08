import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    """User model with role-based access (admin / recruiter / applicant)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'recruiter', or 'applicant'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    jobs = db.relationship("Job", backref="recruiter", lazy=True)
    applications = db.relationship("Application", backref="applicant", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"

    def is_recruiter(self):
        return self.role == "recruiter"

    def is_applicant(self):
        return self.role == "applicant"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Job(db.Model):
    """Job posting created by a recruiter."""

    id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text, nullable=False)  # JSON list stored as text
    min_experience_years = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="open")  # 'open' or 'closed'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    applications = db.relationship("Application", backref="job", lazy=True, cascade="all, delete-orphan")

    def get_skills_list(self):
        """Return required skills as a Python list."""
        if not self.required_skills:
            return []
        try:
            parsed = json.loads(self.required_skills)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [s.strip() for s in self.required_skills.split(",") if s.strip()]

    def set_skills_list(self, skills_list):
        """Save a list of skills as JSON."""
        if isinstance(skills_list, str):
            skills_list = [s.strip() for s in skills_list.split(",") if s.strip()]
        self.required_skills = json.dumps(skills_list)

    def is_open(self):
        return self.status == "open"

    def __repr__(self):
        return f"<Job {self.title}>"


class Application(db.Model):
    """An applicant's application to a specific job."""

    id = db.Column(db.Integer, primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    resume_filename = db.Column(db.String(255), nullable=False)
    resume_text = db.Column(db.Text, default="")  # Extracted raw text
    parsed_data = db.Column(db.Text, default="")  # JSON: name, skills, education, etc.
    match_score = db.Column(db.Integer, default=-1)  # 0-100, -1 = not scored yet
    score_explanation = db.Column(db.Text, default="")
    interview_questions = db.Column(db.Text, default="")  # JSON list
    resume_feedback = db.Column(db.Text, default="")  # AI improvement tips
    status = db.Column(db.String(20), default="pending")  # pending | shortlisted | rejected | on_hold
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Unique constraint: one application per applicant per job
    __table_args__ = (db.UniqueConstraint("applicant_id", "job_id", name="uq_applicant_job"),)

    def get_parsed_dict(self):
        """Return parsed resume data as a dictionary."""
        if not self.parsed_data:
            return {}
        try:
            return json.loads(self.parsed_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_questions_list(self):
        """Return list of interview question dictionaries."""
        if not self.interview_questions:
            return []
        try:
            data = json.loads(self.interview_questions)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Legacy dictionary structure support
                combined = []
                for q in data.get("technical_questions", []):
                    if isinstance(q, dict):
                        q.setdefault("category", "technical")
                        q.setdefault("difficulty", "medium")
                        q.setdefault("good_answer_points", [q.get("what_to_look_for", "")] if q.get("what_to_look_for") else [])
                        combined.append(q)
                for q in data.get("behavioral_questions", []):
                    if isinstance(q, dict):
                        q.setdefault("category", "behavioral")
                        q.setdefault("difficulty", "medium")
                        q.setdefault("good_answer_points", [f"Competency: {q.get('competency', '')}"] if q.get("competency") else [])
                        combined.append(q)
                return combined
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_interview_questions_data(self):
        """Return interview questions dictionary grouped by category."""
        questions = self.get_questions_list()
        return {
            "all_questions": questions,
            "technical_questions": [q for q in questions if q.get("category") == "technical"],
            "gap_probe_questions": [q for q in questions if q.get("category") == "gap_probe"],
            "project_questions": [q for q in questions if q.get("category") == "project"],
            "behavioral_questions": [q for q in questions if q.get("category") == "behavioral"],
        }

    def get_technical_questions(self):
        """Return technical deep-dive questions."""
        return [q for q in self.get_questions_list() if q.get("category") == "technical"]

    def get_gap_probe_questions(self):
        """Return skill gap probe questions."""
        return [q for q in self.get_questions_list() if q.get("category") == "gap_probe"]

    def get_project_questions(self):
        """Return project deep-dive questions."""
        return [q for q in self.get_questions_list() if q.get("category") == "project"]

    def get_behavioral_questions(self):
        """Return behavioral and situational interview questions."""
        return [q for q in self.get_questions_list() if q.get("category") == "behavioral"]

    def get_resume_feedback_data(self):
        """Return resume feedback as a structured dictionary."""
        if not self.resume_feedback:
            return {}
        try:
            data = json.loads(self.resume_feedback)
            if isinstance(data, dict):
                return data
            return {
                "summary": str(self.resume_feedback),
                "priority_actions": [],
                "missing_keywords": [],
                "section_tips": {},
                "rewritten_bullets": [],
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "summary": str(self.resume_feedback),
                "priority_actions": [],
                "missing_keywords": [],
                "section_tips": {},
                "rewritten_bullets": [],
            }

    def status_badge_class(self):
        badges = {
            "pending": "warning",
            "shortlisted": "success",
            "rejected": "danger",
            "on_hold": "secondary",
        }
        return badges.get(self.status, "info")

    def get_display_filename(self):
        """Return clean, original filename without server storage prefix."""
        if not self.resume_filename:
            return "Resume"
        # Prefixes look like: user_1_job_1_753601c6_OriginalName.docx
        parts = self.resume_filename.split("_", 5)
        if len(parts) == 6:
            return parts[5]
        return self.resume_filename

    def get_resume_extension(self):
        """Return normalized file extension without dot ('pdf' or 'docx')."""
        if not self.resume_filename:
            return ""
        return self.resume_filename.rsplit(".", 1)[-1].lower()

    def __repr__(self):
        return f"<Application user={self.applicant_id} job={self.job_id} score={self.match_score}>"


class EmailLog(db.Model):
    """Tracks all outgoing system emails for in-app verification, notifications, and auditing."""

    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False, index=True)
    recipient_name = db.Column(db.String(120), default="")
    subject = db.Column(db.String(255), nullable=False)
    headline = db.Column(db.String(255), default="")
    badge_text = db.Column(db.String(100), default="")
    status = db.Column(db.String(50), default="sent")  # 'delivered', 'simulated', 'failed'
    details = db.Column(db.Text, default="")
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<EmailLog to={self.recipient_email} subject='{self.subject}' status={self.status}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
