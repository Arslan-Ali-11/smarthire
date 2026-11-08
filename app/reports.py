import csv
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_applicants_csv(job, applications):
    """Generate a CSV string of ranked applicants for a job."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Rank",
        "Applicant Name",
        "Applicant Email",
        "Match Score (0-100)",
        "Status",
        "Resume Filename",
        "Score Justification / Summary",
        "Applied At (UTC)",
    ])

    for rank, app in enumerate(applications, 1):
        score_display = app.match_score if app.match_score >= 0 else "Not Scored"
        writer.writerow([
            rank,
            app.applicant.name if app.applicant else "N/A",
            app.applicant.email if app.applicant else "N/A",
            score_display,
            app.status.capitalize(),
            app.resume_filename,
            app.score_explanation.replace("\n", " ").strip() if app.score_explanation else "",
            app.applied_at.strftime("%Y-%m-%d %H:%M:%S") if app.applied_at else "",
        ])

    output.seek(0)
    return output.getvalue()


def generate_applicants_pdf(job, applications):
    """Generate a styled PDF report of ranked applicants for a job."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
    )
    cell_style = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )
    header_cell = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.white,
    )

    story = []

    # Title & Branding
    story.append(Paragraph("SmartHire &mdash; Ranked Candidate Report", title_style))
    story.append(Spacer(1, 4))
    meta_text = (
        f"<b>Job:</b> {job.title} &nbsp;|&nbsp; "
        f"<b>Status:</b> {job.status.capitalize()} &nbsp;|&nbsp; "
        f"<b>Min Experience:</b> {job.min_experience_years} yrs &nbsp;|&nbsp; "
        f"<b>Generated:</b> {datetime.utcnow().strftime('%B %d, %Y %H:%M UTC')}"
    )
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5"), spaceAfter=14))

    # Summary Statistics
    total_apps = len(applications)
    shortlisted = sum(1 for a in applications if a.status == "shortlisted")
    scored = [a.match_score for a in applications if a.match_score >= 0]
    avg_score = round(sum(scored) / len(scored), 1) if scored else "N/A"

    summary_data = [
        [
            Paragraph(f"<b>Total Candidates:</b> {total_apps}", subtitle_style),
            Paragraph(f"<b>Shortlisted:</b> {shortlisted}", subtitle_style),
            Paragraph(f"<b>Avg. Match Score:</b> {avg_score}%", subtitle_style),
            Paragraph(f"<b>Required Skills:</b> {', '.join(job.get_skills_list()[:5])}", subtitle_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[1.7 * inch, 1.3 * inch, 1.8 * inch, 2.7 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # Applicants Table
    table_data = [[
        Paragraph("#", header_cell),
        Paragraph("Candidate", header_cell),
        Paragraph("Email", header_cell),
        Paragraph("Score", header_cell),
        Paragraph("Status", header_cell),
        Paragraph("Applied", header_cell),
    ]]

    for rank, app in enumerate(applications, 1):
        score_text = f"<b>{app.match_score}%</b>" if app.match_score >= 0 else "—"
        status_text = f"<b>{app.status.upper()}</b>"
        applied_str = app.applied_at.strftime("%b %d, %Y") if app.applied_at else "—"

        table_data.append([
            Paragraph(str(rank), cell_bold),
            Paragraph(app.applicant.name if app.applicant else "N/A", cell_bold),
            Paragraph(app.applicant.email if app.applicant else "N/A", cell_style),
            Paragraph(score_text, cell_style),
            Paragraph(status_text, cell_style),
            Paragraph(applied_str, cell_style),
        ])

    app_table = Table(
        table_data,
        colWidths=[0.4 * inch, 2.0 * inch, 2.2 * inch, 0.9 * inch, 1.0 * inch, 1.0 * inch],
    )
    app_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(app_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
