"""
SmartHire Automated Email Notification Service.
Sends transactional emails via SMTP (e.g. Gmail SMTP) with responsive HTML templates
and fallback plain text. Background threaded to ensure zero HTTP request latency.
"""
import smtplib
import threading
import logging
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("smarthire.mailer")


def _send_smtp(to_email, subject, html_content, text_content=None, headline=None, badge_text=None, app=None):
    """Internal SMTP sender executed in background thread."""
    if app is None:
        try:
            from flask import current_app
            app = current_app._get_current_object()
        except RuntimeError:
            try:
                from app import create_app
                app = create_app()
            except Exception:
                logger.error("No Flask application context available for mailer.")
                return False

    with app.app_context():
        from app.models import EmailLog
        from app.extensions import db

        mail_server = app.config.get("MAIL_SERVER", "smtp.gmail.com")
        mail_port = int(app.config.get("MAIL_PORT", 587))
        mail_use_tls = app.config.get("MAIL_USE_TLS", True)
        mail_username = app.config.get("MAIL_USERNAME", "").strip()
        mail_password = app.config.get("MAIL_PASSWORD", "").replace(" ", "").strip()
        sender = app.config.get("MAIL_DEFAULT_SENDER", f"SmartHire <{mail_username}>" if mail_username else "SmartHire <noreply@smarthire.local>")
        suppress_send = app.config.get("MAIL_SUPPRESS_SEND", False)

        # Re-check from environment if config was empty
        if not mail_username or not mail_password:
            import os
            from dotenv import load_dotenv
            load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)
            mail_username = os.environ.get("MAIL_USERNAME", "").strip()
            mail_password = os.environ.get("MAIL_PASSWORD", "").replace(" ", "").strip()
            if mail_username:
                sender = os.environ.get("MAIL_DEFAULT_SENDER", f"SmartHire <{mail_username}>")

        # Body snippet for preview
        body_preview = text_content if text_content else "Automated recruitment notification."

        if suppress_send or not mail_username or not mail_password:
            logger.info(
                f"[SmartHire Mailer (SIMULATED)] Email to '{to_email}' with subject '{subject}'. "
                f"(Credentials not configured or MAIL_SUPPRESS_SEND=True)"
            )
            try:
                log_entry = EmailLog(
                    recipient_email=to_email,
                    subject=subject,
                    headline=headline or "Notification",
                    badge_text=badge_text or "Automated",
                    status="simulated",
                    details=body_preview,
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as le:
                logger.error(f"Error saving EmailLog: {le}")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email

            if text_content:
                msg.attach(MIMEText(text_content, "plain", "utf-8"))
            if html_content:
                msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
                if mail_use_tls:
                    server.starttls()
                server.login(mail_username, mail_password)
                envelope_from = mail_username if mail_username else sender
                server.sendmail(envelope_from, [to_email], msg.as_string())

            logger.info(f"[SmartHire Mailer] Successfully sent email '{subject}' to {to_email}")

            try:
                log_entry = EmailLog(
                    recipient_email=to_email,
                    subject=subject,
                    headline=headline or "Notification",
                    badge_text=badge_text or "Delivered",
                    status="delivered",
                    details=body_preview,
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception as le:
                logger.error(f"Error saving EmailLog: {le}")
            return True
        except Exception as e:
            logger.error(f"[SmartHire Mailer] Failed to send email to {to_email}: {e}")

            try:
                log_entry = EmailLog(
                    recipient_email=to_email,
                    subject=subject,
                    headline=headline or "Notification",
                    badge_text=badge_text or "Failed",
                    status="failed",
                    details=f"SMTP Error: {e}\n\nMessage:\n{body_preview}",
                )
                db.session.add(log_entry)
                db.session.commit()
            except Exception:
                pass
            return False


def send_email_async(to_email, subject, html_content, text_content=None, headline=None, badge_text=None):
    """Trigger email delivery asynchronously in a background daemon thread."""
    try:
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        app = None

    thread = threading.Thread(
        target=_send_smtp,
        args=(to_email, subject, html_content, text_content, headline, badge_text, app),
        daemon=True,
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------
# HTML Template Builder
# ---------------------------------------------------------------------
def _build_email_html(headline, greeting, message_paragraphs, badge_text, badge_color="#3b82f6", action_btn_text=None, action_btn_url=None):
    """Generate consistent, branded responsive HTML email."""
    paragraphs_html = "".join([f"<p style='color: #cbd5e1; font-size: 15px; line-height: 1.6; margin: 12px 0;'>{p}</p>" for p in message_paragraphs])
    
    action_btn_html = ""
    if action_btn_text and action_btn_url:
        action_btn_html = f"""
        <div style="margin: 28px 0 16px 0; text-align: center;">
            <a href="{action_btn_url}" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                {action_btn_text}
            </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{headline}</title>
    </head>
    <body style="margin: 0; padding: 24px; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0">
            <tr>
                <td align="center">
                    <table width="600" border="0" cellspacing="0" cellpadding="0" style="background: #111827; border: 1px solid #1f2937; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 32px 36px; background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(17, 24, 39, 0) 100%); border-bottom: 1px solid #1f2937;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">⚡ Smart<span style="color: #60a5fa;">Hire</span></span>
                                </div>
                                <h1 style="color: #ffffff; font-size: 22px; font-weight: 700; margin: 16px 0 0 0;">{headline}</h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 36px;">
                                <div style="display: inline-block; padding: 4px 12px; background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}44; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 20px;">
                                    {badge_text}
                                </div>
                                <p style="color: #f1f5f9; font-size: 16px; font-weight: 600; margin: 0 0 16px 0;">{greeting}</p>
                                {paragraphs_html}
                                {action_btn_html}
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 24px 36px; background: #0d121f; border-top: 1px solid #1f2937; text-align: center;">
                                <p style="color: #64748b; font-size: 12px; margin: 0; line-height: 1.5;">
                                    This is an automated notification from <strong>SmartHire</strong> AI Recruitment Platform.<br>
                                    Please log in to your dashboard to view complete application progress and AI interview prep.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


# ---------------------------------------------------------------------
# Transactional Email Functions
# ---------------------------------------------------------------------
def send_application_received(applicant_email, applicant_name, job_title):
    """Sent when an applicant successfully submits a job application."""
    subject = f"Application Received: {job_title} - SmartHire"
    headline = "Application Received Successfully"
    greeting = f"Hello {applicant_name},"
    paragraphs = [
        f"Thank you for applying for the <strong>{job_title}</strong> position through SmartHire.",
        "Your application and resume have been securely received and processed by our AI screening engine.",
        "You can view personalized resume feedback and tailored interview prep suggestions directly in your applicant dashboard at any time.",
        "The hiring team will review your profile and update your status as hiring decisions progress.",
    ]
    html = _build_email_html(
        headline=headline,
        greeting=greeting,
        message_paragraphs=paragraphs,
        badge_text="Application Submitted",
        badge_color="#3b82f6",
        action_btn_text="View Applicant Dashboard",
        action_btn_url="http://127.0.0.1:5000/applicant/dashboard",
    )
    text = (
        f"Hello {applicant_name},\n\n"
        f"Thank you for applying for '{job_title}' on SmartHire.\n"
        "Your application and resume have been processed by our AI engine.\n"
        "Log in to your dashboard to track your application status:\n"
        "http://127.0.0.1:5000/applicant/dashboard\n\n"
        "— The SmartHire Team"
    )
    return send_email_async(applicant_email, subject, html, text, headline, "Application Received")


def send_recruiter_new_applicant_alert(recruiter_email, recruiter_name, applicant_name, job_title, match_score):
    """Sent to the recruiter when a candidate submits an application for their job posting."""
    subject = f"New Candidate: {applicant_name} applied for {job_title} ({match_score}% Match)"
    headline = "New Applicant Notification"
    greeting = f"Hello {recruiter_name},"
    paragraphs = [
        f"A new candidate, <strong>{applicant_name}</strong>, has submitted an application for your job posting: <strong>{job_title}</strong>.",
        f"SmartHire AI has screened the resume and calculated an initial <strong>Match Score of {match_score}%</strong>.",
        "Log in to your Recruiter Dashboard to review the full resume, inspect AI recommendations, and take action (Shortlist, Hold, or Reject).",
    ]
    html = _build_email_html(
        headline=headline,
        greeting=greeting,
        message_paragraphs=paragraphs,
        badge_text=f"AI Match: {match_score}%",
        badge_color="#3b82f6",
        action_btn_text="View Candidate in Recruiter Dashboard",
        action_btn_url="http://127.0.0.1:5000/recruiter/dashboard",
    )
    text = (
        f"Hello {recruiter_name},\n\n"
        f"A new candidate, {applicant_name}, has applied for '{job_title}'.\n"
        f"AI Match Score: {match_score}%\n\n"
        "Review this application on your SmartHire Recruiter Dashboard:\n"
        "http://127.0.0.1:5000/recruiter/dashboard\n\n"
        "— SmartHire Team"
    )
    return send_email_async(recruiter_email, subject, html, text, headline, "Recruiter Alert")


def send_application_shortlisted(applicant_email, applicant_name, job_title, recruiter_name="The Hiring Team"):
    """Sent when recruiter shortlists an applicant."""
    subject = f"Great News! You've Been Shortlisted for {job_title} - SmartHire"
    headline = "Congratulations! You are Shortlisted 🎉"
    greeting = f"Dear {applicant_name},"
    paragraphs = [
        f"We have exciting news regarding your application for <strong>{job_title}</strong>.",
        f"<strong>{recruiter_name}</strong> has reviewed your application and selected you for the <strong>Shortlist</strong>!",
        "Our AI screening indicated strong alignment between your qualifications and the position's requirements.",
        "Next steps: Please log into your applicant dashboard to view the tailored interview prep materials generated specifically for this role.",
    ]
    html = _build_email_html(
        headline=headline,
        greeting=greeting,
        message_paragraphs=paragraphs,
        badge_text="Status: Shortlisted",
        badge_color="#10b981",
        action_btn_text="Prepare for Interview",
        action_btn_url="http://127.0.0.1:5000/applicant/dashboard",
    )
    text = (
        f"Dear {applicant_name},\n\n"
        f"Great news! You have been shortlisted for the position '{job_title}' by {recruiter_name}.\n"
        "Log into your SmartHire dashboard to review role details and your interview preparation guide:\n"
        "http://127.0.0.1:5000/applicant/dashboard\n\n"
        "— SmartHire Hiring Team"
    )
    return send_email_async(applicant_email, subject, html, text, headline, "Shortlisted")


def send_application_on_hold(applicant_email, applicant_name, job_title):
    """Sent when recruiter places an application on hold."""
    subject = f"Application Update: {job_title} - SmartHire"
    headline = "Application Status Update"
    greeting = f"Hello {applicant_name},"
    paragraphs = [
        f"We are providing an update regarding your application for the <strong>{job_title}</strong> role.",
        "The recruiter has placed your application <strong>On Hold</strong> while reviewing active candidate batches.",
        "Your resume remains in the active talent pool, and you may be contacted as interview scheduling continues.",
        "Thank you for your patience and interest in this opportunity.",
    ]
    html = _build_email_html(
        headline=headline,
        greeting=greeting,
        message_paragraphs=paragraphs,
        badge_text="Status: On Hold",
        badge_color="#f59e0b",
        action_btn_text="View Application Status",
        action_btn_url="http://127.0.0.1:5000/applicant/dashboard",
    )
    text = (
        f"Hello {applicant_name},\n\n"
        f"Your application for '{job_title}' is currently on hold while candidate reviews are ongoing.\n"
        "Your profile remains active in the consideration pool.\n\n"
        "— SmartHire Team"
    )
    return send_email_async(applicant_email, subject, html, text, headline, "On Hold")


def send_application_rejected(applicant_email, applicant_name, job_title):
    """Sent when recruiter marks an application as rejected / not selected."""
    subject = f"Update regarding your application for {job_title} - SmartHire"
    headline = "Application Status Update"
    greeting = f"Hello {applicant_name},"
    paragraphs = [
        f"Thank you for your interest in the <strong>{job_title}</strong> position and for taking the time to apply.",
        "After careful consideration of all applicants, the hiring team has decided to proceed with other candidates whose experience more closely matches the specific needs of this role at this time.",
        "We encourage you to review the personalized AI resume feedback in your dashboard to help optimize your profile for future openings on SmartHire.",
        "We wish you every success in your ongoing job search.",
    ]
    html = _build_email_html(
        headline=headline,
        greeting=greeting,
        message_paragraphs=paragraphs,
        badge_text="Status: Not Selected",
        badge_color="#ef4444",
        action_btn_text="Explore Other Openings",
        action_btn_url="http://127.0.0.1:5000/applicant/jobs",
    )
    text = (
        f"Hello {applicant_name},\n\n"
        f"Thank you for applying for '{job_title}'. The hiring team has decided to proceed with other applicants for this role.\n"
        "We encourage you to explore other openings on SmartHire and review your AI resume feedback:\n"
        "http://127.0.0.1:5000/applicant/jobs\n\n"
        "— SmartHire Team"
    )
    return send_email_async(applicant_email, subject, html, text, headline, "Not Selected")


# ---------------------------------------------------------------------
# Scheduled Daily Summary for Recruiters
# ---------------------------------------------------------------------
def send_recruiter_daily_summary(recruiter, since_hours=24):
    """
    Generate and send a comprehensive daily email summary of new job applications
    received in the past 24 hours to the recruiter.
    """
    from app.models import Job, Application, User
    from app.extensions import db

    if isinstance(recruiter, int):
        recruiter = db.session.get(User, recruiter)
    if not recruiter or recruiter.role != "recruiter":
        return {"success": False, "count": 0, "reason": "Invalid recruiter"}

    since_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    jobs = Job.query.filter_by(recruiter_id=recruiter.id).all()
    job_map = {j.id: j for j in jobs}
    job_ids = list(job_map.keys())

    if not job_ids:
        new_apps = []
    else:
        new_apps = (
            Application.query.filter(
                Application.job_id.in_(job_ids),
                Application.applied_at >= since_time,
            )
            .order_by(Application.applied_at.desc())
            .all()
        )

    count = len(new_apps)
    scores = [a.match_score for a in new_apps if a.match_score is not None and a.match_score >= 0]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    top_score = max(scores) if scores else 0
    jobs_active_count = len(set(a.job_id for a in new_apps))

    date_label = datetime.now().strftime("%A, %B %d, %Y")
    subject = f"SmartHire Daily Digest: {count} New Candidate{'s' if count != 1 else ''} Today - {date_label}"
    headline = "Recruiter Daily Summary"

    # Build KPI metrics cards HTML
    kpi_html = f"""
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
        <tr>
            <td width="24%" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: #38bdf8;">{count}</div>
                <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-top: 4px;">New Applicants</div>
            </td>
            <td width="4%"></td>
            <td width="24%" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: #34d399;">{avg_score}%</div>
                <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-top: 4px;">Avg Match Score</div>
            </td>
            <td width="4%"></td>
            <td width="24%" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: #f59e0b;">{top_score}%</div>
                <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-top: 4px;">Top Match Score</div>
            </td>
            <td width="4%"></td>
            <td width="24%" style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 22px; font-weight: 800; color: #a855f7;">{jobs_active_count}</div>
                <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600; margin-top: 4px;">Active Roles</div>
            </td>
        </tr>
    </table>
    """

    # Build Candidate table rows
    if count > 0:
        table_rows = []
        for app in new_apps:
            cand_name = app.applicant.name if app.applicant else "Candidate"
            cand_email = app.applicant.email if app.applicant else "N/A"
            job_title = job_map[app.job_id].title if app.job_id in job_map else "Job Posting"

            score = app.match_score if app.match_score is not None else 0
            if score >= 80:
                score_bg, score_fg = "#065f46", "#34d399"
            elif score >= 60:
                score_bg, score_fg = "#1e40af", "#60a5fa"
            elif score >= 40:
                score_bg, score_fg = "#854d0e", "#facc15"
            else:
                score_bg, score_fg = "#991b1b", "#f87171"

            status_badge = app.status.capitalize() if app.status else "Pending"
            applied_time = app.applied_at.strftime("%I:%M %p") if app.applied_at else "Today"

            row_html = f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 12px 10px; color: #f8fafc; font-weight: 600;">
                    {cand_name}<br>
                    <span style="font-size: 11px; color: #94a3b8; font-weight: normal;">{cand_email}</span>
                </td>
                <td style="padding: 12px 10px; color: #cbd5e1;">{job_title}</td>
                <td style="padding: 12px 10px; text-align: center;">
                    <span style="display: inline-block; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: {score_bg}; color: {score_fg};">
                        {score}%
                    </span>
                </td>
                <td style="padding: 12px 10px; text-align: center;">
                    <span style="font-size: 11px; color: #cbd5e1; background: #334155; padding: 3px 8px; border-radius: 4px;">
                        {status_badge}
                    </span>
                </td>
                <td style="padding: 12px 10px; text-align: right; color: #94a3b8; font-size: 11px;">{applied_time}</td>
            </tr>
            """
            table_rows.append(row_html)

        candidates_section = f"""
        <div style="margin-top: 24px;">
            <h3 style="color: #ffffff; font-size: 15px; margin: 0 0 10px 0; font-weight: 700;">
                📋 Today's Candidates Breakdown
            </h3>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; background: #0f172a; border: 1px solid #334155; border-radius: 8px; overflow: hidden; font-size: 13px;">
                <thead>
                    <tr style="background: #1e293b; color: #94a3b8; text-align: left; border-bottom: 2px solid #334155;">
                        <th style="padding: 10px; font-weight: 600;">Candidate</th>
                        <th style="padding: 10px; font-weight: 600;">Job Role</th>
                        <th style="padding: 10px; font-weight: 600; text-align: center;">AI Score</th>
                        <th style="padding: 10px; font-weight: 600; text-align: center;">Status</th>
                        <th style="padding: 10px; font-weight: 600; text-align: right;">Time</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>
        """
    else:
        candidates_section = f"""
        <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 24px; text-align: center; color: #94a3b8; margin: 20px 0;">
            <p style="margin: 0; font-size: 15px; color: #cbd5e1; font-weight: 600;">No new applications were submitted in the last 24 hours.</p>
            <p style="margin: 6px 0 0 0; font-size: 12px; color: #64748b;">
                Your {len(jobs)} active job posting{'s' if len(jobs) != 1 else ''} remain published and accepting applications.
            </p>
        </div>
        """

    message_body = [
        f"Here is your automated daily recruitment digest for <strong>{date_label}</strong>.",
        "Below is the complete summary of candidate activity across your active job postings over the last 24 hours:",
        kpi_html,
        candidates_section,
        "Log into your Recruiter Dashboard to review full CV extractions, view AI recommendations, and advance top candidates to the interview stage.",
    ]

    html = _build_email_html(
        headline="Recruiter Daily Activity Summary",
        greeting=f"Hello {recruiter.name},",
        message_paragraphs=message_body,
        badge_text=f"{count} New Application{'s' if count != 1 else ''}",
        badge_color="#38bdf8",
        action_btn_text="Open Recruiter Dashboard",
        action_btn_url="http://127.0.0.1:5000/recruiter/dashboard",
    )

    # Plain text fallback
    text_lines = [
        f"Hello {recruiter.name},",
        "",
        f"Here is your daily SmartHire application digest for {date_label}:",
        f"• New Applications (last 24h): {count}",
        f"• Average AI Match Score: {avg_score}%",
        f"• Top Candidate Score: {top_score}%",
        f"• Active Roles with Applicants: {jobs_active_count}",
        "",
    ]
    if count > 0:
        text_lines.append("Candidate Breakdown:")
        for app in new_apps:
            cname = app.applicant.name if app.applicant else "Candidate"
            jtitle = job_map[app.job_id].title if app.job_id in job_map else "Job"
            text_lines.append(f" - {cname} | {jtitle} | AI Score: {app.match_score}% | Status: {app.status.capitalize()}")
        text_lines.append("")
    else:
        text_lines.append("No new applications received in the last 24 hours.\n")

    text_lines.append("Review candidates in your dashboard:")
    text_lines.append("http://127.0.0.1:5000/recruiter/dashboard\n")
    text_lines.append("— SmartHire Recruitment Platform")
    text = "\n".join(text_lines)

    th = send_email_async(
        to_email=recruiter.email,
        subject=subject,
        html_content=html,
        text_content=text,
        headline=headline,
        badge_text="Daily Summary",
    )
    return {"success": True, "count": count, "recipient": recruiter.email, "thread": th}


def send_all_recruiter_daily_summaries(since_hours=24):
    """
    Scheduled job entrypoint: sends daily summary emails to all registered recruiters.
    """
    from app.models import User
    from app.extensions import db

    try:
        recruiters = User.query.filter_by(role="recruiter").all()
        results = []
        for r in recruiters:
            res = send_recruiter_daily_summary(r, since_hours=since_hours)
            results.append(res)
        logger.info(f"[SmartHire Scheduler] Sent daily digest to {len(results)} recruiter(s).")
        return results
    except Exception as e:
        logger.error(f"[SmartHire Scheduler] Error sending recruiter daily summaries: {e}")
        return []
