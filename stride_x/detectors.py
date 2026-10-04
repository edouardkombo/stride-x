"""Core detection layers used by STRIDE-X."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from .config import Thresholds, ColumnRoles

Finding = Dict[str, Any]

def _sev_from_impact(impact: float, t: Thresholds) -> str:
    a = abs(impact)
    if a >= t.critical_impact:
        return "CRITICAL"
    if a >= t.severe_impact:
        return "SEVERE"
    if a >= t.operational_impact:
        return "OPERATIONAL"
    return "LOW"

# ---- Layer 1: Domain-aware sanitation / data integrity ----
def detect_data_integrity(df: pd.DataFrame, roles: ColumnRoles, t: Thresholds) -> List[Finding]:
    findings: List[Finding] = []
    stake, vol, act, profit = roles.stake, roles.volume, roles.actives, roles.profit

    if stake and stake in df.columns:
        neg = df[df[stake] < 0]
        if len(neg):
            findings.append({
                "id": "DI-NEG-STAKE",
                "layer": "L1_Integrity",
                "severity": "CRITICAL" if len(neg) > 50 else "SEVERE",
                "category": "Data Integrity",
                "title": "Negative stake / volume base values",
                "description": f"{len(neg)} rows with {stake} < 0 (min={neg[stake].min()}). Impossible for wagered/revenue base amounts.",
                "segment": "Ingestion pipeline",
                "metric_value": float(neg[stake].min()),
                "benchmark": ">= 0",
                "impact": 0.0,
                "count": int(len(neg)),
            })
        zero_act = df[(df[stake] == 0) & (df[profit] != 0)] if profit else pd.DataFrame()
        if len(zero_act):
            all_neg = (zero_act[profit] < 0).all() if profit else False
            findings.append({
                "id": "DI-ZERO-STAKE-PNL",
                "layer": "L1_Integrity",
                "severity": "LOW",
                "category": "Domain / Promo Mechanics",
                "title": "Stake=0 with non-zero profit",
                "description": (
                    f"{len(zero_act)} rows with {stake}=0 and {profit}!=0 "
                    f"(sum profit={zero_act[profit].sum():.2f}). "
                    + ("All negative → consistent with free-bet / promo settlements." if all_neg
                       else "Mixed signs → review before classifying as ETL error.")
                ),
                "segment": "Promo / adjustment layer",
                "metric_value": float(zero_act[profit].sum()),
                "benchmark": "Stake=0 only with documented promo rules",
                "impact": float(zero_act[profit].sum()),
                "count": int(len(zero_act)),
            })

    if vol and vol in df.columns:
        negv = df[df[vol] < 0]
        if len(negv):
            findings.append({
                "id": "DI-NEG-VOLUME",
                "layer": "L1_Integrity",
                "severity": "CRITICAL" if len(negv) > 50 else "SEVERE",
                "category": "Data Integrity",
                "title": "Negative event/volume counts",
                "description": f"{len(negv)} rows with {vol} < 0 (min={negv[vol].min()}).",
                "segment": "Ingestion pipeline",
                "metric_value": float(negv[vol].min()),
                "benchmark": ">= 0",
                "impact": 0.0,
                "count": int(len(negv)),
            })

    if act and vol and act in df.columns and vol in df.columns:
        bad = df[(df[act] == 0) & (df[vol] != 0)]
        if len(bad):
            findings.append({
                "id": "DI-ZERO-ACTIVES",
                "layer": "L1_Integrity",
                "severity": "OPERATIONAL",
                "category": "Data Integrity",
                "title": "Zero actives with non-zero volume",
                "description": f"{len(bad)} rows with {act}=0 but {vol}!=0.",
                "segment": "Identity / activity linkage",
                "metric_value": int(len(bad)),
                "benchmark": "Actives > 0 when volume > 0",
                "impact": 0.0,
                "count": int(len(bad)),
            })
    return findings


# ---- Layer 2: Stratified surface (within-segment temporal Z + masked losses) ----
def detect_stratified(df: pd.DataFrame, roles: ColumnRoles, t: Thresholds) -> List[Finding]:
    findings: List[Finding] = []
    if not roles.date or not roles.profit:
        return findings

    date, profit, stake = roles.date, roles.profit, roles.stake
    segs = [s for s in roles.segment_keys if s in df.columns]

    # Company daily
    daily = df.groupby(date, as_index=False)[profit].sum().rename(columns={profit: "company_profit"})
    daily["z_macro"] = (daily["company_profit"] - daily["company_profit"].mean()) / daily["company_profit"].std(ddof=0)
    macro_bad = daily[daily["z_macro"] < -t.z_critical]
    for _, r in macro_bad.iterrows():
        findings.append({
            "id": f"MACRO-{pd.Timestamp(r[date]).date()}",
            "layer": "L2_Stratified",
            "severity": "CRITICAL",
            "category": "Black-swan day",
            "title": f"Company-level catastrophe {pd.Timestamp(r[date]).date()}",
            "description": f"Daily company profit Z={r['z_macro']:.2f} (profit={r['company_profit']:,.0f}).",
            "segment": "Company total",
            "metric_value": float(r["company_profit"]),
            "benchmark": f"Z > -{t.z_critical}",
            "impact": float(r["company_profit"]),
            "count": 1,
        })

    if not segs:
        return findings

    # Cell grain
    keys = [date] + segs
    cell = df.groupby(keys, as_index=False).agg(
        **{profit: (profit, "sum"), **({stake: (stake, "sum")} if stake else {})}
    )
    cell = cell.merge(daily[[date, "company_profit"]], on=date, how="left")

    # Within-segment temporal Z on profit
    def _z(s: pd.Series) -> pd.Series:
        if len(s) < 5 or s.std(ddof=0) == 0:
            return pd.Series(0.0, index=s.index)
        return (s - s.mean()) / s.std(ddof=0)

    cell["z_within"] = cell.groupby(segs)[profit].transform(_z)

    # Masked losses: company profitable, cell large loss
    masked = cell[(cell["company_profit"] > 0) & (cell[profit] < -t.critical_impact)]
    for _, r in masked.iterrows():
        seg_label = " × ".join(str(r[s]) for s in segs)
        findings.append({
            "id": f"MASKED-{pd.Timestamp(r[date]).date()}-{seg_label}",
            "layer": "L2_Stratified",
            "severity": "CRITICAL",
            "category": "Masked segment loss",
            "title": f"Masked loss on profitable company day ({pd.Timestamp(r[date]).date()})",
            "description": (
                f"{seg_label} lost {r[profit]:,.0f} while company profit was "
                f"+{r['company_profit']:,.0f}. Aggregate dashboards hide this."
            ),
            "segment": seg_label,
            "metric_value": float(r[profit]),
            "benchmark": "No segment loss > critical threshold on green company days",
            "impact": float(r[profit]),
            "count": 1,
        })

    # Extreme within-segment Z on material stake
    if stake:
        extreme = cell[(cell["z_within"] < -t.z_critical) & (cell[stake] >= t.min_stake_for_cell)]
    else:
        extreme = cell[cell["z_within"] < -t.z_critical]
    # limit noise
    extreme = extreme.nsmallest(30, "z_within")
    for _, r in extreme.iterrows():
        seg_label = " × ".join(str(r[s]) for s in segs)
        findings.append({
            "id": f"ZCELL-{pd.Timestamp(r[date]).date()}-{seg_label}",
            "layer": "L2_Stratified",
            "severity": _sev_from_impact(r[profit], t) if r[profit] < 0 else "SEVERE",
            "category": "Within-segment statistical extreme",
            "title": f"Within-segment Z={r['z_within']:.1f} on {pd.Timestamp(r[date]).date()}",
            "description": f"{seg_label} profit={r[profit]:,.0f}, within-segment Z={r['z_within']:.2f}.",
            "segment": seg_label,
            "metric_value": float(r["z_within"]),
            "benchmark": f"|Z| < {t.z_critical}",
            "impact": float(r[profit]),
            "count": 1,
        })

    # Tier counts for reporting
    if stake:
        for thr, label in [
            (1_000_000.0, "1M"),
            (500_000.0, "500k"),
            (250_000.0, "250k"),
        ]:
            n = int(((cell["company_profit"] > 0) & (cell[profit] < -thr)).sum())
            if n:
                findings.append({
                    "id": f"TIER-COUNT-{label}",
                    "layer": "L2_Stratified",
                    "severity": "OPERATIONAL",
                    "category": "Monitoring coverage",
                    "title": f"Masked losses > {label} on profitable days: {n}",
                    "description": f"{n} Market×Platform×Date cells lost more than {thr:,.0f} while company daily profit was positive.",
                    "segment": "All segments",
                    "metric_value": n,
                    "benchmark": "0 preferred under continuous monitoring",
                    "impact": 0.0,
                    "count": n,
                })
        return findings


# ---- Layer 3: Vector decoupling (ratios over time / segments) ----
def detect_vectors(df: pd.DataFrame, roles: ColumnRoles, t: Thresholds) -> List[Finding]:
    findings: List[Finding] = []
    segs = [s for s in roles.segment_keys if s in df.columns]
    act, vol, stake, profit = roles.actives, roles.volume, roles.stake, roles.profit

    if not (act and vol and act in df.columns and vol in df.columns):
        return findings

    # If a week-position like column exists, test period-boundary spikes
    week_col = None
    for c in df.columns:
        if "week" in c.lower() and df[c].dtype == object:
            week_col = c
            break

    if week_col and segs:
        # extract W1..W5
        wp = df[week_col].astype(str).str.extract(r"[Ww](\d)")[0]
        df = df.copy()
        df["_wp"] = wp
        platform_col = segs[-1] if segs else None
        if platform_col:
            for plat, g in df.groupby(platform_col):
                ratios = []
                for w, gw in g.groupby("_wp"):
                    if gw[act].sum() <= 0:
                        continue
                    gpa = gw[vol].sum() / gw[act].sum()
                    ratios.append((w, gpa, gw[stake].sum() if stake else 0,
                                   gw[profit].sum() if profit else 0,
                                   gw[act].sum()))
                if len(ratios) < 2:
                    continue
                # compare W1 vs median of others
                by_w = {w: gpa for w, gpa, *_ in ratios}
                if "1" in by_w:
                    others = [v for k, v in by_w.items() if k != "1"]
                    if others:
                        base = float(np.median(others))
                        r1 = by_w["1"]
                        if base > 0 and r1 / base >= 3.0:
                            # margin check
                            w1_rows = [x for x in ratios if x[0] == "1"][0]
                            margin = (w1_rows[3] / w1_rows[2]) if w1_rows[2] else None
                            findings.append({
                                "id": f"VEC-W1-{plat}",
                                "layer": "L3_Vector",
                                "severity": "SEVERE",
                                "category": "Periodic vector anomaly",
                                "title": f"{plat} Week-1 engagement spike ({r1/base:.1f}×)",
                                "description": (
                                    f"Games/Active in W1={r1:.0f} vs baseline≈{base:.0f} "
                                    f"({r1/base:.1f}×). "
                                    + (f"W1 margin={margin*100:.3f}%." if margin is not None else "")
                                    + " Uniform across segments strongly suggests platform-level "
                                    "period-boundary mechanic or logging rule — audit product vs ETL."
                                ),
                                "segment": str(plat),
                                "metric_value": float(r1 / base),
                                "benchmark": "≈1.0× vs other week positions",
                                "impact": float(w1_rows[3]) if margin is not None and margin < 0.01 else 0.0,
                                "count": 1,
                            })
    return findings


# ---- Layer 4 helpers: severity already assigned; optional period aggregates ----
def detect_period_margin(df: pd.DataFrame, roles: ColumnRoles, t: Thresholds) -> List[Finding]:
    findings: List[Finding] = []
    if not (roles.profit and roles.stake):
        return findings
    # optional Period column
    period_col = None
    for c in df.columns:
        if c.lower() in ("period", "fiscal_period", "month", "ym"):
            period_col = c
            break
    if not period_col:
        return findings
    g = df.groupby(period_col).agg(profit=(roles.profit, "sum"), stake=(roles.stake, "sum"))
    g = g[g["stake"] > 0]
    g["margin"] = g["profit"] / g["stake"]
    if len(g) < 5:
        return findings
    mean_m, std_m = g["margin"].mean(), g["margin"].std(ddof=0)
    if std_m == 0:
        return findings
    g["z"] = (g["margin"] - mean_m) / std_m
    for per, r in g.iterrows():
        if r["z"] < -t.z_critical or r["margin"] < t.catastrophic_margin:
            findings.append({
                "id": f"PERIOD-{per}",
                "layer": "L4_Period",
                "severity": "CRITICAL" if r["margin"] < 0 else "SEVERE",
                "category": "Period margin collapse",
                "title": f"Period {per} margin={r['margin']*100:.2f}% (Z={r['z']:.2f})",
                "description": f"Profit={r['profit']:,.0f}, Stake={r['stake']:,.0f}.",
                "segment": str(per),
                "metric_value": float(r["margin"]),
                "benchmark": f"Mean margin {mean_m*100:.2f}%",
                "impact": float(r["profit"]) if r["profit"] < 0 else 0.0,
                "count": 1,
            })
    return findings
