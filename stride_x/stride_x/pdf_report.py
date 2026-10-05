"""STRIDE-X PDF + HTML executive reports with charts."""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

try:
    from .report import ReportBuilder
except ImportError:
    from stride_x.report import ReportBuilder  # type: ignore

try:
    import matplotlib
    matplotlib.use("Agg")
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
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, KeepTogether,
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _clean_narrative_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"(?m)^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*]\s+", "• ", cleaned)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", cleaned)
    cleaned = re.sub(r"__(.+?)__", r"<b>\1</b>", cleaned)
    cleaned = re.sub(r"<(?!/?b>|/?i>|br\s*/?)[^>]+>", "", cleaned)
    cleaned = cleaned.replace("\n", "<br/>")
    cleaned = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", cleaned)
    if cleaned.count("<b>") > cleaned.count("</b>"):
        cleaned += "</b>" * (cleaned.count("<b>") - cleaned.count("</b>"))
    if cleaned.count("<i>") > cleaned.count("</i>"):
        cleaned += "</i>" * (cleaned.count("<i>") - cleaned.count("</i>"))
    return cleaned


def generate_charts(result: dict) -> Dict[str, io.BytesIO]:
    chart_buffers: Dict[str, io.BytesIO] = {}
    if not HAS_MATPLOTLIB:
        return chart_buffers
    df = ReportBuilder(result).to_dataframe()
    if df.empty:
        return chart_buffers

    style_name = "seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default"
    plt.style.use(style_name)
    colors_map = {
        "CRITICAL": "#c53030",
        "SEVERE": "#dd6b20",
        "OPERATIONAL": "#2b6cb0",
        "LOW": "#718096",
    }

    # Top impact
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=160)
    top_df = df.head(10).copy()
    top_df["abs_impact"] = top_df["impact"].abs() / 1e6
    labels = [str(x)[:28] for x in top_df["title"].fillna(top_df["id"])]
    bar_colors = [colors_map.get(s, "#718096") for s in top_df["severity"]]
    ax.barh(range(len(top_df)), top_df["abs_impact"], color=bar_colors, height=0.65)
    ax.set_yticks(range(len(top_df)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Absolute impact (€ millions)", fontsize=8, fontweight="bold")
    ax.set_title("Top findings by loss magnitude", fontsize=11, fontweight="bold")
    fig.tight_layout()
    buf1 = io.BytesIO()
    fig.savefig(buf1, format="png", bbox_inches="tight")
    plt.close(fig)
    buf1.seek(0)
    chart_buffers["top_impact"] = buf1

    # Severity donut
    fig, ax = plt.subplots(figsize=(4.2, 3.4), dpi=160)
    sev_counts = df["severity"].value_counts()
    pie_colors = [colors_map.get(s, "#718096") for s in sev_counts.index]
    ax.pie(
        sev_counts.values,
        labels=list(sev_counts.index),
        autopct="%1.0f%%",
        colors=pie_colors,
        startangle=120,
        textprops={"fontsize": 8},
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    ax.set_title("Findings by severity", fontsize=11, fontweight="bold")
    fig.tight_layout()
    buf2 = io.BytesIO()
    fig.savefig(buf2, format="png", bbox_inches="tight")
    plt.close(fig)
    buf2.seek(0)
    chart_buffers["severity_pie"] = buf2

    # Layer bar if present
    if "layer" in df.columns:
        fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=160)
        lc = df["layer"].value_counts()
        ax.bar(range(len(lc)), lc.values, color="#2b6cb0", width=0.6)
        ax.set_xticks(range(len(lc)))
        ax.set_xticklabels([str(x)[:18] for x in lc.index], fontsize=7, rotation=15, ha="right")
        ax.set_ylabel("Count", fontsize=8)
        ax.set_title("Findings by detection layer", fontsize=11, fontweight="bold")
        fig.tight_layout()
        buf3 = io.BytesIO()
        fig.savefig(buf3, format="png", bbox_inches="tight")
        plt.close(fig)
        buf3.seek(0)
        chart_buffers["layer_bar"] = buf3

    return chart_buffers


def write_pdf(result: dict, output_path: str | Path, narratives: Optional[dict] = None) -> str:
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    narratives = narratives or {}

    # Always write polished HTML alongside
    html_path = out_file.with_name(out_file.stem + ".html")
    write_html_report(result, html_path, narratives)

    if not HAS_REPORTLAB:
        out_file.write_text(
            f"ReportLab not installed. Open HTML report instead: {html_path}\n"
            "pip install reportlab matplotlib\n",
            encoding="utf-8",
        )
        return str(html_path)

    doc = SimpleDocTemplate(
        str(out_file), pagesize=letter,
        leftMargin=40, rightMargin=40, topMargin=36, bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Heading1"], fontSize=18, leading=22,
        textColor=colors.HexColor("#1A365D"), spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSub", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=colors.HexColor("#4A5568"), spaceAfter=10,
    )
    h1_style = ParagraphStyle(
        "SecH1", parent=styles["Heading2"], fontSize=12, leading=15,
        textColor=colors.HexColor("#2B6CB0"), spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyDark", parent=styles["BodyText"], fontSize=8.5, leading=11.5,
        textColor=colors.HexColor("#2D3748"), spaceAfter=4,
    )

    story = []
    sev = result.get("by_severity") or {}
    u = result.get("uad_comparison") or {}
    story.append(Paragraph("STRIDE-X Executive Audit Report", title_style))
    story.append(Paragraph(
        f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC &nbsp;|&nbsp; "
        f"<b>Rows:</b> {result.get('rows', 0):,} &nbsp;|&nbsp; "
        f"<b>Findings:</b> {result.get('finding_count', 0)} "
        f"(Critical {sev.get('CRITICAL', 0)}, Severe {sev.get('SEVERE', 0)}) &nbsp;|&nbsp; "
        f"<b>Masked &gt;€1M on green days:</b> {u.get('masked_1m', 0)}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2B6CB0"), spaceAfter=10))

    chart_bufs = generate_charts(result)
    if chart_bufs:
        story.append(Paragraph("Visual risk analysis", h1_style))
        row = []
        if "top_impact" in chart_bufs:
            row.append(Image(chart_bufs["top_impact"], width=4.0 * inch, height=1.9 * inch))
        if "severity_pie" in chart_bufs:
            row.append(Image(chart_bufs["severity_pie"], width=2.6 * inch, height=1.9 * inch))
        if row:
            t = Table([row], colWidths=[4.1 * inch, 2.7 * inch][:len(row)])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            story.append(t)
        if "layer_bar" in chart_bufs:
            story.append(Spacer(1, 6))
            story.append(Image(chart_bufs["layer_bar"], width=6.2 * inch, height=2.0 * inch))
        story.append(Spacer(1, 8))

    if narratives.get("plain"):
        story.append(Paragraph("For leadership (plain language)", h1_style))
        story.append(Paragraph(_clean_narrative_text(narratives["plain"]), body_style))
    if narratives.get("technical"):
        story.append(Paragraph("For technical teams", h1_style))
        story.append(Paragraph(_clean_narrative_text(narratives["technical"]), body_style))

    df = ReportBuilder(result).to_dataframe()
    if not df.empty:
        story.append(Paragraph("Top findings log", h1_style))
        data = [["Sev", "Layer", "Title", "Segment", "Impact (€)"]]
        for _, row in df.head(18).iterrows():
            data.append([
                str(row.get("severity", ""))[:10],
                str(row.get("layer", ""))[:14],
                str(row.get("title", ""))[:40],
                str(row.get("segment", ""))[:22],
                f"{row.get('impact', 0):,.0f}",
            ])
        tbl = Table(data, colWidths=[0.85 * inch, 1.0 * inch, 2.6 * inch, 1.5 * inch, 1.0 * inch])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "An HTML version of this report with the same charts was also written next to this PDF "
        f"({html_path.name}). Use browser Print → Save as PDF if you prefer that layout.",
        subtitle_style,
    ))
    doc.build(story)
    return str(out_file)


