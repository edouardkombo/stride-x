"""LLM layer — unified env names for Ollama, OpenAI, Gemini, Anthropic."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Elite report prompts — structured, dual-audience, action-first, no markdown #
# ---------------------------------------------------------------------------

SYSTEM_PLAIN = """You are a trusted advisor writing for a CEO, CFO, and board.
Write in plain English. No jargon unless defined in one short clause.
Do NOT invent numbers — use only figures present in the JSON.
Do NOT use markdown headings with # characters. Use short labeled sections only.

Required structure (use these exact section labels):

WHAT THIS MEANS IN BUSINESS TERMS
One tight analogy (2–4 sentences). Prefer concrete images: retail chain leak, silent pipe under a profitable building, one bad lane on a busy highway.

THE NUMBERS THAT MATTER
Bullet the 4–6 most important facts from the JSON (rows, finding counts, masked losses, largest impacts in euros).

URGENT FIRES (act this week)
Numbered actions for non-technical leaders. Each line: Action — why — owner role (CEO/CFO/COO/Risk).

STRUCTURAL FIXES (this quarter)
Numbered actions for process and governance (not code detail).

WHAT A NORMAL DASHBOARD MISSED
One short paragraph: aggregate “green day” monitoring vs what STRIDE-X found.

Keep under 550 words. Tone: calm, decisive, board-ready."""

SYSTEM_TECH = """You are a principal data scientist briefing the Head of Data, Analytics Engineering, and Risk Tech.
Be precise. Use euros (€). Do NOT invent numbers. Do NOT use # markdown headings.

Required structure (exact section labels):

SCAN SNAPSHOT
Rows, roles detected, severity counts, UAD comparison (macro bad days vs masked losses).

LAYER FINDINGS
For L1, L2, L3, L4: one paragraph each — what the layer measures, what this run found, severity.

ROOT-CAUSE HYPOTHESES
Separate (a) data integrity / ETL, (b) operational / trading loss events, (c) product or period mechanics. Do not claim certainty without evidence.

ENGINEERING ACTIONS
Numbered, specific, implementable (dbt tests, within-segment Z monitors, materiality gates, promo vs negative-stake rules, owner team).

MONITORING TO ADD
What to put in production dashboards so masked losses cannot hide again.

Keep under 700 words. Tone: rigorous, irrefutable, no hype."""

SYSTEM_LAYERS = """You document STRIDE-X methods for an internal wiki and auditors.
Do NOT invent findings. Do NOT use # headings.

For each layer L1 Domain-aware sanitation, L2 Stratified surface, L3 Vector decoupling, L4 Period structure write:
- Purpose (1 sentence)
- Method (1–2 sentences)
- What aggregate UAD misses
- Findings from this run that map to the layer (or “none in top set”)
- Recommended control

Close with a 5-line comparison table in plain text: Aggregate UAD vs STRIDE-X.
Use euros (€). Under 600 words."""


DEFAULTS = {
    "ollama": {
        "model": "llama3.2",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": None,
        "api_key": None,
    },
    "gemini": {
        "model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": None,
    },
    "anthropic": {
        "model": "claude-sonnet-4-5",
        "base_url": None,
        "api_key": None,
    },
}


def _env(*names: str, default: str = "") -> str:
    for n in names:
        v = (os.getenv(n) or "").strip()
        if v:
            return v
    return default


def resolve_provider(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Same variable names for every provider — only values change."""
    provider = (provider or _env("STRIDE_X_LLM_PROVIDER")).lower() or None

    if not provider:
        if _env("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            provider = "gemini"
        elif _env("ANTHROPIC_API_KEY") or _env("STRIDE_X_LLM_API_KEY", "OPENAI_API_KEY").startswith("sk-ant"):
            provider = "anthropic"
        elif _env("STRIDE_X_LLM_API_KEY", "OPENAI_API_KEY").startswith("sk-"):
            provider = "openai"
        else:
            provider = "ollama"

    if provider not in DEFAULTS:
        raise RuntimeError(
            f"Unknown provider {provider!r}. Use: ollama | openai | gemini | anthropic"
        )

    d = DEFAULTS[provider]

    key = (
        api_key
        or _env("STRIDE_X_LLM_API_KEY")
        or (
            _env("GEMINI_API_KEY", "GOOGLE_API_KEY")
            if provider == "gemini"
            else _env("ANTHROPIC_API_KEY")
            if provider == "anthropic"
            else _env("OPENAI_API_KEY")
        )
        or d["api_key"]
        or ""
    )

    # Prefer unified model; do not let a stale OPENAI_MODEL=llama* break Gemini/OpenAI
    unified_model = _env("STRIDE_X_LLM_MODEL")
    legacy_model = _env("OPENAI_MODEL")
    if unified_model:
        mdl = model or unified_model
    elif model:
        mdl = model
    elif legacy_model and provider == "ollama":
        mdl = legacy_model
    elif legacy_model and provider == "openai" and not legacy_model.lower().startswith(("llama", "mistral", "gemini")):
        mdl = legacy_model
    else:
        mdl = d["model"]

    burl = base_url if base_url is not None else (_env("STRIDE_X_LLM_BASE_URL") or _env("OPENAI_BASE_URL") or None)
    if not burl:
        burl = d["base_url"]
    if provider == "ollama":
        if burl and "generativelanguage.googleapis.com" in burl:
            burl = DEFAULTS["ollama"]["base_url"]
        if burl and not burl.rstrip("/").endswith("/v1"):
            burl = burl.rstrip("/") + "/v1"
    if provider == "gemini":
        burl = DEFAULTS["gemini"]["base_url"]

    if provider in ("openai", "gemini", "anthropic") and not key:
        raise RuntimeError(
            f"{provider} selected but STRIDE_X_LLM_API_KEY is empty.\n"
            f"  export STRIDE_X_LLM_PROVIDER={provider}\n"
            f"  export STRIDE_X_LLM_API_KEY=...\n"
            f"  export STRIDE_X_LLM_MODEL={d['model']}\n"
        )

    if provider == "ollama" and (not key or key.lower() in {"", "ollama", "sk-local", "local"}):
        key = "ollama"

    return {"provider": provider, "base_url": burl, "api_key": key, "model": mdl}


def _chat_openai_compat(system: str, user: str, cfg: Dict[str, Any]) -> str:
    from openai import OpenAI

    kwargs: Dict[str, Any] = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.15,
    )
    return resp.choices[0].message.content or ""


