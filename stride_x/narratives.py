"""STRIDE-X Narrative Loader — Handles persona-split analogies and recommendations."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

def load_narrative_template(persona: str) -> dict:
    file_path = TEMPLATES_DIR / f"{persona}_narrative.json"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_split_narratives(result: dict) -> dict[str, str]:
    """Generates clean HTML/Markdown narrative blocks for Exec and Tech personas."""
    exec_data = load_narrative_template("executive")
    tech_data = load_narrative_template("technical")

    # Format Executive Block
    exec_actions_html = "".join([
        f"<li><b>{item['title']}:</b> {item['action']}</li>"
        for item in exec_data.get("actionable_recommendations", [])
    ])
    
    exec_html = f"""
    <div style="background-color: #f0fff4; border-left: 5px solid #38a169; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
        <h3 style="color: #276749; margin-top:0;">👔 Executive Overview & Business Analogy</h3>
        <p><b>{exec_data.get('analogy_headline', '')}</b></p>
        <p><i>"{exec_data.get('analogy_body', '')}"</i></p>
        <h4 style="color: #276749;">Action Items for Leadership:</h4>
        <ul>{exec_actions_html}</ul>
    </div>
    """

    # Format Technical Block
    tech_actions_html = "".join([
        f"<li><b>{item['title']}:</b> {item['action']}</li>"
        for item in tech_data.get("actionable_recommendations", [])
    ])
    
    layer_items = "".join([
        f"<li><b>{k}:</b> {v}</li>"
        for k, v in tech_data.get("layer_breakdown", {}).items()
    ])

    tech_html = f"""
    <div style="background-color: #ebf8ff; border-left: 5px solid #3182ce; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
        <h3 style="color: #2b6cb0; margin-top:0;">🛠️ Technical Audit & Engineering Root Causes</h3>
        <p>{tech_data.get('technical_summary', '')}</p>
        <h4 style="color: #2b6cb0;">Layer-by-Layer Findings:</h4>
        <ul>{layer_items}</ul>
        <h4 style="color: #2b6cb0;">Data Engineering & Risk Actions:</h4>
        <ul>{tech_actions_html}</ul>
    </div>
    """

    return {
        "plain": exec_html,
        "technical": tech_html,
        "exec_json": exec_data,
        "tech_json": tech_data
    }
