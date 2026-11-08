"""
Unified AI Screening & Scoring Engine for SmartHire.
Orchestrates: Gemini (Primary) -> Groq (Fallback) -> Intelligent Heuristic (Offline).
"""
import re
import json
import logging
from app.ai.prompts import (
    RESUME_PARSE_SYSTEM_PROMPT,
    get_parse_prompt,
    MATCH_SCORE_SYSTEM_PROMPT,
    get_score_prompt,
    FEEDBACK_SYSTEM_PROMPT,
    get_feedback_prompt,
    INTERVIEW_QUESTIONS_SYSTEM_PROMPT,
    get_interview_questions_prompt,
    INSIGHTS_SYSTEM_PROMPT,
    get_insights_prompt,
)
from app.ai.gemini_client import call_gemini
from app.ai.groq_client import call_groq
from app.ai.schemas import ApplicationInsights, InterviewQuestion, ResumeFeedback, strip_json_fences

logger = logging.getLogger("smarthire.ai")


def call_ai(system_prompt, user_prompt, fallback_func=None, *args, **kwargs):
    """
    Execute AI call with 3-tier fallback:
    1. Google Gemini API (Free tier)
    2. Groq API (Free fallback)
    3. Heuristic / Local Fallback
    """
    # Tier 1: Gemini
    result = call_gemini(system_prompt, user_prompt)
    if result:
        return result, "Gemini AI"

    # Tier 2: Groq
    result = call_groq(system_prompt, user_prompt)
    if result:
        return result, "Groq AI"

    # Tier 3: Heuristic Fallback
    if fallback_func:
        return fallback_func(*args, **kwargs), "SmartHire Heuristic Engine"

    return {}, "None"


# ---------------------------------------------------------------------
# 1. Resume Parsing
# ---------------------------------------------------------------------
def parse_resume(resume_text):
    """
    Parse raw resume text into structured fields:
    name, email, phone, skills, experience_years, education, projects.
    """
    if not resume_text or not resume_text.strip():
        return heuristic_parse_resume("")

    sys_prompt = RESUME_PARSE_SYSTEM_PROMPT
    user_prompt = get_parse_prompt(resume_text[:4000])

    data, source = call_ai(sys_prompt, user_prompt, fallback_func=heuristic_parse_resume, resume_text=resume_text)
    data["_ai_source"] = source
    return data


# ---------------------------------------------------------------------
# 2. Candidate Match Scoring
# ---------------------------------------------------------------------
def score_candidate(job, resume_text, parsed_data=None):
    """
    Compare candidate resume against job description & required skills.
    Returns:
    {
      "match_score": 85,
      "explanation": "...",
      "matching_skills": [...],
      "missing_skills": [...],
      "strengths": [...],
      "gaps": [...]
    }
    """
    skills_list = job.get_skills_list()
    skills_str = ", ".join(skills_list) if skills_list else "Not specified"

    sys_prompt = MATCH_SCORE_SYSTEM_PROMPT
    user_prompt = get_score_prompt(
        job_title=job.title,
        job_description=job.description[:2500],
        required_skills=skills_str,
        min_experience=job.min_experience_years,
        resume_text=resume_text[:3500],
    )

    result, source = call_ai(
        sys_prompt,
        user_prompt,
        fallback_func=heuristic_score_candidate,
        job=job,
        resume_text=resume_text,
        parsed_data=parsed_data,
    )
    result["_ai_source"] = source
    return result


# ---------------------------------------------------------------------
# 3. Unified Insights Generation (Interview Questions & Resume Feedback)
# ---------------------------------------------------------------------
def _call_ai_manager(system_prompt, user_prompt):
    """
    Query existing AI manager: Gemini first, then Groq fallback.
    Returns parsed dictionary or None.
    """
    # 1. Try Google Gemini API
    try:
        res = call_gemini(system_prompt, user_prompt)
        if res:
            return res
    except Exception as e:
        logger.error(f"[AI Manager] Gemini attempt error: {type(e).__name__}")

    # 2. Try Groq API Fallback
    try:
        res = call_groq(system_prompt, user_prompt)
        if res:
            return res
    except Exception as e:
        logger.error(f"[AI Manager] Groq attempt error: {type(e).__name__}")

    return None


