"""Result-aware dual-audience narratives (executive + technical) with templates as seeds."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_narrative_template(persona: str) -> dict:
    file_path = TEMPLATES_DIR / f"{persona}_narrative.json"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_eur(x: float) -> str:
    try:
        return f"€{abs(float(x)):,.0f}"
    except Exception:
        return str(x)


def _top_findings(result: dict, n: int = 5) -> List[dict]:
    return list(result.get("findings") or [])[:n]


def build_executive_text(result: dict) -> str:
    """Board-ready plain text (no # markdown)."""
    sev = result.get("by_severity") or {}
    u = result.get("uad_comparison") or {}
    tops = _top_findings(result, 5)
    rows = result.get("rows", 0)

    lines = [
        "WHAT THIS MEANS IN BUSINESS TERMS",
        "",
        "Imagine a chain of stores where total daily sales look excellent. In a few locations, "
        "a silent checkout error gives product away. Because the rest of the chain is strong, "
        "the company total stays green — so the leak never appears on the executive dashboard. "
        "STRIDE-X inspects each market×platform “store,” not only the chain total.",
        "",
        "THE NUMBERS THAT MATTER",
        f"- Rows analyzed: {rows:,}",
        f"- Findings: {result.get('finding_count', 0)} "
        f"(Critical {sev.get('CRITICAL', 0)}, Severe {sev.get('SEVERE', 0)}, "
        f"Operational {sev.get('OPERATIONAL', 0)}, Low {sev.get('LOW', 0)})",
        f"- Days a simple company-level scanner would call “bad” (Z < −3): ~{u.get('macro_bad_days', 0)}",
        f"- Segment losses hidden on still-profitable company days: "
        f">{u.get('masked_1m', 0)} above €1M, {u.get('masked_500k', 0)} above €500k",
        "",
        "LARGEST IMPACTS",
    ]
    for f in tops:
        lines.append(
            f"- [{f.get('severity')}] {f.get('title')} — {f.get('segment')} — "
            f"impact {_fmt_eur(f.get('impact', 0))} (signed {f.get('impact', 0):,.0f})"
        )

    lines += [
        "",
        "URGENT FIRES (act this week)",
        "1. Risk / Trading — Review every CRITICAL company-day and segment cell above €1M; "
        "confirm whether the loss is real trading, pricing, or a data defect.",
        "2. Finance — Reconcile the top masked-loss days (green company total, red sub-segment) "
        "so leadership is not briefed only on the net.",
        "3. COO / Product — If the same platform shows repeated period-boundary margin collapse, "
        "freeze related promo mechanics until audited.",
        "",
        "STRUCTURAL FIXES (this quarter)",
        "1. Replace “company daily P&L only” monitoring with segment-level materiality alerts.",
        "2. Separate data-integrity defects (negative stake/volume) from commercial promo settlements.",
        "3. Require owner + due date on every CRITICAL finding in the weekly risk pack.",
        "",
        "WHAT A NORMAL DASHBOARD MISSED",
        "Aggregate monitoring answers whether the company had a bad day. STRIDE-X answers where "
        "margin or data integrity broke inside days that still looked profitable overall.",
    ]
    # merge template actions if present
    tpl = load_narrative_template("executive")
    if tpl.get("actionable_recommendations"):
        lines.append("")
        lines.append("ADDITIONAL LEADERSHIP ACTIONS (playbook)")
        for i, item in enumerate(tpl["actionable_recommendations"], 1):
            lines.append(f"{i}. {item.get('title')}: {item.get('action')}")
    return "\n".join(lines)


def build_technical_text(result: dict) -> str:
    sev = result.get("by_severity") or {}
    u = result.get("uad_comparison") or {}
    roles = result.get("roles") or {}
    by_layer: Dict[str, int] = {}
    for f in result.get("findings") or []:
        by_layer[f.get("layer", "?")] = by_layer.get(f.get("layer", "?"), 0) + 1

    lines = [
        "SCAN SNAPSHOT",
        f"- Source: {result.get('source')}",
        f"- Rows: {result.get('rows', 0):,} | Findings: {result.get('finding_count', 0)} | "
        f"CRITICAL {sev.get('CRITICAL', 0)} / SEVERE {sev.get('SEVERE', 0)} / "
        f"OPERATIONAL {sev.get('OPERATIONAL', 0)} / LOW {sev.get('LOW', 0)}",
        f"- Roles: {roles}",
        f"- UAD macro bad days (Z < −3): {u.get('macro_bad_days', 0)} | "
        f"Masked losses on green days: >€1M={u.get('masked_1m', 0)}, "
        f">€500k={u.get('masked_500k', 0)}, >€250k={u.get('masked_250k', 0)}",
        f"- Findings by layer: {by_layer}",
        "",
        "LAYER FINDINGS",
        "L1 Integrity — Impossible or ambiguous values (negative stake/volume, zero actives with volume, "
        "stake=0 with P&L). Treat all-negative stake=0 P&L as promo-compatible until proven otherwise; "
        "negative stake/volume is pipeline defect.",
        "L2 Stratified — Company-day Z plus within-segment temporal Z; losses on green company days.",
        "L3 Vector — Engagement ratios vs financials (e.g. games/active spikes with flat stake).",
        "L4 Period — Fiscal/period margin collapses vs history.",
        "",
        "ROOT-CAUSE HYPOTHESES",
        "(a) ETL / integrity — negative measures, identity gaps.",
        "(b) Operational black swans — extreme company or segment loss days.",
        "(c) Product / period mechanics — repeated Week-1 or period-boundary dual signatures.",
        "",
        "ENGINEERING ACTIONS",
        "1. Data Engineering — Quarantine negative stake/volume rows; add not-null and sign tests in dbt.",
        "2. Analytics Engineering — Publish within-segment rolling Z and masked-loss monitors (company green + cell < −threshold).",
        "3. Risk Tech — Page on CRITICAL cells; do not rely on company-daily Z alone.",
        "4. Product Analytics — Investigate any platform with synchronized period-boundary engagement×margin anomalies.",
        "",
        "MONITORING TO ADD",
        "- Daily: top N segment losses while company_profit > 0",
        "- Weekly: period margin Z and platform Week-position ratio charts",
        "- Continuous: integrity counters (neg stake, neg volume, zero-actives)",
    ]
    tpl = load_narrative_template("technical")
    if tpl.get("actionable_recommendations"):
        lines.append("")
        lines.append("PLAYBOOK ACTIONS")
        for i, item in enumerate(tpl["actionable_recommendations"], 1):
            lines.append(f"{i}. {item.get('title')}: {item.get('action')}")
    return "\n".join(lines)


def build_layers_text(result: dict) -> str:
    u = result.get("uad_comparison") or {}
    return "\n".join([
        "L1 Domain-aware sanitation",
        "Purpose: separate true pipeline corruption from valid commercial netting.",
        "Method: sign checks on stake/volume; stake=0 with P&L semantics; actives vs volume consistency.",
        "Aggregate UAD miss: often flags all zeros as bugs or ignores them.",
        "",
        "L2 Stratified surface",
        "Purpose: find cell-level disasters under green company totals.",
        "Method: company daily Z; within Market×Platform temporal Z; masked loss tiers.",
        f"This run: macro bad days ≈ {u.get('macro_bad_days', 0)}; "
        f"masked >€1M = {u.get('masked_1m', 0)}; >€500k = {u.get('masked_500k', 0)}.",
        "",
        "L3 Vector decoupling",
        "Purpose: catch engagement vs money divergence (logging or promo engines).",
        "Method: ratios such as games/active vs stake/active across week positions.",
        "",
        "L4 Period structure",
        "Purpose: structural margin regime changes by fiscal period.",
        "Method: period profit/stake margin Z vs history.",
        "",
        "Aggregate UAD vs STRIDE-X",
        f"- UAD focus: company-bad days ≈ {u.get('macro_bad_days', 0)}",
        f"- STRIDE-X adds: masked segment losses and layer-routed integrity/vector/period signals",
    ])


def build_split_narratives(result: dict) -> dict[str, str]:
    """Plain text narratives suitable for PDF and markdown (no raw HTML)."""
    return {
        "plain": build_executive_text(result),
        "technical": build_technical_text(result),
        "layers": build_layers_text(result),
    }
