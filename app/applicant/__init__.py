from flask import Blueprint

bp = Blueprint("applicant", __name__, template_folder="../templates")

from app.applicant import routes  # noqa: E402, F401
