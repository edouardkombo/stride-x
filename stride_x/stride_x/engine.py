"""STRIDE-X orchestration engine."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from .config import Thresholds, ColumnRoles
from .schema import detect_roles, load_any, normalize
from .detectors import (
    detect_data_integrity,
    detect_stratified,
    detect_vectors,
    detect_period_margin,
)

class StrideXEngine:
    """
    Stratified Tiered Risk & Integrity Detection Engine.

    Layers
    ------
    L1  Domain-aware data integrity (negatives, zero-stake semantics)
    L2  Stratified surface (macro Z, within-segment Z, masked losses)
    L3  Vector decoupling (engagement ratios vs financials)
    L4  Period / structural margin collapses + tier routing
    """

    def __init__(
        self,
        thresholds: Optional[Thresholds] = None,
        roles: Optional[ColumnRoles] = None,
    ):
        self.thresholds = thresholds or Thresholds()
        self.role_override = roles

    def run(self, data: str | Path | pd.DataFrame) -> Dict[str, Any]:
        if isinstance(data, (str, Path)):
            df = load_any(str(data))
            source = str(data)
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
            source = "<dataframe>"
        else:
            raise TypeError(f"Unsupported input type for StrideXEngine.run: {type(data)}")

        roles = detect_roles(df, self.role_override)
        df = normalize(df, roles)

        findings: List[Dict[str, Any]] = []
        findings += detect_data_integrity(df, roles, self.thresholds)
        findings += detect_stratified(df, roles, self.thresholds)
        findings += detect_vectors(df, roles, self.thresholds)
        findings += detect_period_margin(df, roles, self.thresholds)

        # rank
        order = {"CRITICAL": 0, "SEVERE": 1, "OPERATIONAL": 2, "LOW": 3}
        findings.sort(key=lambda f: (order.get(f.get("severity", "LOW"), 9), f.get("impact", 0)))

        # UAD comparison stats (aggregate vs stratified)
        uad = {"macro_bad_days": 0, "masked_1m": 0, "masked_500k": 0, "masked_250k": 0}
        for f in findings:
            if f.get("id", "").startswith("MACRO-"):
                uad["macro_bad_days"] += 1
            if f.get("id") == "TIER-COUNT-1M":
                uad["masked_1m"] = f.get("count", 0)
            if f.get("id") == "TIER-COUNT-500k":
                uad["masked_500k"] = f.get("count", 0)
            if f.get("id") == "TIER-COUNT-250k":
                uad["masked_250k"] = f.get("count", 0)

        summary = {
            "source": source,
            "rows": int(len(df)),
            "columns": list(df.columns),
            "roles": {
                "date": roles.date,
                "profit": roles.profit,
                "stake": roles.stake,
                "actives": roles.actives,
                "volume": roles.volume,
                "segments": roles.segment_keys,
            },
            "finding_count": len(findings),
            "by_severity": {
                k: sum(1 for f in findings if f.get("severity") == k)
                for k in ["CRITICAL", "SEVERE", "OPERATIONAL", "LOW"]
            },
            "uad_comparison": uad,
            "findings": findings,
        }
        return summary
