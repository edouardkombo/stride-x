# STRIDE-X

**Stratified Tiered Risk & Integrity Detection Engine**

> Aggregate dashboards ask: *“Did the company have a bad day?”*  
> STRIDE-X asks: *“Where inside a profitable day is margin or data integrity breaking?”*

**Article (project thesis):**  
[Your Dashboard Is Lying to You: Why Top-Line Metrics Are Destroying Enterprise Profitability](https://edouard-kombo.medium.com/your-dashboard-is-lying-to-you-why-top-line-metrics-are-destroying-enterprise-profitability-014ce58596ed)

Version **0.3** — unified LLM config · dual-audience narratives · charted PDF/HTML · BI hand-off pack · Streamlit UI.

---

## The problem (psychology of the blind spot)

Executive tools optimize for **comfort**. A green company KPI is a *net*. In multi-market, multi-platform businesses it can hide large local losses.

Three traps:

1. **Forest vs trees** — Company total looks healthy while Market × Platform cells burn.  
2. **Alert fatigue** — Full granularity without materiality floods teams; thresholds rise until only macro disasters remain.  
3. **Context confusion** — Naive `value ≤ 0` rules treat promotional free-bet settlements like ETL corruption.

STRIDE-X targets the middle: **stratified detection + materiality routing + dual-audience recommendations**.

---

## Regular UAD vs STRIDE-X

| | Regular aggregate UAD | STRIDE-X |
|--|----------------------|----------|
| Grain | Company daily total | Market × Platform × Date (+ period) |
| Question | Bad day? | Where is risk under a green day? |
| Integrity | Blunt sign checks | Domain-aware (promo vs true negatives) |
| Metrics | Single scalar | Financials + engagement vectors |
| Output | Flat flags | Tiered findings, owners, charts, BI artifacts |

Reference run (121k rows): ~**11** macro bad days (Z &lt; −3) vs **4** masked segment losses &gt; €1M (and **25** &gt; €500k) on days the company was still profitable overall.

---

## Detection layers

| Layer | Name | Catches |
|-------|------|---------|
| **L1** | Domain-aware sanitation | Negative stake/volume; zero actives with volume; Stake=0 + P&amp;L semantics |
| **L2** | Stratified surface | Company Z **and** within-segment Z; losses on green company days |
| **L3** | Vector decoupling | Engagement ratios vs financials (e.g. games/active spikes) |
| **L4** | Period structure | Fiscal/period margin collapses |

Severity: **CRITICAL** / **SEVERE** / **OPERATIONAL** / **LOW** (impact tiers configurable).

---

## What you get from a full export

| Artifact | Purpose |
|----------|---------|
| `STRIDE_X_Executive_Report.pdf` | Charted executive PDF |
| `STRIDE_X_Executive_Report.html` | Same story, print-ready HTML (open in browser) |
| `narrative_plain.md` | Leadership: analogy, numbers, **urgent + structural actions** |
| `narrative_technical.md` | Engineering: layers, root-cause hypotheses, **implementation actions** |
| `narrative_layers.md` | Method map for auditors / wiki |
| `stride_x_findings.csv` / `.json` | Source of truth |
| `stride_x_findings.sql` | Warehouse view |
| `schema.yml` | dbt tests |
| `stride_x_findings.view.lkml` | Looker |
| `stride_x_cube.js` | Cube.js |
| `stride_x_measures.dax` | Power BI |
| `tableau_calculated_fields.txt` | Tableau |
| `repro_checks.py` | Pandas re-run of core checks |
| `UAD_vs_STRIDEX.md` | Comparison for *this* run |

Works on messy CSV / Excel / Parquet / JSON with date, profit, volume base, and segment columns (auto-detected).

---

## Install

```bash
cd new_code   # or your clone root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
stride-x doctor   # if entry point available
# or: python -m stride_x.cli --help
```

---

## LLM config (same names for every provider)

```bash
export STRIDE_X_LLM_PROVIDER=ollama|openai|gemini|anthropic
export STRIDE_X_LLM_API_KEY=...
export STRIDE_X_LLM_MODEL=...
```

| Provider | Example |
|----------|---------|
| Ollama (default) | `PROVIDER=ollama` `API_KEY=ollama` `MODEL=llama3.2` |
| Gemini | `PROVIDER=gemini` `API_KEY=…` `MODEL=gemini-2.0-flash` |
| OpenAI | `PROVIDER=openai` `API_KEY=sk-…` `MODEL=gpt-4o-mini` |
| Anthropic | `PROVIDER=anthropic` `API_KEY=sk-ant-…` `MODEL=claude-sonnet-4-5` |

```bash
# verify (no full secret printed)
python -c "from stride_x.llm import resolve_provider; print(resolve_provider())"
```

Narratives use **three** LLM calls (leadership + technical + layers). Prefer cloud models for speed, or skip LLM and use result-aware templates.

---

## How to run

```bash
# Quick scan
python -m stride_x.cli scan -i examples/Flat_Summary.csv

# Full package (templates, no LLM)
python -m stride_x.cli export -i examples/Flat_Summary.csv -o ./audit_out

# Full package + LLM narratives
python -m stride_x.cli export -i examples/Flat_Summary.csv -o ./audit_out --llm
```

Streamlit:

```bash
streamlit run app.py
```

Python:

```python
from stride_x import StrideXEngine, ReportBuilder
from stride_x.narratives import build_split_narratives
from stride_x.artifacts import export_all
from stride_x.pdf_report import write_pdf

result = StrideXEngine().run("data.xlsx")
narratives = build_split_narratives(result)  # or explain_dual(result) with LLM
export_all(result, "audit_out", narratives=narratives)
write_pdf(result, "audit_out/STRIDE_X_Executive_Report.pdf", narratives=narratives)
```

---

## Report quality bar

Leadership section always includes:

- A **business analogy** (forest/stores/highway — not jargon)  
- **Numbers that matter** only from the scan  
- **Urgent fires** and **structural fixes** with owner roles  

Technical section always includes:

- Scan snapshot + UAD comparison  
- Layer findings  
- Root-cause *hypotheses* (integrity vs operational vs product)  
- **Engineering actions** and monitoring to add  

PDF and HTML embed **charts** (top losses, severity mix, layer counts). HTML is the best “elite readable” layout; PDF mirrors it for email packs.

---

## Design honesty

1. Materiality tiers stop pure Z-score floods.  
2. Stake=0 + all-negative P&amp;L is promo-compatible until proven otherwise.  
3. Period vector spikes are signatures for audit — not automatic “fraud” labels.  
4. Classic Microsoft STRIDE security tags are **not** force-mapped onto every margin event.

---

## Project layout

```
new_code/
  README.md
  .env.example
  app.py
  requirements.txt
  pyproject.toml
  stride_x/
    engine.py detectors.py schema.py config.py
    llm.py narratives.py pdf_report.py artifacts.py
    report.py cli.py
    templates/
  examples/
  tests/
```

---

## License

MIT
