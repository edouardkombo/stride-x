"""Generate reproducible data-science artifacts from a STRIDE-X result."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


def _findings_df(result: Dict[str, Any]) -> pd.DataFrame:
    rows = result.get("findings") or []
    if not rows:
        return pd.DataFrame(columns=[
            "id", "severity", "layer", "category", "title", "segment",
            "metric_value", "benchmark", "impact", "description", "count",
        ])
    return pd.DataFrame(rows)


def write_sql_view(result: Dict[str, Any], path: Path, table: str = "stride_x_findings") -> None:
    df = _findings_df(result)
    lines = [
        "-- STRIDE-X findings view (generated)",
        f"-- Source: {result.get('source')}",
        f"-- Rows analyzed: {result.get('rows')}",
        f"CREATE OR REPLACE VIEW {table} AS",
    ]
    if df.empty:
        lines.append("SELECT NULL AS id, NULL AS severity WHERE 1=0;")
    else:
        parts = []
        for _, r in df.iterrows():
            def esc(x):
                if x is None or (isinstance(x, float) and pd.isna(x)):
                    return "NULL"
                if isinstance(x, (int, float)):
                    return str(x)
                s = str(x).replace("'", "''")
                return f"'{s}'"
            parts.append(
                "SELECT "
                f"{esc(r.get('id'))} AS id, "
                f"{esc(r.get('severity'))} AS severity, "
                f"{esc(r.get('layer'))} AS layer, "
                f"{esc(r.get('category'))} AS category, "
                f"{esc(r.get('title'))} AS title, "
                f"{esc(r.get('segment'))} AS segment, "
                f"{esc(r.get('metric_value'))} AS metric_value, "
                f"{esc(r.get('benchmark'))} AS benchmark, "
                f"{esc(r.get('impact'))} AS impact, "
                f"{esc(r.get('description'))} AS description"
            )
        lines.append("\nUNION ALL\n".join(parts) + ";")
    path.write_text("\n".join(lines))


def write_dbt_schema(result: Dict[str, Any], path: Path) -> None:
    src = result.get("source")
    path.write_text(textwrap.dedent(f"""\
    version: 2
    models:
      - name: stride_x_findings
        description: "STRIDE-X stratified anomaly findings. Source: {src}"
        columns:
          - name: id
            description: "Finding identifier"
            tests: [unique, not_null]
          - name: severity
            description: "CRITICAL | SEVERE | OPERATIONAL | LOW"
            tests:
              - accepted_values:
                  values: ['CRITICAL', 'SEVERE', 'OPERATIONAL', 'LOW']
          - name: layer
            description: "L1_Integrity | L2_Stratified | L3_Vector | L4_Period"
          - name: impact
            description: "Signed financial impact"
          - name: segment
            description: "Affected segment label"
    """))


def write_lookml(result: Dict[str, Any], path: Path) -> None:
    path.write_text(textwrap.dedent("""\
    view: stride_x_findings {
      sql_table_name: stride_x_findings ;;

      dimension: id { primary_key: yes type: string sql: ${TABLE}.id ;; }
      dimension: severity { type: string sql: ${TABLE}.severity ;; }
      dimension: layer { type: string sql: ${TABLE}.layer ;; }
      dimension: category { type: string sql: ${TABLE}.category ;; }
      dimension: title { type: string sql: ${TABLE}.title ;; }
      dimension: segment { type: string sql: ${TABLE}.segment ;; }
      dimension: description { type: string sql: ${TABLE}.description ;; }

      measure: total_impact {
        type: sum
        sql: ${TABLE}.impact ;;
        value_format_name: decimal_0
      }
      measure: finding_count { type: count }
      measure: critical_count {
        type: count
        filters: [severity: "CRITICAL"]
      }
    }
    """))


def write_cube_js(result: Dict[str, Any], path: Path) -> None:
    path.write_text(textwrap.dedent("""\
    cube(`StrideXFindings`, {
      sql: `SELECT * FROM stride_x_findings`,
      measures: {
        count: { type: `count` },
        totalImpact: { sql: `impact`, type: `sum` },
        criticalCount: {
          type: `count`,
          filters: [{ sql: `${CUBE}.severity = 'CRITICAL'` }],
        },
      },
      dimensions: {
        id: { sql: `id`, type: `string`, primaryKey: true },
        severity: { sql: `severity`, type: `string` },
        layer: { sql: `layer`, type: `string` },
        segment: { sql: `segment`, type: `string` },
        title: { sql: `title`, type: `string` },
      },
    });
    """))


def write_dax(result: Dict[str, Any], path: Path) -> None:
    path.write_text(textwrap.dedent("""\
    -- Power BI / DAX measures for stride_x_findings
    Total Impact = SUM(stride_x_findings[impact])
    Finding Count = COUNTROWS(stride_x_findings)
    Critical Count = CALCULATE(COUNTROWS(stride_x_findings), stride_x_findings[severity] = "CRITICAL")
    Severe Count = CALCULATE(COUNTROWS(stride_x_findings), stride_x_findings[severity] = "SEVERE")
    Abs Impact = SUMX(stride_x_findings, ABS(stride_x_findings[impact]))
    """))


def write_tableau_snippet(result: Dict[str, Any], path: Path) -> None:
    path.write_text(textwrap.dedent("""\
    -- Tableau: connect to stride_x_findings.csv
    -- Calculated field [Critical Flag]:
    IF [severity] = "CRITICAL" THEN 1 ELSE 0 END

    -- Calculated field [Abs Impact]:
    ABS([impact])

    -- Dashboard suggestion:
    -- Rows: severity, layer | Columns: SUM([Abs Impact])
    -- Detail: title, segment, description | Filter: severity
    """))


def write_repro_py(result: Dict[str, Any], path: Path) -> None:
    roles = json.dumps(result.get("roles") or {}, indent=4)
    src = result.get("source")
    path.write_text(
        '"""Reproducible STRIDE-X style checks (pandas).\n'
        f"Source: {src}\n"
        '"""\n'
        "import pandas as pd\n"
        "import numpy as np\n\n"
        "# df = pd.read_csv(\"your_file.csv\")\n"
        f"ROLES = {roles}\n\n"
        "def company_daily_z(df, date_col, profit_col):\n"
        "    d = df.groupby(date_col)[profit_col].sum()\n"
        "    return ((d - d.mean()) / d.std(ddof=0)).sort_values()\n\n"
        "def within_segment_z(df, date_col, seg_cols, profit_col):\n"
        "    g = df.groupby([date_col] + seg_cols)[profit_col].sum().reset_index()\n"
        "    g[\"z\"] = g.groupby(seg_cols)[profit_col].transform(\n"
        "        lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else 0\n"
        "    )\n"
        "    return g.sort_values(\"z\")\n\n"
        "def masked_losses(df, date_col, seg_cols, profit_col, threshold=1_000_000):\n"
        "    daily = df.groupby(date_col)[profit_col].sum().rename(\"company\")\n"
        "    cell = df.groupby([date_col] + seg_cols)[profit_col].sum().reset_index()\n"
        "    cell = cell.merge(daily, on=date_col)\n"
        "    return cell[(cell[\"company\"] > 0) & (cell[profit_col] < -threshold)]\n"
    )


