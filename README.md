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


## 📄 License
This project is licensed under the MIT License.
