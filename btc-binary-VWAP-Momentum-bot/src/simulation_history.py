#!/usr/bin/env python3
"""
Append-only simulation trading history for analysis (CSV, JSONL, summary JSON).

Used only when config.simulation.enabled is True.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("btc_live.simulation_history")

CSV_COLUMNS = [
    "event",
    "time_utc",
    "unix_ts",
    "market_slug",
    "side",
    "contracts",
    "entry_price",
    "exit_price",
    "entry_cost_usd",
    "trade_pnl_usd",
    "cumulative_pnl_usd",
    "won",
    "trade_number",
    "total_closed_trades",
    "win_rate_pct",
    "max_dd_abs",
    "max_dd_pct",
    "hedged",
]


def _iso(ts: Optional[float] = None) -> str:
    t = ts if ts is not None else time.time()
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SimulationHistoryLogger:
    """
    Logs each simulated OPEN and CLOSE with per-trade PnL and cumulative realized PnL.
    """

    def __init__(
        self,
        csv_path: str = "logs/simulation_trades.csv",
        jsonl_path: Optional[str] = "logs/simulation_history.jsonl",
        summary_path: str = "logs/simulation_summary.json",
    ):
        self.csv_path = Path(csv_path) if (csv_path or "").strip() else None
        jp = (jsonl_path or "").strip()
        self.jsonl_path = Path(jp) if jp else None
        self.summary_path = Path(summary_path) if (summary_path or "").strip() else None
        self._csv_header_written = (
            bool(self.csv_path and self.csv_path.exists() and self.csv_path.stat().st_size > 0)
        )

    def _append_csv_row(self, row: Dict[str, Any]) -> None:
        if not self.csv_path:
            return
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self._csv_header_written
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            if write_header:
                w.writeheader()
                self._csv_header_written = True
            w.writerow({k: row.get(k, "") for k in CSV_COLUMNS})

    def _append_jsonl(self, obj: Dict[str, Any]) -> None:
        if not self.jsonl_path:
            return
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def log_open(
        self,
        *,
        market_slug: str,
        token_name: str,
        contracts: int,
        avg_price: float,
        total_cost: float,
        cumulative_realized_pnl: float,
        hedged: bool,
        trade_number: int,
    ) -> None:
        """trade_number = count of closed trades + 1 (this open is the Nth position)."""
        ts = time.time()
        row = {
            "event": "OPEN",
            "time_utc": _iso(ts),
            "unix_ts": f"{ts:.3f}",
            "market_slug": market_slug,
            "side": token_name,
            "contracts": contracts,
            "entry_price": f"{avg_price:.6f}",
            "exit_price": "",
            "entry_cost_usd": f"{total_cost:.4f}",
            "trade_pnl_usd": "",
            "cumulative_pnl_usd": f"{cumulative_realized_pnl:.4f}",
            "won": "",
            "trade_number": trade_number,
            "total_closed_trades": "",
            "win_rate_pct": "",
            "max_dd_abs": "",
            "max_dd_pct": "",
            "hedged": hedged,
        }
        self._append_csv_row(row)
        self._append_jsonl(
            {
                "type": "open",
                "time_utc": row["time_utc"],
                "unix_ts": ts,
                "market_slug": market_slug,
                "side": token_name,
                "contracts": contracts,
                "avg_price": avg_price,
                "entry_cost_usd": total_cost,
                "cumulative_realized_pnl_usd": cumulative_realized_pnl,
                "hedged": hedged,
                "trade_number": trade_number,
            }
        )
        logger.info(
            f"[SIM] OPEN {token_name} x{contracts} @ {avg_price:.4f} cost=${total_cost:.2f} | "
            f"realized PnL so far ${cumulative_realized_pnl:+.4f}"
        )

    def log_close(
        self,
        record: Any,  # TradeRecord-like
        *,
        cumulative_pnl: float,
        total_closed: int,
        win_rate_pct: float,
        hedged: bool,
    ) -> None:
        ts = getattr(record, "timestamp", None) or time.time()
        row = {
            "event": "CLOSE",
            "time_utc": _iso(ts),
            "unix_ts": f"{ts:.3f}",
            "market_slug": record.market_slug,
            "side": record.token_name,
            "contracts": record.contracts,
            "entry_price": f"{record.entry_price:.6f}",
            "exit_price": f"{record.exit_price:.6f}",
            "entry_cost_usd": f"{record.contracts * record.entry_price:.4f}",
            "trade_pnl_usd": f"{record.pnl:+.4f}",
            "cumulative_pnl_usd": f"{cumulative_pnl:+.4f}",
            "won": record.won,
            "trade_number": total_closed,
            "total_closed_trades": total_closed,
            "win_rate_pct": f"{win_rate_pct:.2f}",
            "max_dd_abs": f"{record.max_drawdown_abs:.6f}",
            "max_dd_pct": f"{record.max_drawdown_pct:.2f}",
            "hedged": hedged,
        }
        self._append_csv_row(row)
        self._append_jsonl(
            {
                "type": "close",
                "time_utc": row["time_utc"],
                "unix_ts": ts,
                "market_slug": record.market_slug,
                "side": record.token_name,
                "contracts": record.contracts,
                "entry_price": record.entry_price,
                "exit_price": record.exit_price,
                "trade_pnl_usd": record.pnl,
                "cumulative_pnl_usd": cumulative_pnl,
                "won": record.won,
                "trade_number": total_closed,
                "total_closed_trades": total_closed,
                "win_rate_pct": win_rate_pct,
                "max_drawdown_abs": record.max_drawdown_abs,
                "max_drawdown_pct": record.max_drawdown_pct,
                "hedged": hedged,
            }
        )
        logger.info(
            f"[SIM] CLOSE #{total_closed} {record.token_name} PnL ${record.pnl:+.4f} | "
            f"cumulative ${cumulative_pnl:+.4f} | WR {win_rate_pct:.1f}% ({total_closed} trades)"
        )

    def write_summary(self, trades_as_dicts: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
        """Full snapshot for quick analysis (includes all closed trades)."""
        if not self.summary_path:
            return
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "updated_at_utc": _iso(),
            **summary,
            "trades": trades_as_dicts,
        }
        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
