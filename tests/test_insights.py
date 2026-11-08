import json
import pytest
from unittest.mock import patch
from app.ai.engine import generate_application_insights, save_application_insights
from app.ai.schemas import ApplicationInsights
from app.models import Application, Job
from app.extensions import db


SAMPLE_VALID_AI_JSON = json.dumps({
    "interview_questions": [
        {
            "category": "technical",
            "question": "Explain how Flask handles request context.",
            "difficulty": "medium",
            "good_answer_points": ["AppContext vs RequestContext", "Thread-local proxies", "current_app and g"]
        },
        {
            "category": "technical",
            "question": "How do you optimize slow queries in PostgreSQL?",
            "difficulty": "hard",
            "good_answer_points": ["EXPLAIN ANALYZE", "Indexes (B-tree, GIN)", "Connection pooling"]
        },
        {
            "category": "technical",
            "question": "Describe the lifecycle of a Docker container.",
            "difficulty": "medium",
            "good_answer_points": ["Image layers", "cgroups and namespaces", "Multi-stage builds"]
        },
        {
            "category": "technical",
            "question": "How do you design REST APIs with proper idempotency?",
            "difficulty": "medium",
            "good_answer_points": ["HTTP methods", "Idempotency keys", "Status codes"]
        },
        {
            "category": "gap_probe",
            "question": "Your profile lacks CI/CD details. How have you automated deployments?",
            "difficulty": "medium",
            "good_answer_points": ["GitHub Actions or GitLab CI", "Automated test runs", "Zero-downtime rollouts"]
        },
        {
            "category": "gap_probe",
            "question": "How do you manage schema migrations with team collaboration?",
            "difficulty": "medium",
            "good_answer_points": ["Alembic / Flask-Migrate", "Backwards compatibility", "Rollback strategies"]
        },
        {
            "category": "project",
            "question": "Tell us about your Flask e-commerce API project.",
            "difficulty": "hard",
            "good_answer_points": ["Concurrency & locking", "Order processing reliability", "Payment gateway integration"]
        },
        {
            "category": "behavioral",
            "question": "Tell me about a time a production incident occurred under your watch.",
            "difficulty": "medium",
            "good_answer_points": ["Blameless post-mortem", "Quick mitigation", "Actionable root-cause fix"]
        },
        {
            "category": "behavioral",
            "question": "How do you resolve architectural disagreements with senior peers?",
            "difficulty": "medium",
            "good_answer_points": ["Data-driven benchmarks", "Prototyping trade-offs", "Disagree and commit"]
        },
        {
            "category": "behavioral",
            "question": "Describe how you prioritize technical debt versus feature velocity.",
            "difficulty": "medium",
            "good_answer_points": ["Business risk assessment", "Allocating sprint budget", "Refactoring critical paths"]
        }
    ],
    "resume_feedback": {
        "summary": "Solid backend profile with strong Python and Flask fundamentals.",
        "priority_actions": [
            "Explicitly list CI/CD pipeline experience.",
            "Quantify performance improvements with metrics.",
            "Highlight distributed caching (e.g., Redis)."
        ],
        "missing_keywords": ["CI/CD", "Redis", "Kafka", "Unit Testing"],
        "section_tips": {
            "summary": "Emphasize architectural leadership alongside hands-on development.",
            "experience": "Use Google-style XYZ formula (Accomplished X measured by Y by doing Z).",
            "skills": "Group technical tools by category (Languages, Databases, DevOps)."
        },
        "rewritten_bullets": [
            "Engineered high-throughput Flask e-commerce REST API reducing checkout latency by 35%.",
            "Architected PostgreSQL relational schemas supporting 100k+ daily queries with sub-50ms response times."
        ]
    }
})


# ---------------------------------------------------------------------
# Test 1: AI Insights Success (1 AI call, exactly 10 questions)
# ---------------------------------------------------------------------
def test_ai_insights_success(app, sample_job, sample_application):
    with app.app_context():
        with patch("app.ai.engine._call_ai_manager") as mock_ai:
            # Wrap response in Markdown JSON fences to test fence stripping as well
            mock_ai.return_value = f"```json\n{SAMPLE_VALID_AI_JSON}\n```"

            parsed = sample_application.get_parsed_dict()
            insights = generate_application_insights(sample_job, sample_application.resume_text, parsed)

            assert isinstance(insights, ApplicationInsights)
            assert len(insights.interview_questions) == 10

            categories = [q.category for q in insights.interview_questions]
            assert categories.count("technical") == 4
            assert categories.count("gap_probe") == 2
            assert categories.count("project") == 1
            assert categories.count("behavioral") == 3

            assert len(insights.resume_feedback.priority_actions) == 3
            assert "CI/CD" in insights.resume_feedback.missing_keywords
            assert len(insights.resume_feedback.rewritten_bullets) == 2

            # Test DB persistence
            db_app = db.session.get(Application, sample_application.id)
            save_application_insights(db_app, insights, app=app)

            # Reload and verify
            db.session.refresh(db_app)
            stored_qs = db_app.get_questions_list()
            assert len(stored_qs) == 10
            assert db_app.get_technical_questions()[0]["category"] == "technical"
            assert len(db_app.get_behavioral_questions()) == 3

            fb = db_app.get_resume_feedback_data()
            assert "Solid backend profile" in fb["summary"]
            assert len(fb["priority_actions"]) == 3
            assert mock_ai.call_count == 1


