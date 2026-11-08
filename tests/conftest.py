import os
import sys

# Ensure smarthire package root is in python path
SMARTHIRE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SMARTHIRE_ROOT not in sys.path:
    sys.path.insert(0, SMARTHIRE_ROOT)

import pytest
from app import create_app
from app.extensions import db
from app.models import User, Job, Application
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"
    MAIL_SUPPRESS_SEND = True


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def recruiter_user(app):
    with app.app_context():
        user = User(
            name="Alice Recruiter",
            email="alice@techcorp.com",
            role="recruiter",
        )
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def other_recruiter(app):
    with app.app_context():
        user = User(
            name="Bob Recruiter",
            email="bob@othercorp.com",
            role="recruiter",
        )
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def applicant_user(app):
    with app.app_context():
        user = User(
            name="Charlie Applicant",
            email="charlie@gmail.com",
            role="applicant",
        )
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def other_applicant(app):
    with app.app_context():
        user = User(
            name="Dave Candidate",
            email="dave@gmail.com",
            role="applicant",
        )
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()
        return db.session.get(User, user.id)


@pytest.fixture
def sample_job(app, recruiter_user):
    with app.app_context():
        job = Job(
            title="Senior Python Backend Engineer",
            description="Seeking a Python engineer proficient in Flask, PostgreSQL, Docker, and REST APIs.",
            required_skills="Python, Flask, PostgreSQL, Docker, REST APIs",
            min_experience_years=4,
            status="open",
            recruiter_id=recruiter_user.id,
        )
        db.session.add(job)
        db.session.commit()
        return db.session.get(Job, job.id)


@pytest.fixture
def sample_application(app, sample_job, applicant_user):
    with app.app_context():
        import json
        app_obj = Application(
            job_id=sample_job.id,
            applicant_id=applicant_user.id,
            resume_filename="resume_test.pdf",
            resume_text="Charlie Applicant. 5 years building Python web services with Flask and PostgreSQL. Docker enthusiast.",
            parsed_data=json.dumps({
                "name": "Charlie Applicant",
                "email": "charlie@gmail.com",
                "phone": "555-0199",
                "skills": ["Python", "Flask", "PostgreSQL"],
                "experience_years": 5,
                "education": "B.S. in Computer Science",
                "projects": ["Built scalable Flask e-commerce API"],
            }),
            match_score=85,
            score_explanation="Strong background in core Python and Flask.",
            status="pending",
        )
        db.session.add(app_obj)
        db.session.commit()
        return db.session.get(Application, app_obj.id)
