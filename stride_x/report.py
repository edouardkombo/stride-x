"""Human and machine-readable report builders."""
from __future__ import annotations
from typing import Any, Dict, List
import json
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

class ReportBuilder:
    def __init__(self, result: Dict[str, Any]):
        self.result = result
        self.console = Console()

    def to_dataframe(self) -> pd.DataFrame:
        rows = self.result.get("findings", [])
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def to_csv(self, path: str) -> None:
        self.to_dataframe().to_csv(path, index=False)

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.result, f, indent=2, default=str)

    def print_console(self) -> None:
        r = self.result
        self.console.print(Panel.fit(
            f"[bold]STRIDE-X[/bold]  source={r.get('source')}  rows={r.get('rows'):,}\n"
            f"roles={r.get('roles')}\n"
            f"findings={r.get('finding_count')}  "
            f"CRITICAL={r['by_severity'].get('CRITICAL',0)}  "
            f"SEVERE={r['by_severity'].get('SEVERE',0)}  "
            f"OPERATIONAL={r['by_severity'].get('OPERATIONAL',0)}  "
            f"LOW={r['by_severity'].get('LOW',0)}",
            title="Run Summary",
        ))
        table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Sev", style="bold")
        table.add_column("Layer")
        table.add_column("Title", max_width=48)
        table.add_column("Segment", max_width=28)
        table.add_column("Impact", justify="right")
        for f in r.get("findings", [])[:40]:
            sev = f.get("severity", "")
            style = {"CRITICAL": "red", "SEVERE": "yellow", "OPERATIONAL": "cyan"}.get(sev, "white")
            table.add_row(
                f"[{style}]{sev}[/{style}]",
                f.get("layer", ""),
                f.get("title", "")[:48],
                str(f.get("segment", ""))[:28],
                f"{f.get('impact', 0):,.0f}",
            )
        self.console.print(table)
        if r.get("finding_count", 0) > 40:
            self.console.print(f"... {r['finding_count']-40} more findings (export CSV/JSON for full list)")
