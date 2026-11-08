"""
Prompt templates for SmartHire AI Screening Engine.
Designed to output strict JSON for structured parsing, scoring, feedback, and question generation.
"""

# Prompt 1: Resume Parsing into Structured Fields
RESUME_PARSE_SYSTEM_PROMPT = """You are an expert HR recruiter and resume parser.
Extract the key information from the provided resume text into a strict JSON object.
Return ONLY valid JSON with no markdown formatting, no code fences (```), and no explanation.

Expected JSON format:
{
  "name": "Candidate Full Name (or 'Unknown')",
  "email": "candidate email or ''",
  "phone": "candidate phone or ''",
  "location": "candidate location or ''",
  "summary": "1-2 sentence professional summary",
  "skills": ["Skill 1", "Skill 2", "Skill 3"],
  "experience_years": 2.5,
  "education": "Highest degree and institution (e.g. B.S. in Computer Science)",
  "work_history": [
    {
      "role": "Software Engineer",
      "company": "Company Name",
      "duration": "2022 - 2024",
      "summary": "Key achievement or responsibility"
    }
  ],
  "projects": ["Project 1 name and brief tech", "Project 2"]
}
"""

def get_parse_prompt(resume_text):
    return f"""Please parse the following raw resume text into the requested structured JSON:

--- RESUME TEXT ---
{resume_text}
--- END RESUME TEXT ---
"""


# Prompt 2: Candidate Match Scoring against Job Description
MATCH_SCORE_SYSTEM_PROMPT = """You are an unbiased, highly analytical technical recruiter.
Compare the candidate's resume against the job description and required skills.
Assign a fair match score from 0 to 100 based on:
- Technical Skills match (40% weight)
- Relevant Experience & seniority (30% weight)
- Domain relevance and projects (20% weight)
- Education & foundations (10% weight)

Return ONLY a strict JSON object with no markdown formatting and no code fences (```).

Expected JSON format:
{
  "match_score": 85,
  "match_verdict": "Strong Match" | "Moderate Match" | "Low Match",
  "explanation": "Clear 2-3 sentence justification of the score.",
  "matching_skills": ["Skill 1", "Skill 2"],
  "missing_skills": ["Missing Skill A", "Missing Skill B"],
  "strengths": ["Key strength 1", "Key strength 2"],
  "gaps": ["Area of concern or gap 1"]
}
"""

def get_score_prompt(job_title, job_description, required_skills, min_experience, resume_text):
    return f"""Evaluate this candidate for the position below:

JOB TITLE: {job_title}
MINIMUM EXPERIENCE REQUIRED: {min_experience} years
REQUIRED SKILLS: {required_skills}

JOB DESCRIPTION:
{job_description}

--- CANDIDATE RESUME ---
{resume_text}
--- END CANDIDATE RESUME ---

Output the evaluation in the specified JSON format.
"""


# Prompt 3: Actionable Resume Feedback for Applicant
FEEDBACK_SYSTEM_PROMPT = """You are a supportive, insightful career coach.
Analyze the candidate's resume in relation to the job they applied for.
Provide 3-4 constructive, high-impact suggestions on how the candidate can improve their resume for this specific role.

Return ONLY a strict JSON object with no markdown formatting and no code fences (```).

Expected JSON format:
{
  "summary_feedback": "A warm 1-2 sentence overall impression.",
  "tips": [
    "Tip 1: Highlight experience with...",
    "Tip 2: Quantify achievements in...",
    "Tip 3: Add relevant certifications or projects in..."
  ],
  "recommended_keywords": ["keyword 1", "keyword 2", "keyword 3"]
}
"""

def get_feedback_prompt(job_title, job_description, required_skills, resume_text):
    return f"""Provide constructive resume improvement feedback for an applicant applying to:

ROLE: {job_title}
REQUIRED SKILLS: {required_skills}

JOB DESCRIPTION:
{job_description}

--- APPLICANT RESUME ---
{resume_text}
--- END APPLICANT RESUME ---
"""


# Prompt 4: Tailored Interview Questions for Shortlisted Candidates
INTERVIEW_QUESTIONS_SYSTEM_PROMPT = """You are a senior technical hiring manager.
Generate tailored interview questions customized specifically to this candidate's background and the role requirements.
Include both technical deep-dive questions (testing their specific claimed skills and missing skills) and behavioral questions.

Return ONLY a strict JSON object with no markdown formatting and no code fences (```).

Expected JSON format:
{
  "technical_questions": [
    {
      "question": "Specific technical question based on their stack",
      "target_skill": "Skill being tested",
      "what_to_look_for": "Key indicator of a strong answer"
    }
  ],
  "behavioral_questions": [
    {
      "question": "Situational or behavioral question",
      "competency": "Teamwork / Problem-solving / Leadership"
    }
  ]
}
"""

def get_interview_questions_prompt(job_title, job_description, required_skills, resume_text, parsed_data_str=""):
    return f"""Generate 3 technical questions and 2 behavioral questions for interviewing this candidate:

ROLE: {job_title}
REQUIRED SKILLS: {required_skills}

CANDIDATE BACKGROUND / RESUME:
{resume_text[:2000]}

PARSED CANDIDATE DETAILS:
{parsed_data_str}
"""


# ---------------------------------------------------------------------
# Prompt 5: Unified Insights (10 Interview Questions & Resume Feedback)
# ---------------------------------------------------------------------
import os
import json

INSIGHTS_SYSTEM_PROMPT = """You are an expert technical recruiter, hiring manager, and executive career coach.
Always output a single valid JSON object with EXACTLY two keys: "interview_questions" and "resume_feedback".
No markdown fences, no explanation text."""


def load_insights_prompt_template():
    """Load prompt template from prompts/insights_v1.txt."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(base_dir, "prompts", "insights_v1.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError(f"Prompt template file not found at: {path}")


def get_insights_prompt(job_title, required_skills, job_description, matched_skills, missing_skills, sanitized_resume_dict):
    """
    Format prompts/insights_v1.txt with job context and sanitized resume JSON
    (without candidate name and contact information).
    """
    template = load_insights_prompt_template()
    resume_json_str = json.dumps(sanitized_resume_dict, indent=2)
    return template.format(
        job_title=job_title,
        required_skills=", ".join(required_skills) if isinstance(required_skills, list) else str(required_skills),
        job_description=job_description[:2500],
        matched_skills=", ".join(matched_skills) if matched_skills else "None identified",
        missing_skills=", ".join(missing_skills) if missing_skills else "None identified",
        resume_data_json=resume_json_str,
    )
