from flask import Blueprint

bp = Blueprint("recruiter", __name__, template_folder="../templates")

from app.recruiter import routes  # noqa: E402, F401
