#!/usr/bin/env python3
"""
Configuration Loader

Loads settings from config.json and .env file.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class MarketConfig:
    """Which Polymarket BTC up/down interval to trade (slug: btc-updown-{5|15}m-<epoch>)."""
    interval_minutes: int = 15

    @property
    def duration_sec(self) -> int:
        return self.interval_minutes * 60

    @property
    def slug_infix(self) -> str:
        """e.g. '5m' or '15m' for btc-updown-5m-..."""
        return f"{self.interval_minutes}m"


@dataclass
class StrategyConfig:
    """Strategy parameters."""
    min_price: float = 0.65
    max_price: float = 0.91
    min_elapsed_sec: int = 480
    min_deviation_pct: float = 5.0
    max_deviation_pct: float = 100.0
    no_entry_before_end_sec: int = 90
    momentum_window_sec: int = 120
    vwap_window_sec: int = 30
    win_rate_csv: str = "data/win_rate.csv"


@dataclass
class EntryConfig:
    """Entry execution parameters."""
    bet_amount_usd: float = 10.0
    price_offset: float = 0.01
    order_type: str = "FAK"
    max_retries: int = 5
    retry_delay_ms: int = 300
    fill_timeout_ms: int = 2000
    min_contracts: int = 5
    min_order_usd: float = 1.0
    max_entry_price: float = 0.91
    ws_recovery_timeout_sec: int = 10


@dataclass
class HedgeConfig:
    """Hedge execution parameters."""
    enabled: bool = True
    hedge_price: float = 0.02
    order_type: str = "GTD"
    max_retries: int = 3
    retry_delay_ms: int = 1000


@dataclass
class RedeemConfig:
    """Auto-redeem parameters."""
    enabled: bool = True
    interval_seconds: int = 180
    auto_confirm: bool = True


@dataclass
class TelegramConfig:
    """Telegram notification parameters."""
    enabled: bool = True
    bot_token: str = ""
    chat_id: str = ""
    chart_every_n_trades: int = 10


@dataclass
class SimulationConfig:
    """
    Paper-trading mode: same WebSockets, signals, and dashboard; no real orders or redeemer.
    When enabled, API keys and private key are optional (not validated).
    """
    enabled: bool = False
    separate_trading_log: bool = True
    trading_log_path: str = "logs/trading_log_sim.json"
    # Analysis exports (OPEN/CLOSE rows, cumulative PnL). Set jsonl path to "" to disable JSONL.
    history_csv_path: str = "logs/simulation_trades.csv"
    history_jsonl_path: str = "logs/simulation_history.jsonl"
    history_summary_path: str = "logs/simulation_summary.json"


@dataclass
class WebDashboardConfig:
    """Optional local web UI (FastAPI). Bind to 127.0.0.1 unless you trust your network."""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class PolymarketConfig:
    """Polymarket API credentials."""
    private_key: str = ""
    funder_address: str = ""
    signature_type: int = 0
    rpc_url: str = "https://polygon-rpc.com"
    chain_id: int = 137
    clob_host: str = "https://clob.polymarket.com"
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""


@dataclass
class Config:
    """Main configuration."""
    market: MarketConfig
    simulation: SimulationConfig
    strategy: StrategyConfig
    entry: EntryConfig
    hedge: HedgeConfig
    redeem: RedeemConfig
    telegram: TelegramConfig
    web_dashboard: WebDashboardConfig
    polymarket: PolymarketConfig


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from JSON file and environment variables.
    
    Args:
        config_path: Path to config.json (default: PROJECT_ROOT/config.json)
    
    Returns:
        Config object with all settings
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "config.json"
    
    # Load JSON config
    with open(config_path, "r") as f:
        data = json.load(f)
    
    # Market interval (5 or 15 minutes)
    market_data = data.get("market", {})
    market = MarketConfig(
        interval_minutes=int(market_data.get("interval_minutes", 15)),
    )

    sim_data = data.get("simulation", {})
    simulation = SimulationConfig(
        enabled=bool(sim_data.get("enabled", False)),
        separate_trading_log=bool(sim_data.get("separate_trading_log", True)),
        trading_log_path=str(sim_data.get("trading_log_path", "logs/trading_log_sim.json")),
        history_csv_path=str(sim_data.get("history_csv_path", "logs/simulation_trades.csv")),
        history_jsonl_path=str(sim_data.get("history_jsonl_path", "logs/simulation_history.jsonl")),
        history_summary_path=str(sim_data.get("history_summary_path", "logs/simulation_summary.json")),
    )

    # Strategy
    strategy_data = data.get("strategy", {})
    strategy = StrategyConfig(
        min_price=strategy_data.get("min_price", 0.65),
        max_price=strategy_data.get("max_price", 0.91),
        min_elapsed_sec=strategy_data.get("min_elapsed_sec", 480),
        min_deviation_pct=strategy_data.get("min_deviation_pct", 5.0),
        max_deviation_pct=strategy_data.get("max_deviation_pct", 100.0),
        no_entry_before_end_sec=strategy_data.get("no_entry_before_end_sec", 90),
        momentum_window_sec=strategy_data.get("momentum_window_sec", 120),
        vwap_window_sec=strategy_data.get("vwap_window_sec", 30),
        win_rate_csv=strategy_data.get("win_rate_csv", "data/win_rate.csv"),
    )
    
    # Entry
    entry_data = data.get("entry", {})
    entry = EntryConfig(
        bet_amount_usd=entry_data.get("bet_amount_usd", 10.0),
        price_offset=entry_data.get("price_offset", 0.01),
        order_type=entry_data.get("order_type", "FAK"),
        max_retries=entry_data.get("max_retries", 5),
        retry_delay_ms=entry_data.get("retry_delay_ms", 300),
        fill_timeout_ms=entry_data.get("fill_timeout_ms", 2000),
        min_contracts=entry_data.get("min_contracts", 5),
        min_order_usd=entry_data.get("min_order_usd", 1.0),
        max_entry_price=entry_data.get("max_entry_price", 0.91),
        ws_recovery_timeout_sec=entry_data.get("ws_recovery_timeout_sec", 10),
    )
    
    # Hedge
    hedge_data = data.get("hedge", {})
    hedge = HedgeConfig(
        enabled=hedge_data.get("enabled", True),
        hedge_price=hedge_data.get("hedge_price", 0.02),
        order_type=hedge_data.get("order_type", "GTD"),
        max_retries=hedge_data.get("max_retries", 3),
        retry_delay_ms=hedge_data.get("retry_delay_ms", 1000),
    )
    
    # Redeem
    redeem_data = data.get("redeem", {})
    redeem = RedeemConfig(
        enabled=redeem_data.get("enabled", True),
        interval_seconds=redeem_data.get("interval_seconds", 180),
        auto_confirm=redeem_data.get("auto_confirm", True),
    )
    
    # Telegram (merge JSON + env)
    telegram_data = data.get("telegram", {})
    telegram = TelegramConfig(
        enabled=telegram_data.get("enabled", True),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        chart_every_n_trades=telegram_data.get("chart_every_n_trades", 10),
    )

    web_data = data.get("web_dashboard", {})
    web_dashboard = WebDashboardConfig(
        enabled=bool(web_data.get("enabled", False)),
        host=str(web_data.get("host", "127.0.0.1")),
        port=int(web_data.get("port", 8765)),
    )
    
    # Polymarket (from env only - secrets)
    polymarket = PolymarketConfig(
        private_key=os.getenv("PRIVATE_KEY", ""),
        funder_address=os.getenv("FUNDER_ADDRESS", ""),
        signature_type=int(os.getenv("SIGNATURE_TYPE", "0")),
        rpc_url=os.getenv("RPC_URL", "https://polygon-rpc.com"),
        chain_id=int(os.getenv("CHAIN_ID", "137")),
        clob_host=os.getenv("CLOB_HOST", "https://clob.polymarket.com"),
        api_key=os.getenv("POLY_API_KEY", ""),
        api_secret=os.getenv("POLY_API_SECRET", ""),
        api_passphrase=os.getenv("POLY_API_PASSPHRASE", ""),
    )
    
    return Config(
        market=market,
        simulation=simulation,
        strategy=strategy,
        entry=entry,
        hedge=hedge,
        redeem=redeem,
        telegram=telegram,
        web_dashboard=web_dashboard,
        polymarket=polymarket,
    )


def validate_config(config: Config) -> list:
    """
    Validate configuration.
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if config.market.interval_minutes not in (5, 15):
        errors.append(
            'market.interval_minutes must be 5 or 15 (Polymarket BTC up/down markets)'
        )

    dur = config.market.duration_sec
    if config.strategy.min_elapsed_sec >= dur:
        errors.append(
            f"strategy.min_elapsed_sec ({config.strategy.min_elapsed_sec}s) must be less than "
            f"market duration ({dur}s for {config.market.interval_minutes}m)"
        )
    if config.strategy.no_entry_before_end_sec >= dur:
        errors.append(
            f"strategy.no_entry_before_end_sec ({config.strategy.no_entry_before_end_sec}s) "
            f"must be less than market duration ({dur}s)"
        )

    live_trading = not config.simulation.enabled

    if live_trading:
        # Required: private key
        if not config.polymarket.private_key:
            errors.append("PRIVATE_KEY not set in .env")
        elif not config.polymarket.private_key.startswith("0x"):
            errors.append("PRIVATE_KEY must start with 0x")

        # Proxy wallet check
        if config.polymarket.signature_type in [1, 2]:
            if not config.polymarket.funder_address:
                errors.append(f"SIGNATURE_TYPE={config.polymarket.signature_type} requires FUNDER_ADDRESS")

        # API credentials
        if not config.polymarket.api_key:
            errors.append("POLY_API_KEY not set")
        if not config.polymarket.api_secret:
            errors.append("POLY_API_SECRET not set")
        if not config.polymarket.api_passphrase:
            errors.append("POLY_API_PASSPHRASE not set")
    
    # Strategy bounds
    if config.strategy.min_price >= config.strategy.max_price:
        errors.append("min_price must be less than max_price")
    
    if config.entry.max_entry_price > config.strategy.max_price:
        errors.append("max_entry_price should not exceed strategy max_price")
    
    if config.strategy.max_deviation_pct <= config.strategy.min_deviation_pct:
        errors.append(
            f"max_deviation_pct ({config.strategy.max_deviation_pct}) "
            f"must be greater than min_deviation_pct ({config.strategy.min_deviation_pct})"
        )

    if config.web_dashboard.enabled:
        if not (1 <= config.web_dashboard.port <= 65535):
            errors.append("web_dashboard.port must be between 1 and 65535")
    
    return errors