def generate_application_insights(job, resume_text, parsed_data=None):
    """
    Generate unified interview questions (10 items) and resume feedback
    using ONE single AI call per application.
    Validates output with Pydantic (ApplicationInsights). Retries once on invalid JSON/validation failure.
    Falls back to intelligent heuristic generation if AI fails.
    """
    # 1. Sanitize resume data (omit name and contact per security instructions)
    sanitized_resume_data = {}
    if parsed_data and isinstance(parsed_data, dict):
        for k, v in parsed_data.items():
            if k.lower() not in ("name", "email", "phone", "contact", "_ai_source"):
                sanitized_resume_data[k] = v
    else:
        sanitized_resume_data = {
            "summary": "Candidate profile",
            "skills": job.get_skills_list()[:3] if hasattr(job, "get_skills_list") else [],
        }

    job_skills = job.get_skills_list() if hasattr(job, "get_skills_list") else []
    cand_skills = sanitized_resume_data.get("skills", [])
    cand_skills_lower = {s.lower() for s in cand_skills} if isinstance(cand_skills, list) else set()
    matched_skills = [s for s in job_skills if s.lower() in cand_skills_lower]
    missing_skills = [s for s in job_skills if s.lower() not in cand_skills_lower]

    try:
        user_prompt = get_insights_prompt(
            job_title=job.title,
            required_skills=job_skills,
            job_description=job.description,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            sanitized_resume_dict=sanitized_resume_data,
        )
    except Exception as e:
        logger.error(f"[AI Insights] Error preparing prompt: {type(e).__name__}")
        return heuristic_application_insights(job, resume_text, parsed_data)

    # Attempt 1: Call AI Manager
    raw_response = None
    try:
        raw_response = _call_ai_manager(INSIGHTS_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning(f"[AI Insights] Call attempt 1 raised exception: {type(e).__name__}")

    if raw_response is not None:
        try:
            cleaned = strip_json_fences(raw_response)
            data = json.loads(cleaned) if isinstance(cleaned, str) else cleaned
            insights = ApplicationInsights.model_validate(data)
            return insights
        except Exception as e1:
            logger.warning(f"[AI Insights] Validation failed on attempt 1 ({type(e1).__name__}). Retrying once...")

    # Attempt 2: Retry once with explicit clarification
    retry_prompt = (
        user_prompt
        + "\n\nCRITICAL RETRY: Your previous response was invalid. Return ONLY strict valid JSON adhering to schema with 'interview_questions' (10 items) and 'resume_feedback'."
    )
    raw_response_retry = None
    try:
        raw_response_retry = _call_ai_manager(INSIGHTS_SYSTEM_PROMPT, retry_prompt)
    except Exception as e:
        logger.warning(f"[AI Insights] Call attempt 2 raised exception: {type(e).__name__}")

    if raw_response_retry is not None:
        try:
            cleaned = strip_json_fences(raw_response_retry)
            data = json.loads(cleaned) if isinstance(cleaned, str) else cleaned
            insights = ApplicationInsights.model_validate(data)
            return insights
        except Exception as e2:
            logger.warning(f"[AI Insights] Validation failed on attempt 2 ({type(e2).__name__}). Falling back to heuristic.")

    # Fallback to intelligent heuristic if AI is unconfigured or failed
    logger.info("[AI Insights] Generating compliant heuristic application insights.")
    return heuristic_application_insights(job, resume_text, parsed_data)


def save_application_insights(application, insights, app=None):
    """
    Persist unified insights into Application.interview_questions and
    Application.resume_feedback, safely committing within app_context.
    """
    if app is None:
        try:
            from flask import current_app
            app = current_app._get_current_object()
        except RuntimeError:
            app = None

    def _save():
        from app.extensions import db
        target_app = application
        if hasattr(application, "id") and application.id:
            db_obj = db.session.get(application.__class__, application.id)
            if db_obj:
                target_app = db_obj

        # 10 interview questions as JSON array
        q_list = [q.model_dump() for q in insights.interview_questions]
        target_app.interview_questions = json.dumps(q_list)
        application.interview_questions = target_app.interview_questions

        # Resume feedback as JSON object
        fb_dict = insights.resume_feedback.model_dump()
        target_app.resume_feedback = json.dumps(fb_dict)
        application.resume_feedback = target_app.resume_feedback

        db.session.commit()

    if app is not None:
        with app.app_context():
            _save()
    else:
        _save()


def process_application_insights(application, app=None):
    """
    Helper to generate and save insights for an application in one single AI call.
    """
    parsed = application.get_parsed_dict()
    insights = generate_application_insights(application.job, application.resume_text, parsed)
    save_application_insights(application, insights, app=app)
    return insights


def generate_resume_feedback(job, resume_text):
    """Legacy helper: returns summary string from unified insights."""
    insights = generate_application_insights(job, resume_text)
    return json.dumps(insights.resume_feedback.model_dump())


def generate_interview_questions(job, resume_text, parsed_data=None):
    """Legacy helper: returns interview questions from unified insights."""
    insights = generate_application_insights(job, resume_text, parsed_data)
    return [q.model_dump() for q in insights.interview_questions]


# =====================================================================
# Intelligent Heuristic Fallback Implementations
# =====================================================================

COMMON_SKILLS_DICTIONARY = [
    "Python", "JavaScript", "TypeScript", "HTML", "CSS", "SQL", "SQLite", "PostgreSQL",
    "MySQL", "MongoDB", "Flask", "Django", "FastAPI", "React", "Vue", "Angular",
    "Node.js", "Express", "Docker", "Kubernetes", "Git", "GitHub", "REST API",
    "GraphQL", "AWS", "Azure", "GCP", "Linux", "CI/CD", "Machine Learning",
    "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-Learn",
    "Java", "C++", "C#", "Go", "Rust", "PHP", "Tailwind", "Bootstrap", "Next.js"
]


def heuristic_parse_resume(resume_text):
    """Local parser extracting skills, contact, and experience using regex heuristics."""
    text_lower = resume_text.lower() if resume_text else ""

    # Extract email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", resume_text)
    email = email_match.group(0) if email_match else ""

    # Extract phone
    phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}", resume_text)
    phone = phone_match.group(0) if phone_match else ""

    # Extract skills
    found_skills = []
    for skill in COMMON_SKILLS_DICTIONARY:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found_skills.append(skill)

    # Extract experience years
    exp_years = 1.0
    exp_matches = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?", text_lower)
    if exp_matches:
        try:
            exp_years = max(float(m) for m in exp_matches[:3])
        except ValueError:
            pass

    # Extract education level
    education = "University Degree"
    if "master" in text_lower or "m.s." in text_lower or "ms " in text_lower:
        education = "Master's Degree"
    elif "bachelor" in text_lower or "b.s." in text_lower or "bs " in text_lower or "b.tech" in text_lower:
        education = "Bachelor's in Computer Science / Engineering"
    elif "phd" in text_lower or "doctorate" in text_lower:
        education = "Ph.D."

    return {
        "name": "Applicant",
        "email": email,
        "phone": phone,
        "location": "",
        "summary": "Technical professional with hands-on software development experience.",
        "skills": found_skills,
        "experience_years": exp_years,
        "education": education,
        "projects": [f"Demonstrated projects utilizing {', '.join(found_skills[:3])}"] if found_skills else [],
    }


