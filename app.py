"""Streamlit UI — scan + full audit package (artifacts, narratives, PDF)."""
from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

import streamlit as st
import pandas as pd

st.set_page_config(page_title="STRIDE-X", layout="wide", page_icon="🛡️")
st.title("STRIDE-X")
st.caption("Stratified Tiered Risk & Integrity Detection Engine")

with st.sidebar:
    st.header("1. Data")
    up = st.file_uploader("Upload CSV / Excel / JSON / Parquet", type=["csv", "xlsx", "xls", "json", "parquet"])
    example = st.selectbox("Or example file", ["(none)", "examples/Flat_Summary.csv"])

    st.header("2. Thresholds")
    critical = st.number_input("Critical impact", value=1_000_000.0, step=100_000.0)
    z_thr = st.number_input("|Z| threshold", value=3.0, step=0.5)

    st.header("3. LLM (optional)")
    st.markdown(
        "Uses env: `STRIDE_X_LLM_PROVIDER`, `STRIDE_X_LLM_API_KEY`, `STRIDE_X_LLM_MODEL` "
        "(same names for Ollama / OpenAI / Gemini / Anthropic)."
    )
    use_llm = st.checkbox("Generate dual-audience narratives", value=False)
    try:
        from stride_x.llm import resolve_provider
        cfg = resolve_provider()
        st.info(f"Active: **{cfg['provider']}** / `{cfg['model']}`")
    except Exception as e:
        st.warning(str(e))

    st.header("4. Run")
    mode = st.radio("Mode", ["Quick scan", "Full audit package"], index=1)
    run = st.button("Run", type="primary")

if not run:
    st.markdown(
        """
### What STRIDE-X does
Aggregate dashboards answer *“Did the company have a bad day?”*  
STRIDE-X answers *“Where inside a profitable day is margin or data integrity breaking?”*

| Layer | Focus | Analogy |
|-------|--------|---------|
| L1 | Domain-aware data integrity (negatives, promo vs ETL) | *Checking if store checkout registers are broken* |
| L2 | Within-segment Z + masked losses on green company days | *Finding a burning store inside a profitable retail chain* |
| L3 | Engagement vectors vs financials | *Detecting phantom traffic inflating billings* |
| L4 | Period margin structure | *Spotting silent leakages in monthly subscriptions* |

Upload a multi-segment performance file, then **Run**.
"""
    )
    st.stop()

from stride_x import StrideXEngine, ReportBuilder
from stride_x.config import Thresholds
from stride_x.artifacts import export_all
from stride_x.pdf_report import write_pdf
from stride_x.cli import _fallback_plain, _fallback_technical, _fallback_layers

# Resolve input path
path = None
if up is not None:
    suffix = Path(up.name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(up.getbuffer())
    tmp.close()
    path = tmp.name
elif example != "(none)" and Path(example).exists():
    path = example
else:
    st.error("Upload a file or place examples/Flat_Summary.csv")
    st.stop()

engine = StrideXEngine(thresholds=Thresholds(critical_impact=critical, z_critical=z_thr))
with st.spinner("Scanning…"):
    result = engine.run(path)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows", f"{result['rows']:,}")
c2.metric("Findings", result["finding_count"])
c3.metric("CRITICAL", result["by_severity"].get("CRITICAL", 0))
c4.metric("SEVERE", result["by_severity"].get("SEVERE", 0))
c5.metric("OPERATIONAL", result["by_severity"].get("OPERATIONAL", 0))

u = result.get("uad_comparison") or {}
st.markdown(
    f"**UAD vs STRIDE-X:** macro bad days (Z<-3) ≈ **{u.get('macro_bad_days', 0)}** · "
    f"masked losses on green days >1M **{u.get('masked_1m', 0)}** · "
    f">500k **{u.get('masked_500k', 0)}**"
)

st.subheader("Detected roles")
st.json(result["roles"])

df = ReportBuilder(result).to_dataframe()
if df.empty:
    st.success("No findings under current thresholds.")
else:
    st.subheader("Findings")
    st.dataframe(df, use_container_width=True)
    st.download_button("Download findings CSV", df.to_csv(index=False), "stride_x_findings.csv", "text/csv")
    
    # Graphs & Charts inside UI
    try:
        import plotly.express as px
        plot_df = df.copy()
        plot_df["abs_impact"] = plot_df["impact"].abs()
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            fig_bar = px.bar(
                plot_df.head(30), x="id", y="abs_impact", color="severity",
                title="Top findings by |impact| ($)",
                color_discrete_map={
                    "CRITICAL": "#e74c3c", "SEVERE": "#f39c12",
                    "OPERATIONAL": "#3498db", "LOW": "#95a5a6",
                },
                template="plotly_white",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with col_c2:
            fig_pie = px.pie(
                plot_df, names="severity", values="abs_impact",
                title="Exposure Distribution by Severity",
                color="severity",
                color_discrete_map={
                    "CRITICAL": "#e74c3c", "SEVERE": "#f39c12",
                    "OPERATIONAL": "#3498db", "LOW": "#95a5a6",
                },
                hole=0.4, template="plotly_white",
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    except Exception:
        pass

narratives = {
    "plain": _fallback_plain(result),
    "technical": _fallback_technical(result),
    "layers": _fallback_layers(result),
}

if use_llm:
    with st.spinner("LLM narratives (3 calls: plain + technical + layers)…"):
        try:
            from stride_x.llm import explain_dual
            narratives = explain_dual(result)
            st.success(f"Narratives from {narratives.get('provider')}/{narratives.get('model')}")
        except Exception as e:
            st.error(f"LLM failed — using structured fallbacks. {e}")

st.subheader("Executive Briefing & Actions")
st.markdown(narratives.get("plain") or "")

with st.expander("Technical Analysis & Engineering Tasks"):
    st.markdown(narratives.get("technical") or "")

with st.expander("Layer-by-Layer Method"):
    st.markdown(narratives.get("layers") or "")

if mode == "Full audit package":
    out = Path(tempfile.mkdtemp(prefix="stride_x_audit_"))
    written = export_all(result, out, narratives=narratives)
    pdf_path = write_pdf(result, out / "STRIDE_X_Report.pdf", narratives=narratives)
    written.append(pdf_path)

    st.subheader("Export package")
    st.write(f"Generated **{len(written)}** files in session temp dir.")
    
    zip_base = out.parent / out.name
    shutil.make_archive(str(zip_base), "zip", out)
    zip_path = Path(str(zip_base) + ".zip")
    st.download_button(
        "Download full audit ZIP (CSV, SQL, LookML, dbt, DAX, Tableau, narratives, PDF/HTML)",
        zip_path.read_bytes(),
        file_name="stride_x_audit_package.zip",
        mime="application/zip",
        type="primary",
    )
    st.code("\n".join(Path(w).name for w in written), language=None)
