# ⚡ SmartHire — AI-Powered Resume Screening & Recruitment Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black.svg)](https://palletsprojects.com/p/flask/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple.svg)](https://getbootstrap.com/)
[![Tests](https://img.shields.io/badge/Tests-5%20Passed%20(Pytest)-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**SmartHire** is a full-stack, enterprise-grade automated recruitment platform built with **Python/Flask**, **Bootstrap 5**, and a **Unified AI Screening & Insights Engine** (Google Gemini 2.5 Flash &rarr; Groq LLaMA 3.3 70B &rarr; Intelligent Heuristic Fallback).

Designed to streamline technical talent acquisition, eliminate manual resume bottlenecks, generate tailored interview questions for recruiters, and provide candidates with transparent, actionable resume feedback.

---

## 🌟 Key Platform Capabilities

### 1. Unified 1-Call AI Insights Engine
- **Single AI Call Per Application**: Both tailored interview questions and structured candidate feedback are generated in one unified inference call to avoid rate limits.
- **Pydantic Output Validation**: Strict schema enforcement (`ApplicationInsights`, `InterviewQuestion`, `ResumeFeedback`) with automated 1-attempt retry on malformed JSON.
- **Prompt Injection Defense**: Resume data is sanitized (omitting PII such as name and contact info) and isolated inside `<resume_data>` tags with explicit untrusted data instructions.
- **Graceful Multi-Tier Fallback**: Queries **Google Gemini** first, automatically falls back to **Groq LLaMA 3.3**, and defaults to an **Intelligent Heuristic Engine** if APIs are unconfigured or down.

### 2. Recruiter Command Center
- **Job Lifecycle Management**: Create, edit, close/reopen, and delete job postings with customizable skill tags and minimum experience requirements.
- **Candidate Review & Extraction Drawer**: Instant review of candidate resumes with extracted contact info, skills matrix, education, and experience.
- **10 Tailored Interview Questions (Shortlisted Only)**:
  - **4 Technical Deep-Dive** questions testing claimed tech stack and architecture.
  - **2 Skill Gap Probes** targeting missing required competencies.
  - **1 Project Deep-Dive** probing real-world project deliverables.
  - **3 Behavioral & Cultural Fit** questions evaluating collaboration and leadership.
  - Includes difficulty levels and key signals / good answer points for hiring managers.
- **One-Click Candidate Export**: Export ranked applicant lists to formatted **CSV** and styled **PDF reports** via ReportLab.

### 3. Applicant Portal & Actionable AI Feedback
- **Resume Upload & Parsing**: Native text extraction supporting **PDF** (`PyMuPDF`) and **DOCX** (`python-docx`) files.
- **Objective Match Scoring**: Evaluates candidate experience, technical skills, and domain projects against job requirements for an objective **0–100% Match Score**.
- **Actionable AI Resume Advice**:
  - Executive Feedback Summary.
  - Missing Keywords Cloud (skills present in job description but missing from resume).
  - Prioritized Action Items with numbered step recommendations.
  - Section-by-Section Enhancement Tips (Summary, Experience, Skills, Projects).
  - High-Impact Rewritten Bullet Examples based strictly on the candidate's own text.
- **Strict Privacy**: Applicants only see their resume feedback; interview questions remain strictly confidential to the recruiter.

### 4. Automated Daily Recruiter Digest & Email Alerts
- **Background Scheduler**: Automated background cron thread (`app/scheduler.py`) sends daily digest emails to recruiters summarizing new applications, candidate scores, and activity across the last 24 hours.
- **Event-Driven Notifications**: Instant transactional emails delivered when:
  - An application is successfully submitted.
  - Candidate status is updated to **Shortlisted**, **On Hold**, or **Rejected**.
- **Zero-Latency Async Mailer**: Background threading ensures email sending never blocks HTTP request lifecycles.

### 5. Administrator Control Center
- Platform-wide telemetry: total accounts, active jobs, submissions, and conversion funnel analytics.
- User management: search, filter, promote/demote roles, and account moderation.
- Global application audits and resume inspection.
- Custom branded HTTP error pages (403 Forbidden, 404 Not Found, 413 File Too Large, 500 Server Error).

---

## 🏗️ Architecture & Project Structure

```
smarthire/
├── app/
│   ├── admin/               # Administrator Blueprint & System Moderation
│   ├── ai/                  # AI Engine (Gemini, Groq, Prompts & Pydantic Schemas)
│   ├── applicant/           # Applicant Routes, Job Board & AI Resume Advice
│   ├── auth/                # Authentication, Registration & Notification Center
│   ├── recruiter/           # Recruiter Dashboard, Candidate Drawers & Shortlisting
│   ├── static/              # CSS Stylesheets, JS & SVG Icons
│   ├── templates/           # Jinja2 Templates (Strictly HTML-escaped, no |safe)
│   ├── extensions.py        # SQLAlchemy & Flask-Login instances
│   ├── mailer.py            # Transactional & Daily Digest SMTP Mailer
│   ├── models.py            # User, Job, and Application Database Models
│   ├── parser.py            # PDF / DOCX Resume Text Extraction
│   ├── reports.py           # CSV & PDF Export Generator (ReportLab)
│   ├── scheduler.py         # Automated 24h Recruiter Digest Scheduler
│   └── __init__.py          # Flask Application Factory
├── prompts/
│   └── insights_v1.txt      # Master AI Prompt Template with <resume_data> guard
├── tests/
│   ├── conftest.py          # Pytest Fixtures with In-Memory SQLite Isolation
│   └── test_insights.py     # Comprehensive Unit & Access-Control Test Suite
├── uploads/                 # Uploaded Candidate Resumes (.gitkeep preserved)
├── .env.example             # Template for Environment Configuration
├── .gitignore               # Production Git Rules (Excludes .env, DB, Resumes)
├── config.py                # Environment Configuration & Database URL Resolver
├── Procfile                 # Production WSGI Runner (Gunicorn)
├── requirements.txt         # Pinned Production Dependencies
├── run.py                   # Local & Cloud Server Entry Point
└── runtime.txt              # Target Python Runtime Version
```

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- **Python 3.10+** (Python 3.12 or 3.13 recommended)
- **pip** and **git**

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/smarthire.git
cd smarthire
```

### 3. Create a Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys (all keys are optional; the application automatically runs intelligent heuristics if omitted):
```env
SECRET_KEY=your-random-secret-key-32-chars
FLASK_DEBUG=1

# Database (Default: local SQLite database)
DATABASE_URL=sqlite:///instance/smarthire.db

# AI Engine API Keys
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here

# Gmail SMTP Email Notifications (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER="SmartHire <your-email@gmail.com>"
```

### 6. Run the Application
```bash
python run.py
```
Open your browser to: **`http://127.0.0.1:5000`**

---

## 🔑 Default Seeded Accounts

The platform automatically provisions default test accounts on first launch:

| Role | Email | Password | Dashboard URL |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@smarthire.com` | `admin123` | `/admin/dashboard` |
| **Recruiter** | `recruiter@example.com` | `password123` | `/recruiter/dashboard` |
| **Applicant** | `john.doe@example.com` | `password123` | `/applicant/dashboard` |

---

## 🧪 Running the Test Suite

SmartHire includes automated tests covering AI success, JSON retry loops, heuristic fallbacks, and multi-tenant access control:

```bash
python -m pytest -v tests/test_insights.py
```

**Test Coverage**:
- `test_ai_insights_success`: Verifies single AI call outputting 10 questions (4 technical, 2 gap probe, 1 project, 3 behavioral) and complete resume feedback.
- `test_ai_insights_invalid_json_retry`: Verifies 1-time automated retry upon receiving malformed JSON.
- `test_ai_insights_failure_fallback`: Verifies graceful fallback to offline heuristic generation when AI APIs timeout.
- `test_access_control_applicant_feedback`: Asserts applicant ownership, feedback visibility, interview questions privacy, and cross-user 403 blocks.
- `test_access_control_recruiter_questions`: Asserts recruiter ownership, hidden questions while pending, unlocked questions upon shortlisting, and unauthorized recruiter 403 blocks.

---

## 🌐 Production Deployment (Render Free Tier)

1. **Push Code to GitHub**:
   ```bash
   git add .
   git commit -m "Deploy SmartHire to production"
   git push origin main
   ```
2. **Create Web Service on Render**:
   - Go to [Render.com](https://render.com) and click **New + &rarr; Web Service**.
   - Select your GitHub repository.
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
   - **Instance Type**: `Free`
3. **Set Environment Variables on Render**:
   - In the Render dashboard, add `SECRET_KEY`, `FLASK_DEBUG=0`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `MAIL_USERNAME`, `MAIL_PASSWORD`, etc.
4. **Deploy**:
   - Click **Create Web Service**. Your application will be live at `https://smarthire-xxxx.onrender.com`.

---

## 🛡️ Security Highlights
- **No `|safe` rendering**: All user input, parsed resume text, and AI responses are automatically HTML-escaped by Jinja2 to prevent XSS.
- **Untrusted Prompt Isolation**: Candidate resume content is framed inside `<resume_data>` tags with explicit override prevention.
- **Sanitized Logging**: API keys and resume text are automatically redacted with regex filters before reaching log files.
- **Access Control Decorators**: `@recruiter_required`, `@applicant_required`, and ownership verification prevent IDOR (Insecure Direct Object Reference).

---

## 📄 License
This project is licensed under the MIT License.