def heuristic_score_candidate(job, resume_text, parsed_data=None):
    """Calculates an accurate match score (0-100) using skill overlap & experience comparison."""
    if not parsed_data:
        parsed_data = heuristic_parse_resume(resume_text)

    candidate_skills = {s.lower() for s in parsed_data.get("skills", [])}
    required_skills = [s.strip() for s in job.get_skills_list()]

    matched = []
    missing = []

    text_lower = resume_text.lower()
    for req in required_skills:
        req_clean = req.lower()
        if req_clean in candidate_skills or req_clean in text_lower:
            matched.append(req)
        else:
            missing.append(req)

    # Skill match ratio (max 65 pts)
    total_req = max(len(required_skills), 1)
    skill_score = (len(matched) / total_req) * 65

    # Experience match ratio (max 25 pts)
    cand_exp = parsed_data.get("experience_years", 1.0)
    req_exp = max(job.min_experience_years, 0)

    if req_exp == 0 or cand_exp >= req_exp:
        exp_score = 25
    else:
        exp_score = max(5, int((cand_exp / req_exp) * 25))

    # Base education & completeness (10 pts)
    base_score = 10

    total_score = min(100, int(round(skill_score + exp_score + base_score)))

    # Generate clear explanation
    if total_score >= 80:
        verdict = "Strong Match"
        exp_msg = f"Strong candidate: matches {len(matched)} of {total_req} required skills ({', '.join(matched[:4])}) with {cand_exp} years relevant experience."
    elif total_score >= 60:
        verdict = "Moderate Match"
        exp_msg = f"Good foundational profile: possesses key skills in {', '.join(matched[:3]) if matched else 'core areas'}, but lacks {', '.join(missing[:3])}."
    else:
        verdict = "Low Match"
        exp_msg = f"Limited overlap: missing critical skills ({', '.join(missing[:4])}) and requires additional domain experience."

    return {
        "match_score": total_score,
        "match_verdict": verdict,
        "explanation": exp_msg,
        "matching_skills": matched,
        "missing_skills": missing,
        "strengths": [f"Demonstrated background in {s}" for s in matched[:3]],
        "gaps": [f"Missing required experience in {s}" for s in missing[:3]],
    }


