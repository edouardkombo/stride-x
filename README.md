# STRIDE-X

**Stratified Tiered Risk & Integrity Detection Engine**

> Aggregate dashboards answer: *“Did the company have a bad day?”*  
> STRIDE-X answers: *“Where inside a profitable day is margin or data integrity breaking?”*

Version **0.3** — unified LLM config, full audit exports, Streamlit audit UI, Ollama / OpenAI / Gemini / Anthropic.

---

## Why this exists (psychology of the blind spot)

Leadership tools are optimized for **comfort**, not diagnosis. A single green KPI (company daily profit, company margin) creates a false sense of control. In multi-market, multi-platform businesses, that number is a **net** of winners and losers.

Humans and naive monitors both fall for the same trap:

1. **Forest vs trees** — The forest (company total) can look healthy while individual trees (Market × Platform cells) are on fire.
2. **Alert fatigue** — Teams that try full granularity drown in −€400 noise and raise thresholds until only macro disasters remain.
3. **Context confusion** — Blunt rules (`value ≤ 0 → bad`) treat promotional free-bet settlements like ETL corruption.

STRIDE-X is designed for the uncomfortable middle: **stratified signal with materiality routing**, so serious issues surface without requiring the whole company to have a “bad day.”

---

## Differentiation: regular UAD vs STRIDE-X

| | **Regular UAD** (aggregate) | **STRIDE-X** |
|--|------------------------------|--------------|
| Grain | Company (or one entity) daily total | Market × Platform × Date (and period) |
| Question | Did we have a bad day? | Where is risk hiding under a green day? |
| Integrity | Often `≤ 0` = error | Domain-aware (promo netting vs true negatives) |
| Metrics | Single scalar (profit, revenue) | Financials **plus** engagement vectors |
| Output | Flat anomaly list | Tiered findings + owner routing + BI artifacts |

On the reference gaming performance audit (R1, 121k rows):

- Aggregate UAD-style macro Z &lt; −3 ≈ **11** company-bad days  
- STRIDE-X **masked** segment losses on *profitable* company days: **4** &gt; €1M, **25** &gt; €500k  
- Within-segment temporal extremes on green days: hundreds (actionable only with materiality tiers)

---

## Detection layers

| Layer | Name | What it catches |
|-------|------|-----------------|
| **L1** | Domain-aware sanitation | Negative stake/volume; zero actives with volume; Stake=0 + P&amp;L (promo vs ETL) |
| **L2** | Stratified surface | Company-day Z **and** within-segment temporal Z; losses hidden under green company days |
| **L3** | Vector decoupling | Engagement ratios (e.g. games/active) vs stable stake — period-boundary mechanics |
| **L4** | Period structure | Fiscal/period margin collapses vs history |

Severity routing: **CRITICAL** / **SEVERE** / **OPERATIONAL** / **LOW** by impact tiers (configurable).

---

## Value for data science & analytics engineering

STRIDE-X is not only a scanner — each `audit` run emits a **reproducible hand-off pack**:

| Artifact | Use |
|----------|-----|
| `stride_x_findings.csv` / `.json` | Source of truth for findings |
| `stride_x_findings.sql` | Warehouse view |
| `schema.yml` | dbt tests on severity / keys |
| `stride_x_findings.view.lkml` | Looker |
| `stride_x_cube.js` | Cube.js semantic layer |
| `stride_x_measures.dax` | Power BI |
| `tableau_calculated_fields.txt` | Tableau starters |
| `repro_checks.py` | Pandas equivalents of core checks |
| `UAD_vs_STRIDEX.md` | Method comparison for *this* run |
| `narrative_*.md` | Executive + technical + layer docs |
| `STRIDE_X_Report.pdf` (or HTML) | Shareable report |

That closes the gap between “notebook one-off” and something engineering can implement in the semantic layer.

Works on **any messy tabular extract** (CSV, Excel, Parquet, JSON) when you roughly have: date, profit/PnL, volume base (stake/GMV/amount), and segment columns. Names are auto-detected; overrides available.

---

## Install

```bash
cd stride_x
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
stride-x doctor
```

---

## LLM configuration (same names for every provider)

You only change **values**, not variable names. No `unset` required when switching.