# ---------------------------------------------------------------------
# Test 2: Invalid JSON on first attempt, retry succeeds
# ---------------------------------------------------------------------
def test_ai_insights_invalid_json_retry(app, sample_job, sample_application):
    with app.app_context():
        with patch("app.ai.engine._call_ai_manager") as mock_ai:
            # Attempt 1: Corrupted JSON
            # Attempt 2: Valid JSON
            mock_ai.side_effect = [
                '{"interview_questions": [{"category": "invalid"}',  # Broken JSON
                SAMPLE_VALID_AI_JSON,
            ]

            parsed = sample_application.get_parsed_dict()
            insights = generate_application_insights(sample_job, sample_application.resume_text, parsed)

            assert mock_ai.call_count == 2
            assert isinstance(insights, ApplicationInsights)
            assert len(insights.interview_questions) == 10
            assert insights.resume_feedback.summary.startswith("Solid backend")


# ---------------------------------------------------------------------
# Test 3: Total AI failure triggers heuristic fallback with 10 questions
# ---------------------------------------------------------------------
def test_ai_insights_failure_fallback(app, sample_job, sample_application):
    with app.app_context():
        with patch("app.ai.engine._call_ai_manager") as mock_ai:
            mock_ai.side_effect = RuntimeError("API connection timeout or quota exhausted")

            parsed = sample_application.get_parsed_dict()
            insights = generate_application_insights(sample_job, sample_application.resume_text, parsed)

            assert isinstance(insights, ApplicationInsights)
            assert len(insights.interview_questions) == 10

            categories = [q.category for q in insights.interview_questions]
            assert categories.count("technical") == 4
            assert categories.count("gap_probe") == 2
            assert categories.count("project") == 1
            assert categories.count("behavioral") == 3

            assert len(insights.resume_feedback.priority_actions) >= 1
            assert len(insights.resume_feedback.rewritten_bullets) >= 1


# ---------------------------------------------------------------------
# Test 4: Access Control - Applicant Feedback
# ---------------------------------------------------------------------
def test_access_control_applicant_feedback(app, sample_application, applicant_user, other_applicant):
    with app.app_context():
        # Prepopulate application with insights
        db_app = db.session.get(Application, sample_application.id)
        parsed_insights = ApplicationInsights.model_validate_json(SAMPLE_VALID_AI_JSON)
        save_application_insights(db_app, parsed_insights)

    client = app.test_client()

    # 1. Login as the owner applicant: should succeed (200)
    client.post("/login", data={"email": applicant_user.email, "password": "pass123"}, follow_redirects=True)
    resp = client.get(f"/applicant/applications/{sample_application.id}/feedback")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Applicant SHOULD see their resume feedback
    assert "Actionable AI Resume Feedback" in html
    assert "Solid backend profile with strong Python" in html
    assert "Explicitly list CI/CD pipeline experience." in html

    # Applicant must NEVER see interview questions
    assert "Tailored Interview Questions for Candidate" not in html
    assert "Tailored Interview Guide" not in html
    assert "Explain how Flask handles request context." not in html

    # 2. Logout and login as another applicant: must be forbidden (403)
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"email": other_applicant.email, "password": "pass123"}, follow_redirects=True)
    resp2 = client.get(f"/applicant/applications/{sample_application.id}/feedback")
    assert resp2.status_code == 403


# ---------------------------------------------------------------------
# Test 5: Access Control - Recruiter Questions & Job Ownership
# ---------------------------------------------------------------------
def test_access_control_recruiter_questions(app, sample_job, sample_application, recruiter_user, other_recruiter):
    with app.app_context():
        # Prepopulate application with insights
        db_app = db.session.get(Application, sample_application.id)
        parsed_insights = ApplicationInsights.model_validate_json(SAMPLE_VALID_AI_JSON)
        save_application_insights(db_app, parsed_insights)

    client = app.test_client()

    # 1. Recruiter viewing applicants when application is PENDING:
    client.post("/login", data={"email": recruiter_user.email, "password": "pass123"}, follow_redirects=True)
    resp = client.get(f"/recruiter/jobs/{sample_job.id}/applicants")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # When pending, interview questions MUST be hidden behind shortlisted gate
    assert "Tailored interview questions will be revealed when this candidate is" in html
    assert "Explain how Flask handles request context." not in html

    # 2. Now SHORTLIST the candidate: questions should now be visible to the job's recruiter
    with app.app_context():
        db_app = db.session.get(Application, sample_application.id)
        db_app.status = "shortlisted"
        db.session.commit()

    resp2 = client.get(f"/recruiter/jobs/{sample_job.id}/applicants")
    assert resp2.status_code == 200
    html2 = resp2.get_data(as_text=True)

    # Questions are now visible
    assert "Tailored Interview Questions (10)" in html2
    assert "Explain how Flask handles request context." in html2
    assert "Technical Deep-Dive (4)" in html2
    assert "Skill Gap Probes (2)" in html2

    # 3. Logout and login as another recruiter who does NOT own the job: must be forbidden (403)
    client.get("/logout", follow_redirects=True)
    client.post("/login", data={"email": other_recruiter.email, "password": "pass123"}, follow_redirects=True)
    resp3 = client.get(f"/recruiter/jobs/{sample_job.id}/applicants")
    assert resp3.status_code == 403
