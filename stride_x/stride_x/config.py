"""Default detection thresholds and column role mappings."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Thresholds:
    # Materiality tiers (absolute impact in currency units)
    critical_impact: float = 1_000_000.0
    severe_impact: float = 500_000.0
    operational_impact: float = 250_000.0
    # Statistical
    z_critical: float = 3.0
    z_severe: float = 2.0
    # Margin
    industry_margin_low: float = 0.02   # 2%
    industry_margin_high: float = 0.08  # 8%
    catastrophic_margin: float = -0.05  # -5%
    # Volume floors (ignore pure noise)
    min_stake_for_cell: float = 100_000.0
    min_stake_for_margin: float = 1_000.0

@dataclass
class ColumnRoles:
    """Semantic roles. Auto-detected when possible; override via config."""
    date: Optional[str] = None
    segment_keys: List[str] = field(default_factory=list)  # e.g. Market, Platform
    profit: Optional[str] = None
    stake: Optional[str] = None          # volume / revenue base
    actives: Optional[str] = None
    volume: Optional[str] = None         # e.g. Game Count / orders
    week_pos: Optional[str] = None

# Heuristic name maps for auto schema detection
PROFIT_ALIASES = ["profit", "net_profit", "pnl", "net_pnl", "margin_amount", "ggr"]
STAKE_ALIASES = ["stake", "wager", "turnover", "gmv", "volume_value", "amount", "revenue_base"]
ACTIVES_ALIASES = ["actives", "active_users", "users", "unique_users", "dau"]
VOLUME_ALIASES = ["game count", "game_count", "games", "bets", "orders", "transactions", "events"]
DATE_ALIASES = ["date", "day", "dt", "transaction_date", "event_date"]
SEGMENT_ALIASES = ["market", "platform", "experience", "product", "channel", "region", "merchant", "provider"]
