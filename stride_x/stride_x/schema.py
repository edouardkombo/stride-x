"""Schema auto-detection and normalization."""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from .config import (
    ColumnRoles, PROFIT_ALIASES, STAKE_ALIASES, ACTIVES_ALIASES,
    VOLUME_ALIASES, DATE_ALIASES, SEGMENT_ALIASES,
)

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")

def _match(col: str, aliases: List[str]) -> bool:
    n = _norm(col)
    return any(a.replace(" ", "_") == n or a.replace(" ", "_") in n or n in a.replace(" ", "_") for a in aliases)

def detect_roles(df: pd.DataFrame, override: Optional[ColumnRoles] = None) -> ColumnRoles:
    roles = override or ColumnRoles()
    cols = list(df.columns)

    if not roles.date:
        for c in cols:
            if _match(c, DATE_ALIASES):
                roles.date = c
                break
        if not roles.date:
            # try dtype
            for c in cols:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    roles.date = c
                    break

    if not roles.profit:
        for c in cols:
            if _match(c, PROFIT_ALIASES):
                roles.profit = c
                break
    if not roles.stake:
        for c in cols:
            if _match(c, STAKE_ALIASES):
                roles.stake = c
                break
    if not roles.actives:
        for c in cols:
            if _match(c, ACTIVES_ALIASES):
                roles.actives = c
                break
    if not roles.volume:
        for c in cols:
            if _match(c, VOLUME_ALIASES):
                roles.volume = c
                break
    if not roles.segment_keys:
        segs = [c for c in cols if _match(c, SEGMENT_ALIASES)]
        roles.segment_keys = segs[:3]  # cap

    return roles

def load_any(path: str) -> pd.DataFrame:
    p = path.lower()
    if p.endswith(".csv"):
        return pd.read_csv(path)
    if p.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    if p.endswith(".parquet"):
        return pd.read_parquet(path)
    if p.endswith(".json"):
        return pd.read_json(path)
    raise ValueError(f"Unsupported format: {path}")

def normalize(df: pd.DataFrame, roles: ColumnRoles) -> pd.DataFrame:
    out = df.copy()
    if roles.date:
        out[roles.date] = pd.to_datetime(out[roles.date], errors="coerce")
    for col in [roles.profit, roles.stake, roles.actives, roles.volume]:
        if col and col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
