"""LLM layer — unified env names for Ollama, OpenAI, Gemini, Anthropic."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

SYSTEM_TECH = """You are a senior data scientist and risk engineer.
Explain STRIDE-X findings with precise language: Z-scores, stratified cells, materiality tiers, data integrity.
Do not invent numbers. Structure by layer (L1 integrity, L2 stratified, L3 vectors, L4 periods).
For each major finding: what was measured, why it is anomalous, recommended owner (Data Eng / Product / Trading / Finance).
Contrast briefly with what a simple aggregate UAD (company-daily Z only) would have missed.
Use euros (€). Keep total under 900 words."""

SYSTEM_PLAIN = """You are explaining a business audit to executives who are not data scientists.
Use plain language and short analogies (e.g. "company profit is the forest; each market×platform is a tree — a forest can look healthy while one tree is on fire").
Do not invent numbers. Group into: urgent fires, structural problems, data plumbing issues, things to monitor.
Say who should act (engineering, product, risk, finance). Avoid jargon or define it in one clause.
Use euros (€). Keep total under 700 words."""

SYSTEM_LAYERS = """You are documenting a detection framework for a technical wiki.
For each STRIDE-X layer (L1 Domain-aware sanitation, L2 Stratified surface, L3 Vector decoupling, L4 Period structure):
explain purpose, method, what a regular aggregate UAD would miss, and map the findings from the JSON that belong to that layer.
Do not invent findings. Use euros (€)."""

# Unified env (preferred):
#   STRIDE_X_LLM_PROVIDER = ollama | openai | gemini | anthropic
#   STRIDE_X_LLM_API_KEY
#   STRIDE_X_LLM_MODEL
#   STRIDE_X_LLM_BASE_URL   (optional)
#
# Backward-compatible aliases still read:
#   OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, OLLAMA_HOST,
#   GEMINI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY

DEFAULTS = {
    "ollama": {
        "model": "llama3.2",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": None,  # official API
        "api_key": None,
    },
    "gemini": {
        "model": "gemini-3.8-flash",
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
    """
    Resolve LLM config. Same variable names for every provider — only values change.

        export STRIDE_X_LLM_PROVIDER=gemini
        export STRIDE_X_LLM_API_KEY=...
        export STRIDE_X_LLM_MODEL=gemini-3.8-flash

    No unset required when switching: set PROVIDER + KEY + MODEL together.
    """
    provider = (provider or _env("STRIDE_X_LLM_PROVIDER")).lower() or None

    # Auto-detect if provider not set
    if not provider:
        if _env("STRIDE_X_LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY") and (
            _env("STRIDE_X_LLM_PROVIDER") == "gemini"
            or (_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"))
        ):
            # prefer explicit gemini keys
            if _env("GEMINI_API_KEY", "GOOGLE_API_KEY") and not _env("STRIDE_X_LLM_PROVIDER"):
                # only auto-gemini if gemini-specific key present and no openai sk-
                if _env("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    provider = "gemini"
        if not provider:
            if _env("ANTHROPIC_API_KEY") and not _env("STRIDE_X_LLM_API_KEY"):
                provider = "anthropic"
            elif _env("STRIDE_X_LLM_API_KEY", "OPENAI_API_KEY").startswith("sk-ant"):
                provider = "anthropic"
            elif _env("STRIDE_X_LLM_API_KEY", "OPENAI_API_KEY").startswith("sk-"):
                provider = "openai"
            elif _env("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                provider = "gemini"
            else:
                provider = "ollama"

    if provider not in DEFAULTS:
        raise RuntimeError(
            f"Unknown provider {provider!r}. Use: ollama | openai | gemini | anthropic"
        )

    d = DEFAULTS[provider]

    # Unified names first, then legacy aliases
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

    mdl = (
        model
        or _env("STRIDE_X_LLM_MODEL")
        or _env("OPENAI_MODEL")  # legacy
        or d["model"]
    )

    burl = (
        base_url
        if base_url is not None
        else (_env("STRIDE_X_LLM_BASE_URL") or _env("OPENAI_BASE_URL") or None)
    )
    if not burl:
        burl = d["base_url"]
    if provider == "ollama" and burl and "generativelanguage.googleapis.com" in burl:
        burl = DEFAULTS["ollama"]["base_url"]
    if provider == "ollama" and burl and not burl.rstrip("/").endswith("/v1"):
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

    return {
        "provider": provider,
        "base_url": burl,
        "api_key": key,
        "model": mdl,
    }


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
        temperature=0.2,
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
        temperature=0.2,
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
            "Set the same three variables for any provider:\n"
            "  export STRIDE_X_LLM_PROVIDER=ollama|openai|gemini|anthropic\n"
            "  export STRIDE_X_LLM_API_KEY=...\n"
            "  export STRIDE_X_LLM_MODEL=...\n"
        ) from e


def _slim_findings(result: Dict[str, Any], max_findings: int = 20) -> List[Dict[str, Any]]:
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
            "description": (f.get("description") or "")[:500],
            "category": f.get("category"),
        })
    return out


def explain_findings(result: Dict[str, Any], model: Optional[str] = None, max_findings: int = 18) -> str:
    parts = explain_dual(result, model=model, max_findings=max_findings)
    return (
        "## For leadership (plain language)\n\n"
        + parts["plain"]
        + "\n\n## For technical teams\n\n"
        + parts["technical"]
    )


def explain_dual(
    result: Dict[str, Any],
    model: Optional[str] = None,
    max_findings: int = 18,
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
        "plain": _chat(SYSTEM_PLAIN, "Write the executive briefing.\n\n" + blob, cfg),
        "technical": _chat(SYSTEM_TECH, "Write the technical analysis.\n\n" + blob, cfg),
        "layers": _chat(SYSTEM_LAYERS, "Document each detection layer with findings.\n\n" + blob, cfg),
        "provider": cfg["provider"],
        "model": cfg["model"],
    }