def write_uad_md(result: Dict[str, Any], path: Path) -> None:
    c = result.get("uad_comparison") or {}
    path.write_text(textwrap.dedent(f"""\
    # Regular UAD vs STRIDE-X (this run)

    | Approach | What it measures | This run |
    |----------|------------------|----------|
    | **Regular UAD (aggregate)** | Company-total daily Z-score | Macro bad days (Z < -3): **{c.get('macro_bad_days', 'n/a')}** |
    | **STRIDE-X L2 stratified** | Within-segment Z + masked losses on green days | Masked > 1M: **{c.get('masked_1m', 'n/a')}**; >500k: **{c.get('masked_500k', 'n/a')}** |
    | **STRIDE-X L1 integrity** | Impossible values, promo vs ETL | See L1 findings |
    | **STRIDE-X L3 vectors** | Engagement ratios vs financials | See L3 findings |

    Aggregate UAD answers: *Did the company have a bad day?*
    STRIDE-X answers: *Where inside a profitable day is margin or data integrity breaking?*
    """))


def export_all(
    result: Dict[str, Any],
    out_dir: str | Path,
    narratives: Optional[Dict[str, str]] = None,
) -> List[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []

    df = _findings_df(result)
    p = out / "stride_x_findings.csv"
    df.to_csv(p, index=False)
    written.append(str(p))

    p = out / "stride_x_result.json"
    with open(p, "w") as f:
        json.dump(result, f, indent=2, default=str)
    written.append(str(p))

    for name, fn in [
        ("stride_x_findings.sql", write_sql_view),
        ("schema.yml", write_dbt_schema),
        ("stride_x_findings.view.lkml", write_lookml),
        ("stride_x_cube.js", write_cube_js),
        ("stride_x_measures.dax", write_dax),
        ("tableau_calculated_fields.txt", write_tableau_snippet),
        ("repro_checks.py", write_repro_py),
        ("UAD_vs_STRIDEX.md", write_uad_md),
    ]:
        p = out / name
        fn(result, p)
        written.append(str(p))

    if narratives:
        for key, text in narratives.items():
            p = out / f"narrative_{key}.md"
            p.write_text(text or "")
            written.append(str(p))

    return written
