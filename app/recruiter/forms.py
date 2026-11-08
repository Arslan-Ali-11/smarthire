from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class JobForm(FlaskForm):
    title = StringField(
        "Job Title",
        validators=[DataRequired(), Length(min=3, max=200)],
        render_kw={"placeholder": "e.g. Junior Backend Developer"},
    )
    description = TextAreaField(
        "Job Description & Responsibilities",
        validators=[DataRequired(), Length(min=20)],
        render_kw={
            "rows": 6,
            "placeholder": "Describe the role, responsibilities, expectations, and any perks...",
        },
    )
    required_skills = StringField(
        "Required Skills (comma-separated)",
        validators=[DataRequired()],
        render_kw={"placeholder": "e.g. Python, Flask, SQLite, REST API, Git"},
    )
    min_experience_years = IntegerField(
        "Minimum Experience (Years)",
        validators=[NumberRange(min=0, max=50, message="Experience must be 0 or more.")],
        default=0,
        render_kw={"placeholder": "0"},
    )
    status = SelectField(
        "Posting Status",
        choices=[("open", "Open (Accepting Applications)"), ("closed", "Closed")],
        default="open",
    )
    submit = SubmitField("Save Job Posting")