```bash
export STRIDE_X_LLM_PROVIDER=ollama|openai|gemini|anthropic
export STRIDE_X_LLM_API_KEY=...
export STRIDE_X_LLM_MODEL=...
# optional:
# export STRIDE_X_LLM_BASE_URL=...
```

Check resolution (key masked):

```bash
stride-x llm-config
```

### Ollama (default — local)

```bash
ollama serve
ollama pull llama3.2

export STRIDE_X_LLM_PROVIDER=ollama
export STRIDE_X_LLM_API_KEY=ollama
export STRIDE_X_LLM_MODEL=llama3.2
```

### Google Gemini

```bash
export STRIDE_X_LLM_PROVIDER=gemini
export STRIDE_X_LLM_API_KEY=your-key-from-aistudio.google.com
export STRIDE_X_LLM_MODEL=gemini-3.8-flash
```

### OpenAI

```bash
export STRIDE_X_LLM_PROVIDER=openai
export STRIDE_X_LLM_API_KEY=sk-...
export STRIDE_X_LLM_MODEL=gpt-4o-mini
```

### Anthropic Claude

```bash
export STRIDE_X_LLM_PROVIDER=anthropic
export STRIDE_X_LLM_API_KEY=sk-ant-...
export STRIDE_X_LLM_MODEL=claude-sonnet-4-5
```

Copy `.env.example` for contributors. Legacy `OPENAI_*` / `GEMINI_API_KEY` still work as fallbacks; **prefer the unified `STRIDE_X_LLM_*` names.**

Narratives run **three** LLM calls (plain + technical + layers). Local models can be slow — use Gemini/OpenAI/Anthropic for speed, or `--no-llm` for offline structured text.

---

## How to run

### Full audit package (recommended)

```bash
stride-x audit path/to/data.xlsx --out-dir ./audit_out
stride-x audit path/to/data.xlsx --out-dir ./audit_out --no-llm   # no LLM wait
```

### Quick scan

```bash
stride-x scan path/to/data.xlsx
stride-x scan path/to/data.xlsx --explain
stride-x scan data.csv --csv-out findings.csv --json-out findings.json
```

### Schema overrides (messy extracts)

```bash
stride-x audit data.csv \
  --date-col Date \
  --profit-col Profit \
  --stake-col Stake \
  --segment-cols Market,Experience \
  --out-dir ./audit_out
```

### Streamlit UI

```bash
streamlit run app.py
```

- Upload file or use example  
- **Quick scan** or **Full audit package**  
- Optional LLM narratives  
- Download findings CSV and full audit ZIP (SQL, LookML, dbt, DAX, Tableau, narratives, PDF/HTML)

---

## Python API

```python
from stride_x import StrideXEngine, ReportBuilder
from stride_x.artifacts import export_all
from stride_x.pdf_report import write_pdf
from stride_x.llm import explain_dual

result = StrideXEngine().run("data.xlsx")
ReportBuilder(result).print_console()

narratives = explain_dual(result)  # uses STRIDE_X_LLM_* env
export_all(result, "audit_out", narratives=narratives)
write_pdf(result, "audit_out/STRIDE_X_Report.pdf", narratives=narratives)
```

---

## Design honesty

1. **Materiality tiers** exist so within-segment Z does not equal infinite alerts.  
2. **Stake=0 + all-negative P&amp;L** is promo-compatible until proven otherwise — not auto-ETL failure.  
3. **Periodic vector spikes** are signatures for product/ETL audit; the engine does not invent root cause.  
4. Classic Microsoft **STRIDE security** labels are not force-mapped onto every margin event (that overclaims).

---

## Project layout

```
stride_x/
  README.md
  .env.example
  pyproject.toml
  requirements.txt
  app.py                 # Streamlit: scan + full audit ZIP
  stride_x/
    engine.py            # orchestration + UAD comparison stats
    detectors.py         # L1–L4
    schema.py            # load + role auto-detect
    config.py            # thresholds
    report.py            # console / CSV / JSON
    llm.py               # unified provider config + dual narratives
    artifacts.py         # SQL, dbt, LookML, Cube, DAX, Tableau, repro
    pdf_report.py        # PDF or HTML fallback
    cli.py               # scan | audit | llm-config | doctor
  examples/
  tests/
```

---

## License

MIT