def _chat_anthropic(system: str, user: str, cfg: Dict[str, Any]) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("pip install anthropic") from e
    client = anthropic.Anthropic(api_key=cfg["api_key"])
    resp = client.messages.create(
        model=cfg["model"],
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=0.15,
    )
    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


def _chat(system: str, user: str, cfg: Dict[str, Any]) -> str:
    try:
        if cfg["provider"] == "anthropic":
            return _chat_anthropic(system, user, cfg)
        return _chat_openai_compat(system, user, cfg)
    except Exception as e:
        raise RuntimeError(
            f"LLM call failed: {e}\n"
            f"provider={cfg.get('provider')} model={cfg.get('model')!r} "
            f"base_url={cfg.get('base_url')!r}\n"
            "  export STRIDE_X_LLM_PROVIDER=ollama|openai|gemini|anthropic\n"
            "  export STRIDE_X_LLM_API_KEY=...\n"
            "  export STRIDE_X_LLM_MODEL=...\n"
        ) from e


def _slim_findings(result: Dict[str, Any], max_findings: int = 15) -> List[Dict[str, Any]]:
    out = []
    for f in (result.get("findings") or [])[:max_findings]:
        out.append({
            "severity": f.get("severity"),
            "layer": f.get("layer"),
            "title": f.get("title"),
            "segment": f.get("segment"),
            "impact": f.get("impact"),
            "metric_value": f.get("metric_value"),
            "benchmark": f.get("benchmark"),
            "description": (f.get("description") or "")[:400],
            "category": f.get("category"),
        })
    return out


def explain_findings(result: Dict[str, Any], model: Optional[str] = None, max_findings: int = 15) -> str:
    parts = explain_dual(result, model=model, max_findings=max_findings)
    return (
        "FOR LEADERSHIP\n\n"
        + parts["plain"]
        + "\n\nFOR TECHNICAL TEAMS\n\n"
        + parts["technical"]
    )


def explain_dual(
    result: Dict[str, Any],
    model: Optional[str] = None,
    max_findings: int = 15,
    provider: Optional[str] = None,
) -> Dict[str, str]:
    cfg = resolve_provider(model=model, provider=provider)
    payload = {
        "summary": {
            k: result[k]
            for k in ("source", "rows", "roles", "finding_count", "by_severity", "uad_comparison")
            if k in result
        },
        "top_findings": _slim_findings(result, max_findings),
    }
    blob = json.dumps(payload, default=str)
    return {
        "plain": _chat(
            SYSTEM_PLAIN,
            "Write the executive briefing from this STRIDE-X audit JSON. Follow the required section labels exactly.\n\n"
            + blob,
            cfg,
        ),
        "technical": _chat(
            SYSTEM_TECH,
            "Write the technical briefing from this STRIDE-X audit JSON. Follow the required section labels exactly.\n\n"
            + blob,
            cfg,
        ),
        "layers": _chat(
            SYSTEM_LAYERS,
            "Document methods and map findings from this STRIDE-X audit JSON.\n\n" + blob,
            cfg,
        ),
        "provider": cfg["provider"],
        "model": cfg["model"],
    }