def heuristic_generate_feedback(job, resume_text):
    """Provides actionable advice based on missing required skills."""
    required = job.get_skills_list()
    text_lower = resume_text.lower()
    missing = [s for s in required if s.lower() not in text_lower]

    tips = []
    if missing:
        tips.append(f"Emphasize experience with {', '.join(missing[:3])} in your project descriptions.")
    tips.append("Quantify your project outcomes using real metrics (e.g., 'improved query speed by 30%').")
    tips.append(f"Tailor your summary to highlight how your background solves the specific requirements of the {job.title} role.")

    return {
        "summary_feedback": f"Your resume has strong foundations. Addressing the skill gaps for {job.title} will boost your interview callback rate.",
        "tips": tips,
        "recommended_keywords": missing[:5] if missing else required[:5],
    }


def heuristic_interview_questions(job, parsed_data=None):
    """Generates targeted technical and behavioral questions."""
    job_skills = job.get_skills_list()
    tech_skills = job_skills[:3] if job_skills else ["Python", "System Design", "Database Modeling"]

    technical = []
    for skill in tech_skills:
        technical.append({
            "question": f"Can you describe a challenging project where you implemented {skill}? What architectural decisions and trade-offs did you make?",
            "target_skill": skill,
            "what_to_look_for": f"Deep understanding of {skill} patterns, error handling, and performance optimization.",
        })

    behavioral = [
        {
            "question": f"Tell me about a time when you had to learn a new tool or framework rapidly under a tight project deadline for a role like {job.title}.",
            "competency": "Adaptability & Problem Solving",
        },
        {
            "question": "Describe a situation where you disagreed with a teammate or stakeholder on an architectural approach. How did you reach consensus?",
            "competency": "Collaboration & Communication",
        },
    ]

    return {
        "technical_questions": technical,
        "behavioral_questions": behavioral,
    }