def write_html_report(result: dict, output_path: str | Path, narratives: Optional[dict] = None) -> str:
    """Polished self-contained HTML report (print-ready)."""
    out = Path(output_path)
    narratives = narratives or {}
    sev = result.get("by_severity") or {}
    u = result.get("uad_comparison") or {}
    df = ReportBuilder(result).to_dataframe()

    # Embed charts as base64
    import base64
    imgs_html = ""
    charts = generate_charts(result)
    for key, buf in charts.items():
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        imgs_html += f'<div class="chart"><img src="data:image/png;base64,{b64}" alt="{key}"/></div>\n'

    def esc(t: str) -> str:
        return (
            (t or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def pre(t: str) -> str:
        return f"<pre class='narrative'>{esc(t)}</pre>"

    rows = ""
    if not df.empty:
        for _, r in df.head(25).iterrows():
            rows += (
                f"<tr><td>{esc(str(r.get('severity','')))}</td>"
                f"<td>{esc(str(r.get('layer','')))}</td>"
                f"<td>{esc(str(r.get('title','')))}</td>"
                f"<td>{esc(str(r.get('segment','')))}</td>"
                f"<td class='num'>{r.get('impact',0):,.0f}</td></tr>"
            )

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>STRIDE-X Executive Audit Report</title>
<style>
  :root {{ --navy:#1A365D; --blue:#2B6CB0; --muted:#4A5568; --bg:#F7FAFC; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; color: #1a202c; background: #fff; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 24px 64px; }}
  h1 {{ color: var(--navy); font-size: 1.75rem; margin: 0 0 8px; }}
  h2 {{ color: var(--blue); font-size: 1.15rem; margin: 28px 0 10px; border-bottom: 2px solid #E2E8F0; padding-bottom: 6px; }}
  .meta {{ color: var(--muted); font-size: 0.9rem; line-height: 1.5; }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0 8px; }}
  .kpi {{ background: var(--bg); border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px; min-width: 120px; }}
  .kpi b {{ display: block; font-size: 1.25rem; color: var(--navy); }}
  .kpi span {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .03em; }}
  .charts {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: center; margin: 12px 0 20px; }}
  .chart img {{ max-width: 100%; height: auto; border: 1px solid #E2E8F0; border-radius: 8px; background: #fff; }}
  pre.narrative {{ white-space: pre-wrap; font-family: inherit; font-size: 0.92rem; line-height: 1.45;
    background: var(--bg); border-left: 4px solid var(--blue); padding: 14px 16px; border-radius: 0 8px 8px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 8px; }}
  th {{ background: var(--navy); color: #fff; text-align: left; padding: 8px; }}
  td {{ border-bottom: 1px solid #E2E8F0; padding: 7px 8px; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #F7FAFC; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  footer {{ margin-top: 32px; font-size: 0.8rem; color: var(--muted); }}
  @media print {{ body {{ margin: 0; }} .wrap {{ padding: 12px; }} }}
</style>
</head><body><div class="wrap">
<h1>STRIDE-X Executive Audit Report</h1>
<p class="meta">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC<br/>
Source: {esc(str(result.get('source','')))}</p>
<div class="kpis">
  <div class="kpi"><b>{result.get('rows',0):,}</b><span>Rows</span></div>
  <div class="kpi"><b>{result.get('finding_count',0)}</b><span>Findings</span></div>
  <div class="kpi"><b>{sev.get('CRITICAL',0)}</b><span>Critical</span></div>
  <div class="kpi"><b>{sev.get('SEVERE',0)}</b><span>Severe</span></div>
  <div class="kpi"><b>{u.get('macro_bad_days',0)}</b><span>UAD bad days</span></div>
  <div class="kpi"><b>{u.get('masked_1m',0)}</b><span>Masked &gt;€1M</span></div>
</div>
<h2>Visual risk analysis</h2>
<div class="charts">{imgs_html or '<p class="meta">Install matplotlib for charts.</p>'}</div>
<h2>For leadership</h2>
{pre(narratives.get('plain') or 'Run with LLM or templates for executive narrative.')}
<h2>For technical teams</h2>
{pre(narratives.get('technical') or '')}
<h2>Method layers</h2>
{pre(narratives.get('layers') or '')}
<h2>Top findings</h2>
<table>
<thead><tr><th>Sev</th><th>Layer</th><th>Title</th><th>Segment</th><th>Impact (€)</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<footer>
STRIDE-X — Stratified Tiered Risk &amp; Integrity Detection Engine.
Aggregate dashboards ask “Did the company have a bad day?” STRIDE-X asks where risk hides under a green day.
</footer>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    return str(out)
