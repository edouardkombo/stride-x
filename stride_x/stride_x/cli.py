"""STRIDE-X Command-Line Interface.

Provides CLI access for scanning datasets, exporting full audit packages (CSV, SQL,
LookML, dbt, DAX, PDF/HTML reports), and previewing narrative briefs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import StrideXEngine
from .config import Thresholds
from .report import ReportBuilder
from .artifacts import export_all
from .pdf_report import write_pdf
from .narratives import build_split_narratives


def _get_narratives(result: dict, use_llm: bool = False) -> dict:
    """Dual-audience narratives: LLM when requested, else result-aware templates."""
    if use_llm:
        try:
            from .llm import explain_dual
            narratives = explain_dual(result)
            print(f"[INFO] LLM narratives via {narratives.get('provider')}/{narratives.get('model')}")
            return narratives
        except Exception as e:
            print(f"[WARN] LLM failed ({e}). Using structured analytical narratives.", file=__import__('sys').stderr)
    return build_split_narratives(result)



def _fallback_plain(result: dict) -> str:
    """Plain-language executive fallback explanation with business analogies."""
    f_count = result.get("finding_count", 0)
    crit = result.get("by_severity", {}).get("CRITICAL", 0)
    uad = result.get("uad_comparison", {})
    masked = uad.get("masked_1m", 0)

    return (
        f"### Executive Summary & Business Analogy\n\n"
        f"**Business Analogy:** Imagine running a chain of 100 successful retail stores. "
        f"Overall daily revenue is reaching record highs, making the company look green and healthy. "
        f"However, in 3 specific sub-segments, a checkout glitch is giving away free premium products. "
        f"Because the other 97 stores perform exceptionally well, overall profit masks this severe daily leak.\n\n"
        f"**Key Findings:**\n"
        f"- Detected **{f_count}** total integrity and loss findings across active layers.\n"
        f"- **{crit}** critical findings require immediate executive attention.\n"
        f"- Identified **{masked}** masked loss instances exceeding $1,000,000 on green net-profit days.\n\n"
        f"**Leadership Action Items:**\n"
        f"1. **Pause High-Risk Spending:** Freeze promotional budgets on identified outlier sub-segments immediately.\n"
        f"2. **Cross-Functional Alignment:** Instruct Finance and Marketing leads to reconcile daily marketing credits against gateway ledgers.\n"
        f"3. **Enforce Governance:** Establish hard stop-loss threshold policies per campaign account."
    )


def _fallback_technical(result: dict) -> str:
    """Technical engineering fallback explanation with root-cause tasks."""
    f_count = result.get("finding_count", 0)
    by_sev = result.get("by_severity", {})

    return (
        f"### Technical Engineering & Data Risk Analysis\n\n"
        f"**Scan Metrics:** {f_count} findings (CRITICAL: {by_sev.get('CRITICAL', 0)}, "
        f"SEVERE: {by_sev.get('SEVERE', 0)}, OPERATIONAL: {by_sev.get('OPERATIONAL', 0)}).\n\n"
        f"**Layer Breakdown & Remediation Plan:**\n"
        f"- **L1 Integrity:** Audit ingestion scripts for null-padding and missing foreign key joins on promo attribution tables.\n"
        f"- **L2 Anomaly Detection:** Implement windowed rolling 30-day Z-score baseline models in dbt to replace static thresholding.\n"
        f"- **L3 Vector Reconciliation:** Deploy dynamic micro-batch reconciliation queries comparing engagement click logs with transaction ledgers every 2 hours.\n"
        f"- **L4 Period Metrics:** Establish automated tracking on long-term subscription margin erosion."
    )


def _fallback_layers(result: dict) -> str:
    """Layer method summary fallback."""
    return (
        "### STRIDE-X Framework Layers\n\n"
        "1. **L1 Integrity Layer:** Domain-aware ETL check for negative prices, invalid discounts, or orphaned join keys.\n"
        "2. **L2 Stratified Anomaly Layer:** Segment-level Z-score anomaly scanning on green company revenue days.\n"
        "3. **L3 Vector Layer:** Engagement vs. financial vector alignment (identifying zero-revenue click spikes).\n"
        "4. **L4 Period Layer:** Multi-period structural trend and margin degradation analysis."
    )


def cmd_scan(args: argparse.Namespace) -> None:
    """Executes a quick analytical scan and outputs summary to stdout."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    engine = StrideXEngine(thresholds=Thresholds(critical_impact=args.critical, z_critical=args.z_thr))
    result = engine.run(input_path)

    df = ReportBuilder(result).to_dataframe()
    print("=" * 60)
    print("STRIDE-X SCAN RESULTS SUMMARY")
    print("=" * 60)
    print(f"Rows Processed : {result.get('rows', 0):,}")
    print(f"Total Findings : {result.get('finding_count', 0)}")
    print(f"Severity Breakdown: {result.get('by_severity', {})}")
    print("-" * 60)

    if not df.empty:
        print("\nTop 10 Findings by Financial Impact:")
        print(df[["id", "layer", "severity", "impact", "title"]].head(10).to_string(index=False))
    else:
        print("\nNo findings detected under the specified thresholds.")


def cmd_export(args: argparse.Namespace) -> None:
    """Runs a full audit scan and exports all artifacts (SQL, LookML, dbt, DAX, PDF/HTML)."""
    input_path = Path(args.input)
    out_dir = Path(args.out_dir)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    engine = StrideXEngine(thresholds=Thresholds(critical_impact=args.critical, z_critical=args.z_thr))
    result = engine.run(input_path)
    narratives = _get_narratives(result, use_llm=args.llm)

    written = export_all(result, out_dir, narratives=narratives)
    pdf_path = write_pdf(result, out_dir / "STRIDE_X_Executive_Report.pdf", narratives=narratives)
    written.append(pdf_path)

    print("=" * 60)
    print("STRIDE-X AUDIT PACKAGE EXPORT COMPLETE")
    print("=" * 60)
    print(f"Destination Directory : {out_dir.resolve()}")
    print(f"Generated Files ({len(written)}):")
    for w in written:
        print(f"  - {Path(w).name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stride_x",
        description="STRIDE-X: Stratified Tiered Risk & Integrity Detection Engine CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: scan
    p_scan = subparsers.add_parser("scan", help="Run a quick scan on a dataset")
    p_scan.add_argument("-i", "--input", required=True, help="Path to CSV/Parquet/XLSX/JSON dataset")
    p_scan.add_argument("--critical", type=float, default=1_000_000.0, help="Critical financial impact threshold")
    p_scan.add_argument("--z-thr", type=float, default=3.0, help="Z-score anomaly threshold")
    p_scan.set_defaults(func=cmd_scan)

    # Subcommand: export
    p_export = subparsers.add_parser("export", help="Run full scan and export audit package + PDF/HTML report")
    p_export.add_argument("-i", "--input", required=True, help="Path to CSV/Parquet/XLSX/JSON dataset")
    p_export.add_argument("-o", "--out-dir", default="./stride_x_audit_output", help="Output directory for package")
    p_export.add_argument("--critical", type=float, default=1_000_000.0, help="Critical financial impact threshold")
    p_export.add_argument("--z-thr", type=float, default=3.0, help="Z-score anomaly threshold")
    p_export.add_argument("--llm", action="store_true", help="Generate AI narratives using configured LLM provider")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