def heuristic_application_insights(job, resume_text, parsed_data=None):
    """
    Intelligent heuristic fallback that generates a fully validated ApplicationInsights
    object with exactly 10 questions (4 technical, 2 gap_probe, 1 project, 3 behavioral)
    and complete structured feedback if AI services are offline or fail.
    """
    job_skills = job.get_skills_list() if hasattr(job, "get_skills_list") else []
    cand_skills = parsed_data.get("skills", []) if parsed_data else []
    cand_skills_lower = {s.lower() for s in cand_skills} if isinstance(cand_skills, list) else set()
    matched = [s for s in job_skills if s.lower() in cand_skills_lower]
    missing = [s for s in job_skills if s.lower() not in cand_skills_lower]

    primary_tech = (matched + job_skills + ["System Architecture", "Database Modeling", "API Engineering"])[:4]
    while len(primary_tech) < 4:
        primary_tech.append(f"Core Stack {len(primary_tech)+1}")

    gap_tech = missing[:2] if missing else ["Production Deployment", "Scale & Observability"]
    while len(gap_tech) < 2:
        gap_tech.append(f"Domain Competency {len(gap_tech)+1}")

    project_list = parsed_data.get("projects", []) if parsed_data else []
    proj_name = project_list[0] if project_list else f"{job.title} Implementation"

    questions = [
        # 4 Technical Questions
        InterviewQuestion(
            category="technical",
            question=f"Can you explain the architectural decisions, trade-offs, and design patterns you used when building with {primary_tech[0]}?",
            difficulty="medium",
            good_answer_points=[
                f"Clear understanding of {primary_tech[0]} patterns and idiomatic practices",
                "Knowledge of performance bottlenecks and memory considerations",
                "Testing and error-handling strategies",
            ],
        ),
        InterviewQuestion(
            category="technical",
            question=f"How do you handle asynchronous operations, concurrency, and high load when utilizing {primary_tech[1]}?",
            difficulty="hard",
            good_answer_points=[
                "Concurrency primitives and thread safety",
                "Lock contention and async event loops",
                "Graceful degradation under heavy traffic",
            ],
        ),
        InterviewQuestion(
            category="technical",
            question=f"Describe your strategy for state management, data integrity, and caching when working with {primary_tech[2]}.",
            difficulty="medium",
            good_answer_points=[
                "Cache invalidation techniques (TTL vs write-through)",
                "ACID compliance and transaction boundaries",
                "Index tuning and query performance",
            ],
        ),
        InterviewQuestion(
            category="technical",
            question=f"What automated testing frameworks and CI/CD pipelines do you set up for applications written with {primary_tech[3]}?",
            difficulty="easy",
            good_answer_points=[
                "Unit test isolation and mocking external services",
                "Integration test harness reliability",
                "Static analysis and automated linting in pipelines",
            ],
        ),
        # 2 Gap Probe Questions
        InterviewQuestion(
            category="gap_probe",
            question=f"This role relies on {gap_tech[0]}. Although it isn't prominent in your recent CV, how would you quickly ramp up and solve a production issue with it?",
            difficulty="medium",
            good_answer_points=[
                "Structured self-learning methodology",
                "Proactive reading of official documentation and source code",
                "Transferable skills from analogous frameworks",
            ],
        ),
        InterviewQuestion(
            category="gap_probe",
            question=f"Have you evaluated or worked with {gap_tech[1]} in personal projects or open source? If not, what comparable framework have you used?",
            difficulty="medium",
            good_answer_points=[
                "Honest self-assessment of technical capabilities",
                "Hands-on willingness to build PoCs",
                "Analytical comparison with familiar alternatives",
            ],
        ),
        # 1 Project Question
        InterviewQuestion(
            category="project",
            question=f"Walk me through the end-to-end architecture of '{proj_name}'. What was your specific individual contribution, and what was the quantifiable outcome?",
            difficulty="medium",
            good_answer_points=[
                "Deep ownership of implementation details and trade-offs",
                "Measurable business or system performance metric achieved",
                "Post-mortem learnings and what they would do differently",
            ],
        ),
        # 3 Behavioral Questions
        InterviewQuestion(
            category="behavioral",
            question="Tell me about a time when a critical bug made it into production on a project with a tight deadline. How did you triage, resolve, and communicate it?",
            difficulty="medium",
            good_answer_points=[
                "Calm triage and root-cause analysis",
                "Clear, transparent communication with stakeholders",
                "Post-incident review and regression test prevention",
            ],
        ),
        InterviewQuestion(
            category="behavioral",
            question="Describe a situation where you had a strong technical disagreement with a teammate or lead. How did you handle the debate and reach consensus?",
            difficulty="medium",
            good_answer_points=[
                "Respectful and data-driven debate",
                "Active listening and openness to compromise",
                "Commitment to the final team consensus once decided",
            ],
        ),
        InterviewQuestion(
            category="behavioral",
            question="Can you give an example of how you mentored a junior colleague or onboarded a new engineer into a complex codebase?",
            difficulty="easy",
            good_answer_points=[
                "Empathy, patience, and clear technical communication",
                "Structured architectural walkthroughs and documentation",
                "Constructive and encouraging code review culture",
            ],
        ),
    ]

    resume_feedback = ResumeFeedback(
        summary=f"Your profile demonstrates solid technical foundations for the {job.title} position. Addressing identified keyword gaps and quantifying project achievements will noticeably boost your recruiter interview callbacks.",
        priority_actions=[
            f"Add explicit bullet points detailing your hands-on experience with {', '.join(missing[:3]) if missing else 'core system design'}." if missing else "Highlight system architecture and end-to-end delivery metrics.",
            "Quantify your bullet points using the Google X-Y-Z formula: 'Accomplished [X] as measured by [Y] by doing [Z]'.",
            "Front-load your most relevant technical stack in your summary and modern technical skills matrix.",
            "Include links to live project demos, GitHub repositories, or technical writing.",
        ],
        missing_keywords=missing[:6] if missing else job_skills[:5],
        section_tips={
            "summary": f"Tailor your 2-3 line summary specifically to target {job.title} requirements rather than a generic developer profile.",
            "experience": "Ensure each employment role highlights measurable latency improvements, revenue impact, or user scaling statistics.",
            "skills": f"Group skills into clear categories (Languages, Frameworks, Cloud/DevOps, Databases) and prioritize {', '.join(job_skills[:4])}.",
            "projects": "Highlight architecture, technical trade-offs, and production URL links for every showcased project.",
        },
        rewritten_bullets=[
            f"Architected and optimized backend services using {primary_tech[0]}, improving query response latency by 35% across 50,000+ daily active requests.",
            f"Engineered and automated end-to-end CI/CD test coverage utilizing {primary_tech[1]}, decreasing deployment cycle failures by 40%.",
        ],
    )

    return ApplicationInsights(interview_questions=questions, resume_feedback=resume_feedback)
