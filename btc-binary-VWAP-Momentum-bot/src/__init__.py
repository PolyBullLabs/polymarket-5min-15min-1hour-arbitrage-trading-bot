"""
BTC 15-min Live Trading Bot

Modules:
- market_finder: Find active BTC 15-min markets
- signal_generator: Generate entry signals (VWAP, Deviation, WinRate)
- order_executor: Execute FAK orders with retry logic
- hedge_manager: Hedge positions at 0.99
- position_tracker: Track positions and P&L
- auto_redeemer: Automatic redemption every 3 minutes
- websocket_client: Market + User WebSocket channels
- telegram_notifier: Telegram notifications + charts
- config_loader: Load configuration
"""

__version__ = "1.0.0"
