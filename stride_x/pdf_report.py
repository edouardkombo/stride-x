"""STRIDE-X PDF Report Generator.

Generates executive PDF reports with embedded Matplotlib chart visualizations,
structured narrative sections, and formatted findings tables.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Optional
import re
import html
import pandas as pd
#from .report import ReportBuilder
# Safe imports for internal modules (using relative imports)
try:
    from .report import ReportBuilder  # Or whichever function/class is in report.py
except ImportError:
    # If report.py exports functions or a different class name:
    from . import report as report_module


# Safe imports for Matplotlib and ReportLab
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive headless backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        HRFlowable,
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

def _clean_narrative_text(text: str) -> str:
    if not text:
        return ""

    # 1. Convert Markdown bold syntax (**text**) to HTML (<b>text</b>)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)

    # 2. Fix unclosed opening <b> tags before standard bold prefixes
    cleaned = re.sub(r"<b>(\s*<b>)", r"<b>", cleaned)
    cleaned = re.sub(r"<b>([^<]*?):<b>", r"<b>\1:</b>", cleaned)

    # 3. Escape raw ampersands which also crash ReportLab XML parser
    cleaned = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", cleaned)

    # 4. Auto-close any unclosed <b> or <i> tags at the end of the text
    open_b = cleaned.count("<b>") - cleaned.count("</b>")
    if open_b > 0:
        cleaned += "</b>" * open_b

    open_i = cleaned.count("<i>") - cleaned.count("</i>")
    if open_i > 0:
        cleaned += "</i>" * open_i

    return cleaned

def generate_charts(result: dict) -> Dict[str, io.BytesIO]:
    """Generates chart buffers (Severity distribution, Top Findings) if Matplotlib is installed."""
    chart_buffers = {}
    if not HAS_MATPLOTLIB:
        return chart_buffers

    df = ReportBuilder(result).to_dataframe()
    if df.empty:
        return chart_buffers

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # 1. Top 10 Impact Findings Chart
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    top_df = df.head(10).copy()
    top_df["abs_impact"] = top_df["impact"].abs() / 1e6

    colors_map = {
        "CRITICAL": "#d9534f",
        "SEVERE": "#f0ad4e",
        "OPERATIONAL": "#0275d8",
        "LOW": "#6c757d",
    }
    bar_colors = [colors_map.get(s, "#6c757d") for s in top_df["severity"]]

    ax.barh(top_df["id"], top_df["abs_impact"], color=bar_colors, height=0.6)
    ax.invert_yaxis()
    ax.set_xlabel("Financial Impact (€ Millions)", fontsize=9, fontweight="bold")
    ax.set_ylabel("Finding ID", fontsize=9, fontweight="bold")
    ax.set_title("Top 10 Findings by Loss Magnitude", fontsize=11, fontweight="bold", pad=10)
    ax.tick_params(labelsize=8)

    plt.tight_layout()
    buf1 = io.BytesIO()
    plt.savefig(buf1, format="png", bbox_inches="tight")
    plt.close(fig)
    buf1.seek(0)
    chart_buffers["top_impact"] = buf1

    # 2. Severity Distribution Donut Chart
    fig, ax = plt.subplots(figsize=(4, 3.2), dpi=200)
    sev_counts = df["severity"].value_counts()
    pie_colors = [colors_map.get(s, "#6c757d") for s in sev_counts.index]

    wedges, texts, autotexts = ax.pie(
        sev_counts.values,
        labels=sev_counts.index,
        autopct="%1.1f%%",
        colors=pie_colors,
        startangle=140,
        textprops={"fontsize": 8},
        wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2)
    )
    plt.setp(autotexts, size=8, weight="bold", color="white")
    ax.set_title("Exposure Distribution by Severity", fontsize=11, fontweight="bold", pad=10)

    plt.tight_layout()
    buf2 = io.BytesIO()
    plt.savefig(buf2, format="png", bbox_inches="tight")
    plt.close(fig)
    buf2.seek(0)
    chart_buffers["severity_pie"] = buf2

    return chart_buffers


def write_pdf(
    result: dict,
    output_path: str | Path,
    narratives: Optional[dict] = None
) -> str:
    """Renders a PDF report with embedded charts, structured narrative styles, and tables."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not HAS_REPORTLAB:
        # Fallback text file if reportlab is not installed
        out_file.write_text("ReportLab is not installed. Please run `pip install reportlab matplotlib`.", encoding="utf-8")
        return str(out_file)

    doc = SimpleDocTemplate(
        str(out_file),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=5,
    )

    story = []

    # Title Banner
    story.append(Paragraph("🛡️ STRIDE-X Executive Audit Report", title_style))
    story.append(
        Paragraph(
            f"<b>Rows Analyzed:</b> {result.get('rows', 0):,} | "
            f"<b>Total Findings:</b> {result.get('finding_count', 0)} | "
            f"<b>Critical:</b> {result.get('by_severity', {}).get('CRITICAL', 0)} | "
            f"<b>Severe:</b> {result.get('by_severity', {}).get('SEVERE', 0)}",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=12))

    # Embedded Matplotlib Visualizations
    chart_bufs = generate_charts(result)
    if chart_bufs:
        story.append(Paragraph("Visual Risk Analysis", h1_style))
        img1 = Image(chart_bufs["top_impact"], width=3.8 * inch, height=1.8 * inch)
        img2 = Image(chart_bufs["severity_pie"], width=2.8 * inch, height=1.8 * inch)

        chart_table = Table([[img1, img2]], colWidths=[3.9 * inch, 2.9 * inch])
        chart_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(chart_table)
        story.append(Spacer(1, 8))

    # Executive Narrative Briefing
    if narratives and "plain" in narratives:
        story.append(Paragraph("Executive Summary & Business Action Items", h1_style))
        for line in narratives["plain"].split("\n\n"):
            clean = line.replace("###", "").replace("**", "<b>").replace("**", "</b>")
            if clean.strip():
                #story.append(Paragraph(clean.strip(), body_style))
                clean_text = _clean_narrative_text(clean.strip())
                story.append(Paragraph(clean_text, body_style))
        story.append(Spacer(1, 8))

    # Technical Remediation Plan
    if narratives and "technical" in narratives:
        story.append(Paragraph("Technical Engineering Analysis", h1_style))
        for line in narratives["technical"].split("\n\n"):
            clean = line.replace("###", "").replace("**", "<b>").replace("**", "</b>")
            if clean.strip():
                #story.append(Paragraph(clean.strip(), body_style))
                clean_text = _clean_narrative_text(clean.strip())
                story.append(Paragraph(clean_text, body_style))
        story.append(Spacer(1, 8))

    # Findings Audit Table
    df = ReportBuilder(result).to_dataframe()
    if not df.empty:
        story.append(Paragraph("Top Audit Findings Log", h1_style))
        table_data = [["Sev", "Layer", "Title / Context", "Impact (€)"]]
        for _, row in df.head(15).iterrows():
            table_data.append([
                str(row.get("severity", "")),
                str(row.get("layer", "")),
                str(row.get("title", ""))[:45],
                f"{row.get('impact', 0):,.0f}"
            ])

        t = Table(table_data, colWidths=[1.0 * inch, 1.1 * inch, 3.4 * inch, 1.3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ]))
        story.append(t)

    doc.build(story)
    return str(out_file)
