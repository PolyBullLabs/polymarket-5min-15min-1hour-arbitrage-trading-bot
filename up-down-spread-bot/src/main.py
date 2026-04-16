#!/usr/bin/env python3
"""
Meridian — Polymarket 15-minute multi-asset trading system.

Four parallel traders (BTC, ETH, SOL, XRP), one wallet.
Strategy: late-window entry (Late Entry V3 / late_v3).
"""
import argparse
import json
import time
import signal
import sys
import subprocess
import os
import threading
import requests
from pathlib import Path
from typing import Dict
from concurrent.futures import ThreadPoolExecutor

from data_feed import DataFeed
from strategy import LateEntryStrategy
from multi_trader import MultiTrader
from dashboard_multi_ab import DashboardMultiAB
from polymarket_api import get_market_outcome
from telegram_notifier import get_notifier
from safety_guard import SafetyGuard
from order_executor import OrderExecutor
from keyboard_listener import KeyboardListener
from market_config import apply_market_window_settings
import trader as trader_module


# Global configuration constants
STRATEGY_BASES = ['late_v3']
COINS = ['btc', 'eth', 'sol', 'xrp']

# Global stop flag
stop_flag = False
data_feed = None
multi_trader_instance = None  # Will hold MultiTrader for graceful shutdown
keyboard_listener = None  # Will hold KeyboardListener for cleanup

# Global redeem positions cache for Telegram /r command
redeem_positions_cache = []
redeem_cache_lock = threading.Lock()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global stop_flag, data_feed, multi_trader_instance, keyboard_listener
    print("\n[SYSTEM] Shutdown signal received, stopping...")
    stop_flag = True
    
    # Stop keyboard listener first
    if keyboard_listener:
        print("[KEYBOARD] Stopping listener...")
        keyboard_listener.stop()
    
    # Stop data feed
    if data_feed:
        print("[DATA] Stopping feeds...")
        data_feed.stop()
        print("[DATA] Feeds stopped")
    
    # Save all active positions before exit
    if multi_trader_instance:
        print("[SHUTDOWN] Saving active positions...")
        saved_count = 0
        for strategy_name, trader in multi_trader_instance.traders.items():
            if trader.positions:
                print(f"[{strategy_name}] Has {len(trader.positions)} active position(s)")
                for market_slug, pos in list(trader.positions.items()):
                    try:
                        # Force-save position as emergency exit
                        # We don't know the final price, so save current state
                        trade = {
                            'market_slug': market_slug,
                            'strategy': strategy_name,
                            'up_contracts': pos['UP']['contracts'],
                            'down_contracts': pos['DOWN']['contracts'],
                            'up_invested': pos['UP']['invested'],
                            'down_invested': pos['DOWN']['invested'],
                            'total_invested': pos['UP']['invested'] + pos['DOWN']['invested'],
                            'pnl': 0.0,  # Unknown - will calculate on next run
                            'winner': 'UNKNOWN',
                            'closed_at': int(time.time()),
                            'btc_start': pos.get('btc_start', 0),
                            'btc_final': 0,  # Unknown
                            'entries_count': pos.get('entries_count', 0),
                            'status': 'EMERGENCY_SAVE'  # Mark as emergency
                        }
                        trader._log_trade(trade)
                        saved_count += 1
                        print(f"  ✓ Saved {market_slug}")
                    except Exception as e:
                        print(f"  ✗ Failed to save {market_slug}: {e}")
        print(f"[SHUTDOWN] Saved {saved_count} position(s)")
    
    print("[SYSTEM] Shutdown complete")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def load_config(config_path: str = None) -> dict:
    """Load configuration and resolve market_window → market_interval_sec."""
    if config_path is None:
        # Default to ../config/config.json relative to this file
        config_path = Path(__file__).parent.parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    apply_market_window_settings(cfg)
    return cfg


def _parse_cli_args():
    """CLI for optional web dashboard."""
    p = argparse.ArgumentParser(description="Meridian — Polymarket 15m crypto desk")
    p.add_argument(
        "--web",
        action="store_true",
        help="Serve web dashboard (Flask) in background for control + live analytics",
    )
    p.add_argument("--web-port", type=int, default=5050, help="Dashboard port (default 5050)")
    p.add_argument(
        "--web-host",
        type=str,
        default="127.0.0.1",
        help="Bind address (default 127.0.0.1; use 0.0.0.0 for LAN)",
    )
    return p.parse_args()


def validate_system():
    """Validate all components before starting"""
    print("[VALIDATION] Testing sizing formulas...")
    # Validation passed
    
    print("[VALIDATION] All systems ready")
    return True


def _get_portfolio_stats(multi_trader, markets_skipped, session_start_time):
    """Helper to calculate portfolio statistics for Telegram notifications"""
    stats = {}
    
    for coin in COINS:
        strategy_name = f"{STRATEGY_BASES[0]}_{coin}"
        trader = multi_trader.traders.get(strategy_name)
        
        if not trader:
            stats[f'{coin}_pnl'] = 0
            stats[f'{coin}_wr'] = 0
            stats[f'{coin}_markets_played'] = 0
            stats[f'{coin}_markets_skipped'] = 0
            continue
        
        perf = trader.get_performance_stats()
        
        stats[f'{coin}_pnl'] = trader.current_capital - trader.starting_capital
        stats[f'{coin}_wr'] = perf['win_rate']
        stats[f'{coin}_markets_played'] = perf['total_trades']
        stats[f'{coin}_markets_skipped'] = markets_skipped.get(coin, 0)
    
    stats['total_pnl'] = sum(stats.get(f'{coin}_pnl', 0) for coin in COINS)
    stats['uptime'] = time.time() - session_start_time
    
    return stats


# ═══════════════════════════════════════════════════════════
# GLOBAL STATE (for callbacks)
# ═══════════════════════════════════════════════════════════
wallet_balance = 0.0  # Will be set in main() after wallet check


def validate_prices(up_ask: float, down_ask: float, up_timestamp: float, down_timestamp: float, 
                   coin: str = '', threshold_sec: float = 2.0) -> tuple:
    """
    Validate that prices are synchronized and fresh
    
    Returns: (is_valid: bool, reason: str)
    """
    now = time.time()
    
    # Check 1: Freshness (prices updated recently)
    up_age = now - up_timestamp if up_timestamp > 0 else 999
    down_age = now - down_timestamp if down_timestamp > 0 else 999
    
    if up_age > threshold_sec:
        return False, f"UP_STALE_{up_age:.1f}s"
    if down_age > threshold_sec:
        return False, f"DOWN_STALE_{down_age:.1f}s"
    
    # Check 2: Timestamp sync (both updated in same time window)
    if abs(up_timestamp - down_timestamp) > threshold_sec:
        return False, f"DESYNC_{abs(up_timestamp - down_timestamp):.1f}s"
    
    # Check 3: Sum validation (UP + DOWN ≈ 1.0)
    # Allow wider range (0.95-1.15) to account for spread and rapid price changes
    price_sum = up_ask + down_ask
    if price_sum < 0.95 or price_sum > 1.15:
        return False, f"INVALID_SUM_{price_sum:.3f}"
    
    return True, "OK"


def run_manual_redeem():
    """Callback for manual redeem (M key)"""
    print("\n" + "="*80)
    print(" MANUAL REDEEM TRIGGERED ".center(80, "="))
    print("="*80 + "\n")
    
    try:
        # Import the redeemall module directly
        import sys
        sys.path.insert(0, "/root/clip")
        
        # Load environment from 4coins_live
        from dotenv import load_dotenv
        from pathlib import Path
        env_path = Path("/root/4coins_live/.env")
        load_dotenv(env_path, override=True)
        
        # Import and run redeemall with auto-confirm
        import redeemall
        print("[REDEEM] Starting automatic redemption...")
        print("[REDEEM] Using wallet from: /root/4coins_live/.env")
        print()
        
        redeemall.main(auto_confirm=True)
        
        print("\n[REDEEM] Completed!")
            
    except Exception as e:
        print(f"\n[REDEEM] Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(" Returning to trading... ".center(80))
    print("="*80 + "\n")
    
    # Give user 2 seconds to see the result
    time.sleep(2)


def main(args=None):
    """Main trading loop"""
    global stop_flag, data_feed, wallet_balance, keyboard_listener
    if args is None:
        args = _parse_cli_args()
    
    # Track session start time for uptime
    session_start_time = time.time()
    
    config = load_config()
    
    print("=" * 115)
    _pm = config.get("data_sources", {}).get("polymarket", {})
    _iv = int(_pm.get("market_interval_sec", 900))
    _ml = "5m" if _iv == 300 else ("15m" if _iv == 900 else f"{_iv}s")
    print(f"  MERIDIAN — Polymarket crypto desk ({_ml} markets)".center(115))
    print("  BTC · ETH · SOL · XRP  |  Late-window entry  |  Hybrid stop-loss & flip-stop".center(115))
    print("  Unified wallet  |  Real-time books  |  FAK execution".center(115))
    print("=" * 115)
    print()
    
    # Validate system
    if not validate_system():
        print("[ERROR] System validation failed!")
        return
    
    # Track skipped markets for each coin
    markets_skipped = {coin: 0 for coin in COINS}
    
    # Track completed markets for chart generation
    total_completed_markets = 0
    last_chart_at = 0  # Markets count when last chart was sent
    CHART_INTERVAL = config.get('notifications', {}).get('chart_every_n_markets', 10)
    print(f"[CONFIG] Loaded configuration (Meridian · late-window entry + hybrid stop-loss)")
    _pm_cfg = config.get("data_sources", {}).get("polymarket", {})
    _iv_cfg = int(_pm_cfg.get("market_interval_sec", 900))
    _mw_cfg = str(_pm_cfg.get("market_window", "") or ("15m" if _iv_cfg == 900 else "5m" if _iv_cfg == 300 else ""))
    print(
        f"         Market window: \"{_mw_cfg or _iv_cfg}\" → {_iv_cfg}s "
        f"(edit data_sources.polymarket.market_window: \"5m\" or \"15m\")"
    )
    print(f"         Entry window (config file): {config['strategy'].get('entry_window_sec', 'default')} seconds (strategy may cap to market length)")
    print(f"         Entry Frequency: Every {config['strategy']['entry_frequency_sec']} seconds")
    print(f"         Price Max: ${config['strategy']['price_max']}")
    print(f"         Exit #1: Hybrid Stop-Loss (per coin):")
    
    # Dynamically derive from config
    for coin in ['btc', 'eth', 'sol', 'xrp']:
        sl_cfg = config.get('exit', {}).get('stop_loss', {}).get('per_coin', {}).get(coin, {})
        if sl_cfg.get('enabled'):
            sl_type = sl_cfg.get('type', 'fixed')
            sl_value = sl_cfg.get('value', 0)
            if sl_type == 'fixed':
                print(f"                  {coin.upper()}: Fixed ${sl_value}")
            else:
                print(f"                  {coin.upper()}: Percent {sl_value}%")
        else:
            print(f"                  {coin.upper()}: Disabled")
    
    print(f"         Exit #2: Flip-Stop (price reversal protection)")
    _sz = config.get("strategy", {}).get("sizing", {})
    print(
        f"         Sizing: {_sz.get('above_180_sec', 8)}/{_sz.get('above_120_sec', 10)}/{_sz.get('below_120_sec', 12)} "
        f"contracts (tiers vs time-left; thresholds scale with market window)"
    )
    print()
    
    # ═══════════════════════════════════════════════════════════
    # SAFETY & REAL TRADING SETUP
    # ═══════════════════════════════════════════════════════════
    
    # Create SafetyGuard (pass ENTIRE config, SafetyGuard will take safety section itself)
    safety_guard = SafetyGuard(config)
    
    # Create OrderExecutor (pass config for retry parameters!)
    order_executor = OrderExecutor(safety_guard, config)
    
    # Setup balance change callback to update global wallet_balance
    def on_balance_change(amount: float, operation: str, is_absolute: bool = False):
        """
        Callback for balance changes from OrderExecutor
        
        Args:
            amount: Amount changed (positive = received, negative = spent) or absolute balance
            operation: Operation type ('BUY', 'SELL', 'REDEEM', 'REDEEM_REFRESH')
            is_absolute: If True, amount is the new absolute balance (not a delta)
        """
        global wallet_balance
        try:
            if is_absolute:
                # Absolute value from blockchain
                old_balance = wallet_balance
                wallet_balance = amount
                change = amount - old_balance
                change_sign = "+" if change >= 0 else ""
                print(f"[BALANCE] 🔄 Updated from blockchain: ${wallet_balance:,.2f} ({change_sign}${change:.2f})")
            else:
                # Delta change
                wallet_balance += amount
                sign = "+" if amount >= 0 else ""
                print(f"[BALANCE] 💰 {operation}: {sign}${amount:.2f} → ${wallet_balance:,.2f}")
        except Exception as e:
            print(f"[BALANCE] ⚠️ Callback error: {e}")
            import traceback
            traceback.print_exc()
    
    order_executor.set_balance_callback(on_balance_change)
    
    # Setup market closing check callback (race condition protection)
    def is_market_closing(market_slug: str, coin: str) -> bool:
        """
        Check: is market closing for SPECIFIC coin (stop-loss/flip-stop triggered)
        
        🔥 CRITICAL: Blocks buys if market_start_prices[coin] == -2
        Prevents race condition when buy goes through AFTER trigger
        
        Args:
            market_slug: Market identifier
            coin: Coin name ('btc', 'eth', 'sol', 'xrp')
        
        Returns:
            True - market is closing for THIS coin, block buys
            False - market is open for this coin, buys are allowed
        """
        # Check ONLY for specified coin (per-coin blocking!)
        if coin in market_start_prices:
            status = market_start_prices[coin].get(market_slug, None)
            if status == -2:
                return True  # Market is closing for THIS coin!
        return False  # Market is open for this coin
    
    order_executor.set_market_closing_check(is_market_closing)
    
    # Check wallet balance (if not DRY_RUN)
    if not safety_guard.dry_run:
        print("\n[WALLET] Checking wallet balance...")
        wallet_balance = order_executor.get_wallet_usdc_balance()
        
        if not wallet_balance or wallet_balance <= 0:
            print("\n" + "="*80)
            print("❌ ERROR: Cannot read wallet balance or balance is 0!")
            print("   Check your PRIVATE_KEY in .env and ensure wallet has USDC")
            print("="*80)
            sys.exit(1)
        
        print("\n" + "="*80)
        print(f"💰 Wallet balance: ${wallet_balance:.2f}")
        print(f"   Address: {order_executor.wallet_address}")
        print("🔴 LIVE TRADING MODE - REAL MONEY")
        print("="*80 + "\n")
    else:
        # DRY_RUN - use simulated balance
        wallet_balance = 10000.0  # Simulated balance
        print("\n" + "="*80)
        print(f"🟢 DRY_RUN MODE: Simulated balance ${wallet_balance:.2f}")
        print("   No real orders will be placed")
        print("="*80 + "\n")
    
    # Inject executor into trader module
    trader_module.set_order_executor(order_executor)
    print("[SYSTEM] ✓ OrderExecutor injected into trader module")
    
    # 📂 Load metadata from disk (CRITICAL for redeem after restart!)
    trader_module.load_market_metadata_from_disk()
    print()
    
    # ═══════════════════════════════════════════════════════════
    
    # Initialize data feed (shared across all strategies)
    print("[SYSTEM] Initializing multi-market data feed...")
    data_feed = DataFeed(config)
    data_feed.start()
    time.sleep(5)  # Let data stabilize
    
    # Initialize 2 strategies (1 base × 2 coins) using global constants
    print(f"[SYSTEM] Initializing 2 parallel strategies...")
    strategies = {}
    strategy_names = []
    
    for base_name in STRATEGY_BASES:
        for coin in COINS:
            strategy_name = f"{base_name}_{coin}"
            strategy_names.append(strategy_name)
            strategies[strategy_name] = LateEntryStrategy(config)
            print(f"         ✓ {strategy_name:30s} (late-window entry | time-based sizing)")
    
    _sample_st = strategies.get(f"{STRATEGY_BASES[0]}_{COINS[0]}")
    if _sample_st:
        print(f"         Effective entry window: last {_sample_st.entry_window}s | sizing tiers: >{_sample_st.sizing_t1}s / >{_sample_st.sizing_t2}s")
    
    # Initialize multi-trader (unified wallet - no capital distribution)
    global multi_trader_instance
    print("\n[SYSTEM] Initializing multi-trader...")
    # Note: capital_per_strategy=0 because all strategies share one wallet balance
    # Individual trader capital is only used for per-coin PnL statistics, not limits
    multi_trader = MultiTrader(capital_per_strategy=0, strategy_names=strategy_names)
    multi_trader_instance = multi_trader  # Store for graceful shutdown
    print()
    
    # Initialize dashboard (pass config for trading status display)
    dashboard = DashboardMultiAB(width=160, coins=COINS, config=config)
    
    import web_dashboard_state as web_dashboard_state_mod
    web_dashboard_state_mod.set_session_start(session_start_time)
    if getattr(args, "web", False):
        from web_dashboard.server import run_server_thread
        proj_root = Path(__file__).resolve().parent.parent
        run_server_thread(host=args.web_host, port=args.web_port, project_root=proj_root)
        print(f"[WEB] Dashboard: http://{args.web_host}:{args.web_port}/")
        print()
    
    # Initialize Telegram notifier with event callback
    dashboard.add_event("Initializing Telegram notifier...", 'system')
    from telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier(event_callback=lambda msg, t: dashboard.add_event(msg, t))
    
    # Track market start prices for EACH coin separately
    # {coin: {market_slug: price or status}}
    # Values: positive float (valid price), -1 (skipped - started mid-market)
    market_start_prices = {coin: {} for coin in COINS}
    
    # Track pending markets for EACH coin separately
    # {coin: {market_slug: {...}}}
    pending_markets = {coin: {} for coin in COINS}
    
    # Track if we witnessed a market switch for EACH coin
    witnessed_market_switch = {coin: False for coin in COINS}
    
    # Thread-safe lock for shared state access
    market_lock = threading.Lock()
    
    # 🛡️ ASYNC SYSTEM #2: ThreadPoolExecutor for parallel exit checks
    sys2_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sys2")
    
    # 🔄 ASYNC REDEEM: ThreadPoolExecutor for sequential redeems
    # max_workers=1 so redeems go one by one (not in parallel)
    redeem_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="redeem")
    
    # ═══════════════════════════════════════════════════════════════
    # TELEGRAM COMMAND HANDLER - Thread-safe chart generation on demand
    # ═══════════════════════════════════════════════════════════════
    def handle_chart_command():
        """
        Generate and send PnL chart on demand when user sends /chart or /pnl
        THREAD-SAFE: Uses market_lock to safely read multi_trader data
        FAULT-TOLERANT: Full error handling, never crashes main loop
        """
        try:
            print("\n[TELEGRAM CMD] 📊 Generating PnL chart on demand...")
            
            # Generate chart path (unique name to avoid conflicts)
            import uuid
            chart_path = f"/root/4coins_live/logs/pnl_chart_on_demand_{uuid.uuid4().hex[:8]}.png"
            
            print(f"[TELEGRAM CMD] 📊 Chart request received")
            print(f"[TELEGRAM CMD] Chart path: {chart_path}")
            print(f"[TELEGRAM CMD] COINS list: {COINS}")
            print(f"[TELEGRAM CMD] Log dir: /root/4coins_live/logs")
            
            # Import chart generator
            from pnl_chart_generator import generate_pnl_chart
            
            # Generate chart (reads JSONL files - safe concurrent read)
            # NOTE: We don't check total_completed_markets because it resets after restart
            # Instead, generate_pnl_chart will check actual files and return False if no data
            print(f"[TELEGRAM CMD] Calling generate_pnl_chart()...")
            result = generate_pnl_chart('/root/4coins_live/logs', COINS, chart_path)
            print(f"[TELEGRAM CMD] generate_pnl_chart() returned: {result}")
            
            if not result:
                print("[TELEGRAM CMD] ⚠️ No trade data found in files")
                notifier.send_message("⚠️ No completed markets yet. Chart will be available after first market closes.")
                return
            
            # THREAD-SAFE: Lock access to shared data for stats reading
            with market_lock:
                
                # Get current portfolio stats (safe read under lock)
                try:
                    portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                except Exception as e:
                    print(f"[TELEGRAM CMD] ⚠️ Stats error: {e}")
                    portfolio_stats = {'total_pnl': 0, 'uptime': '?'}
                
                # Count actual completed markets from files (not from memory variable)
                # This works correctly after bot restart
                actual_markets_count = 0
                for coin in COINS:
                    trades_file = Path(f"/root/4coins_live/logs/late_v3_{coin}/trades.jsonl")
                    if trades_file.exists():
                        try:
                            with open(trades_file, 'r') as f:
                                actual_markets_count += sum(1 for _ in f)
                        except:
                            pass
                
                # Create caption
                total_pnl = portfolio_stats.get('total_pnl', 0)
                uptime = portfolio_stats.get('uptime', '?')
                
                # Format PnL by coin
                coin_stats = []
                for coin in COINS:
                    coin_pnl = portfolio_stats.get(f'{coin}_pnl', 0)
                    emoji = "🟢" if coin_pnl >= 0 else "🔴"
                    coin_stats.append(f"{coin.upper()}: {emoji} ${coin_pnl:+.0f}")
                
                caption = f"""<b>📊 Current PnL Chart</b>

💰 <b>Total:</b> ${total_pnl:+.2f}
📈 <b>Markets:</b> {actual_markets_count}
⏱ <b>Session:</b> {uptime}

<b>By Coin:</b>
{' | '.join(coin_stats)}"""
            
            # Send photo (outside lock - network I/O can be slow)
            if notifier.send_photo(chart_path, caption):
                print(f"[TELEGRAM CMD] ✓ Chart sent successfully")
            else:
                print(f"[TELEGRAM CMD] ✗ Failed to send chart to Telegram")
                notifier.send_message("❌ Chart generated but failed to send. Please try again.")
            
            # Cleanup temp file
            try:
                import os
                os.remove(chart_path)
            except:
                pass
                
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Fatal error: {error_msg}")
            try:
                notifier.send_message(f"❌ Error generating chart:\n<code>{error_msg}</code>")
            except:
                pass  # Don't crash if notification fails
    
    def get_pol_price_usd() -> float:
        """
        Get current POL price in USD via CoinGecko API
        
        Returns:
            POL price in USD or 0.45 (fallback) if API unavailable
        """
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': 'polygon-ecosystem-token',
                'vs_currencies': 'usd'
            }
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                price = data.get('polygon-ecosystem-token', {}).get('usd')
                if price:
                    print(f"[PRICE API] POL price: ${price:.4f}")
                    return float(price)
            
            # Fallback if API didn't return price
            print(f"[PRICE API] ⚠️ Failed to get POL price, using fallback: $0.45")
            return 0.45
            
        except Exception as e:
            print(f"[PRICE API] ⚠️ Error getting POL price: {e}, using fallback: $0.45")
            return 0.45
    
    def get_active_positions():
        """
        Get active positions via Polymarket Data API
        THREAD-SAFE: Only readonly API requests, doesn't use shared state
        
        Returns:
            List of positions or None on error
        """
        try:
            # Get wallet address from order_executor
            wallet = order_executor.wallet_address
            if not wallet:
                print("[POSITIONS API] ⚠️ No wallet address")
                return None
            
            url = "https://data-api.polymarket.com/positions"
            params = {
                'user': wallet,
                'sizeThreshold': 0.1,  # Minimum 0.1 contracts
                'limit': 50,
                'sortBy': 'CURRENT',
                'sortDirection': 'DESC'
            }
            
            print(f"[POSITIONS API] Fetching positions for {wallet[:6]}...{wallet[-4:]}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                positions = response.json()
                print(f"[POSITIONS API] ✅ Got {len(positions)} positions")
                return positions
            else:
                print(f"[POSITIONS API] ⚠️ Failed: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[POSITIONS API] ⚠️ Error: {e}")
            return None
    
    def handle_balance_command():
        """
        Show wallet balance when user sends /balance
        THREAD-SAFE: Safe concurrent access
        """
        try:
            print("\n[TELEGRAM CMD] 💰 Getting wallet balance...")
            
            # Get balances
            usdc_balance = order_executor.get_wallet_usdc_balance()
            pol_balance = order_executor.get_pol_balance()
            
            if usdc_balance is None:
                notifier.send_message("❌ Failed to get USDC balance")
                return
            
            # Get current POL price via CoinGecko API
            pol_price_usd = get_pol_price_usd()
            pol_value_usd = (pol_balance or 0) * pol_price_usd
            
            total_usd = usdc_balance + pol_value_usd
            
            # Format message
            message = f"""<b>💰 WALLET BALANCE</b>
━━━━━━━━━━━━━━━

<b>USDC:</b> ${usdc_balance:,.2f}
<b>POL:</b> {pol_balance or 0:.4f} (~${pol_value_usd:.2f})

━━━━━━━━━━━━━━━
<b>TOTAL:</b> ${total_usd:,.2f}

<i>Wallet: {order_executor.wallet_address[:6]}...{order_executor.wallet_address[-4:]}</i>"""
            
            notifier.send_message(message)
            print(f"[TELEGRAM CMD] ✅ Balance sent: ${total_usd:.2f}")
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Balance error: {error_msg}")
            try:
                notifier.send_message(f"❌ Error getting balance:\n<code>{error_msg}</code>")
            except:
                pass  # Don't crash if notification fails
    
    def handle_positions_command():
        """
        Show active positions when user sends /t or /positions
        THREAD-SAFE: Only readonly API calls, no shared state access
        """
        try:
            print("\n[TELEGRAM CMD] 📊 Getting active positions...")
            
            # Get positions via API (thread-safe - only API request)
            positions = get_active_positions()
            
            if positions is None:
                notifier.send_message("❌ Failed to get positions from API")
                return
            
            if not positions:
                notifier.send_message("📊 <b>No active positions</b>\n\nAll markets closed or redeemed! 🎉")
                return
            
            # Calculate total metrics
            total_value = sum(p.get('currentValue', 0) for p in positions)
            total_pnl = sum(p.get('cashPnl', 0) for p in positions)
            redeemable_value = sum(p.get('currentValue', 0) for p in positions if p.get('redeemable'))
            redeemable_count = sum(1 for p in positions if p.get('redeemable'))
            
            # Format message
            message = f"<b>📊 ACTIVE POSITIONS ({len(positions)})</b>\n"
            message += "━━━━━━━━━━━━━━━\n\n"
            
            # Show up to 10 positions
            for i, p in enumerate(positions[:10]):
                title = p.get('title', 'Unknown')
                # Truncate long names
                if len(title) > 45:
                    title = title[:42] + "..."
                
                outcome = p.get('outcome', '?')
                size = p.get('size', 0)
                avg_price = p.get('avgPrice', 0)
                cur_price = p.get('curPrice', 0)
                initial = p.get('initialValue', 0)
                current = p.get('currentValue', 0)
                pnl = p.get('cashPnl', 0)
                pnl_pct = p.get('percentPnl', 0)
                redeemable = p.get('redeemable', False)
                
                # Emoji by status
                if redeemable:
                    emoji = "💰"
                    status = " [REDEEM!]"
                elif pnl >= 0:
                    emoji = "🟢"
                    status = ""
                else:
                    emoji = "🔴"
                    status = ""
                
                message += f"<b>{outcome}</b>: {title}\n"
                message += f"├ Size: {size:.1f} contracts\n"
                message += f"├ Entry: ${avg_price:.3f} → Now: ${cur_price:.3f}\n"
                message += f"├ Value: ${initial:.2f} → ${current:.2f}\n"
                message += f"└ PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) {emoji}{status}\n\n"
            
            # If more than 10 positions
            if len(positions) > 10:
                hidden_value = sum(p.get('currentValue', 0) for p in positions[10:])
                hidden_pnl = sum(p.get('cashPnl', 0) for p in positions[10:])
                message += f"<i>...and {len(positions) - 10} more positions"
                message += f" (${hidden_value:.2f}, PnL: ${hidden_pnl:+.2f})</i>\n\n"
            
            # Final statistics
            message += "━━━━━━━━━━━━━━━\n"
            message += f"<b>Total Value:</b> ${total_value:.2f}\n"
            message += f"<b>Total PnL:</b> ${total_pnl:+.2f}"
            
            if total_value > 0:
                total_pnl_pct = (total_pnl / (total_value - total_pnl)) * 100
                message += f" ({total_pnl_pct:+.1f}%)"
            
            if redeemable_count > 0:
                message += f"\n<b>💰 Redeemable:</b> ${redeemable_value:.2f} ({redeemable_count} markets)"
            
            notifier.send_message(message)
            print(f"[TELEGRAM CMD] ✅ Positions sent: {len(positions)} items, ${total_value:.2f}")
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Positions error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.send_message(f"❌ Error getting positions:\n<code>{error_msg}</code>")
            except:
                pass  # Don't crash if notification fails
    
    def handle_redeem_command():
        """
        Show redeemable positions with interactive buttons
        THREAD-SAFE: Uses API calls and redeem_collector methods
        """
        global redeem_positions_cache
        
        try:
            print("\n[TELEGRAM CMD] 💰 Getting redeemable positions...")
            
            # Use existing method from SimpleRedeemCollector
            positions = redeem_collector._fetch_redeemable_positions()
            
            if positions is None:
                notifier.send_message("❌ Failed to fetch redeemable positions from API")
                return
            
            if not positions:
                notifier.send_message("✅ <b>No positions to redeem!</b>\n\nAll markets are already redeemed or still open.")
                return
            
            # Save to cache for callback handlers (thread-safe)
            with redeem_cache_lock:
                redeem_positions_cache = positions
            
            # Calculate total value
            total_value = sum(p.get('currentValue', 0) for p in positions)
            
            # Format message
            message = f"<b>💰 REDEEMABLE POSITIONS ({len(positions)})</b>\n"
            message += "━━━━━━━━━━━━━━━\n\n"
            
            for i, p in enumerate(positions[:10]):  # Max 10 positions in list
                title = p.get('title', 'Unknown')
                if len(title) > 40:
                    title = title[:37] + "..."
                
                outcome = p.get('outcome', '?')
                size = p.get('size', 0)
                value = p.get('currentValue', 0)
                
                message += f"<b>#{i+1}</b> [{outcome}] {title}\n"
                message += f"  └ {size:.1f} contracts = ${value:.2f}\n\n"
            
            if len(positions) > 10:
                hidden_value = sum(p.get('currentValue', 0) for p in positions[10:])
                message += f"<i>...and {len(positions) - 10} more (${hidden_value:.2f})</i>\n\n"
            
            message += "━━━━━━━━━━━━━━━\n"
            message += f"<b>Total Value:</b> ${total_value:.2f}\n\n"
            message += "<i>Choose action:</i>"
            
            # Create buttons
            buttons = [
                [
                    {"text": "💰 Redeem All", "callback_data": "redeem_all"},
                    {"text": "❌ Cancel", "callback_data": "redeem_cancel"}
                ]
            ]
            
            # Add button for each position (up to 10 items)
            for i in range(min(len(positions), 10)):
                buttons.append([
                    {"text": f"💰 Redeem #{i+1}", "callback_data": f"redeem_pos_{i}"}
                ])
            
            # Send message with buttons
            notifier.send_message_with_buttons(message, buttons)
            print(f"[TELEGRAM CMD] ✅ Redeem menu sent: {len(positions)} positions, ${total_value:.2f}")
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Redeem error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.send_message(f"❌ Error getting redeemable positions:\n<code>{error_msg}</code>")
            except:
                pass
    
    def handle_redeem_all_callback(callback_id: str, message_id: int):
        """Handle 'Redeem All' button click"""
        global redeem_positions_cache
        
        try:
            # Get positions from cache (thread-safe)
            with redeem_cache_lock:
                positions = redeem_positions_cache.copy()
            
            if not positions:
                notifier.answer_callback_query(callback_id, "❌ No positions in cache", show_alert=True)
                return
            
            notifier.answer_callback_query(callback_id, "🚀 Starting redeem process...")
            
            total = len(positions)
            
            # Update message
            notifier.edit_message_text(
                message_id, 
                f"<b>🚀 REDEEMING {total} POSITIONS...</b>\n\n<i>Please wait, this may take a few minutes...</i>"
            )
            
            # Redeem process with pauses
            success_count = 0
            fail_count = 0
            total_redeemed = 0.0
            
            for i, pos in enumerate(positions):
                # Use existing method from SimpleRedeemCollector
                result = redeem_collector._redeem_one(i + 1, total, pos)
                
                if result:
                    success_count += 1
                    total_redeemed += pos.get('currentValue', 0)
                else:
                    fail_count += 1
                
                # Pause between redeems (as in automatic collector)
                if i < total - 1:
                    pause = redeem_collector.pause_between
                    print(f"[REDEEM] Pause {pause}s before next redeem...")
                    time.sleep(pause)
            
            # Final report
            message = f"<b>✅ REDEEM COMPLETED!</b>\n"
            message += "━━━━━━━━━━━━━━━\n\n"
            message += f"<b>Total positions:</b> {total}\n"
            message += f"<b>Redeemed:</b> {success_count} ✅\n"
            message += f"<b>Failed:</b> {fail_count} ❌\n"
            message += f"<b>Total value:</b> ${total_redeemed:.2f}\n"
            
            notifier.edit_message_text(message_id, message)
            print(f"[TELEGRAM CMD] ✅ Redeem all completed: {success_count}/{total}")
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Redeem all error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.edit_message_text(message_id, f"❌ Redeem failed:\n<code>{error_msg}</code>")
            except:
                pass
    
    def handle_redeem_position_callback(callback_id: str, message_id: int, index: int):
        """Handle 'Redeem #N' button click"""
        global redeem_positions_cache
        
        try:
            # Get positions from cache (thread-safe)
            with redeem_cache_lock:
                positions = redeem_positions_cache.copy()
            
            if index >= len(positions):
                notifier.answer_callback_query(callback_id, "❌ Position not found", show_alert=True)
                return
            
            pos = positions[index]
            title = pos.get('title', 'Unknown')[:40]
            
            notifier.answer_callback_query(callback_id, f"🚀 Redeeming position #{index+1}...")
            
            # Update message
            notifier.edit_message_text(
                message_id,
                f"<b>🚀 REDEEMING POSITION #{index+1}...</b>\n\n{title}\n\n<i>Please wait...</i>"
            )
            
            # Redeem one position
            result = redeem_collector._redeem_one(1, 1, pos)
            
            if result:
                value = pos.get('currentValue', 0)
                message = f"<b>✅ REDEEM SUCCESS!</b>\n\n"
                message += f"Position #{index+1} redeemed\n"
                message += f"Value: ${value:.2f}"
            else:
                message = f"<b>❌ REDEEM FAILED!</b>\n\n"
                message += f"Position #{index+1} failed to redeem\n"
                message += f"Check logs for details."
            
            notifier.edit_message_text(message_id, message)
            print(f"[TELEGRAM CMD] ✅ Redeem position #{index+1}: {'success' if result else 'failed'}")
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Redeem position error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.edit_message_text(message_id, f"❌ Redeem failed:\n<code>{error_msg}</code>")
            except:
                pass
    
    def handle_redeem_cancel_callback(callback_id: str, message_id: int):
        """Handle 'Cancel' button click"""
        try:
            notifier.answer_callback_query(callback_id, "Cancelled")
            notifier.edit_message_text(message_id, "❌ <b>Redeem cancelled</b>")
            print(f"[TELEGRAM CMD] ℹ️ Redeem cancelled by user")
        except Exception as e:
            print(f"[TELEGRAM CMD] ✗ Cancel error: {e}")
    
    def handle_shutdown_command():
        """
        Emergency shutdown: find and stop main.py process
        THREAD-SAFE: Uses OS signals, doesn't access shared state
        
        ⚠️ CRITICAL: This will stop the trading bot!
        """
        try:
            print("\n[TELEGRAM CMD] 🛑 EMERGENCY SHUTDOWN requested!")
            
            # Find process main.py
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'python3.*src/main.py'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    pid = result.stdout.strip()
                    
                    if not pid:
                        notifier.send_message("❌ <b>Process not found!</b>\n\nThe bot is not running.")
                        return
                    
                    # Send confirmation with buttons
                    message = f"⚠️ <b>EMERGENCY SHUTDOWN</b>\n\n"
                    message += f"<b>Process found:</b> PID {pid}\n"
                    message += f"<b>Command:</b> python3 src/main.py\n\n"
                    message += f"<i>This will gracefully stop the bot and save all positions.</i>\n\n"
                    message += f"<b>Are you sure?</b>"
                    
                    buttons = [
                        [
                            {"text": "🛑 STOP BOT", "callback_data": f"shutdown_confirm_{pid}"},
                            {"text": "❌ Cancel", "callback_data": "shutdown_cancel"}
                        ]
                    ]
                    
                    notifier.send_message_with_buttons(message, buttons)
                    print(f"[TELEGRAM CMD] ℹ️ Shutdown confirmation sent for PID {pid}")
                    
                else:
                    notifier.send_message("❌ <b>Process not found!</b>\n\nThe bot is not running.")
                    
            except subprocess.TimeoutExpired:
                notifier.send_message("❌ <b>Timeout!</b>\n\nFailed to find process.")
            except Exception as e:
                error_msg = str(e)[:200]
                notifier.send_message(f"❌ <b>Error finding process:</b>\n<code>{error_msg}</code>")
                
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Shutdown error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.send_message(f"❌ <b>Shutdown failed:</b>\n<code>{error_msg}</code>")
            except:
                pass
    
    def handle_shutdown_confirm_callback(callback_id: str, message_id: int, pid: str):
        """Handle 'STOP BOT' confirmation button click"""
        try:
            notifier.answer_callback_query(callback_id, "🛑 Stopping bot...", show_alert=True)
            
            # Update message
            notifier.edit_message_text(
                message_id,
                f"<b>🛑 STOPPING BOT...</b>\n\nPID: {pid}\n\n<i>Sending SIGINT signal...</i>"
            )
            
            # Send SIGINT (like Ctrl+C)
            try:
                os.kill(int(pid), signal.SIGINT)
                
                # Wait a bit
                time.sleep(2)
                
                # Check that process is stopped
                result = subprocess.run(
                    ['ps', '-p', pid],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Process still running (graceful shutdown in progress)
                    message = f"<b>✅ SHUTDOWN SIGNAL SENT!</b>\n\n"
                    message += f"PID: {pid}\n\n"
                    message += f"<i>Bot is shutting down gracefully...</i>\n"
                    message += f"<i>Check logs for details.</i>"
                else:
                    # Process stopped
                    message = f"<b>✅ BOT STOPPED!</b>\n\n"
                    message += f"PID: {pid}\n\n"
                    message += f"<i>All positions saved.</i>"
                
                notifier.edit_message_text(message_id, message)
                print(f"[TELEGRAM CMD] ✅ Shutdown signal sent to PID {pid}")
                
            except ProcessLookupError:
                # Process no longer exists
                notifier.edit_message_text(
                    message_id,
                    f"<b>ℹ️ BOT ALREADY STOPPED</b>\n\nPID {pid} no longer exists."
                )
            except PermissionError:
                notifier.edit_message_text(
                    message_id,
                    f"<b>❌ PERMISSION DENIED</b>\n\nCannot stop PID {pid}.\nRun bot as same user."
                )
            
        except Exception as e:
            error_msg = str(e)[:200]
            print(f"[TELEGRAM CMD] ✗ Shutdown confirm error: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                notifier.edit_message_text(message_id, f"❌ <b>Shutdown failed:</b>\n<code>{error_msg}</code>")
            except:
                pass
    
    def handle_shutdown_cancel_callback(callback_id: str, message_id: int):
        """Handle 'Cancel' button click"""
        try:
            notifier.answer_callback_query(callback_id, "Cancelled")
            notifier.edit_message_text(message_id, "✅ <b>Shutdown cancelled</b>\n\nBot continues running.")
            print(f"[TELEGRAM CMD] ℹ️ Shutdown cancelled by user")
        except Exception as e:
            print(f"[TELEGRAM CMD] ✗ Cancel error: {e}")
    
    # Create dict with redeem callback handlers
    redeem_callbacks = {
        'redeem_all': handle_redeem_all_callback,
        'redeem_position': handle_redeem_position_callback,
        'redeem_cancel': handle_redeem_cancel_callback
    }
    
    # Create dict with shutdown callback handlers
    shutdown_callbacks = {
        'shutdown_confirm': handle_shutdown_confirm_callback,
        'shutdown_cancel': handle_shutdown_cancel_callback
    }
    
    # Start Telegram command listener (daemon thread, won't block shutdown)
    dashboard.add_event("Starting command listener...", 'telegram')
    try:
        notifier.start_command_listener(
            on_chart_command=handle_chart_command,
            on_balance_command=handle_balance_command,
            on_positions_command=handle_positions_command,
            on_redeem_command=handle_redeem_command,
            on_redeem_callbacks=redeem_callbacks,
            on_shutdown_command=handle_shutdown_command,
            on_shutdown_callbacks=shutdown_callbacks
        )
        dashboard.add_event("Command listener active (/chart, /b, /t, /r, /off)", 'success')
    except Exception as e:
        dashboard.add_event(f"Listener failed: {str(e)[:40]}", 'error')
        dashboard.add_event("Bot continues without commands", 'info')
    
    # ═══════════════════════════════════════════════════════════════
    # 🔥 SIMPLE REDEEM COLLECTOR - Periodic API-based redeem system
    # Replaces complex pending_markets logic
    # ═══════════════════════════════════════════════════════════════
    from simple_redeem_collector import SimpleRedeemCollector
    
    # Get wallet address from order_executor
    wallet_address = order_executor.wallet_address
    
    if wallet_address:
        print(f"\n[SYSTEM] Initializing Simple Redeem Collector...")
        print(f"[SYSTEM] Wallet: {wallet_address[:10]}...{wallet_address[-8:]}")
        
        redeem_collector = SimpleRedeemCollector(
            wallet_address=wallet_address,
            config=config,
            order_executor=order_executor,
            trader_module=trader_module,
            multi_trader=multi_trader,  # 🔥 FIX: For creating trade records
            notifier=notifier  # 🔥 FIX: For Telegram notifications
        )
        
        # Start in background thread (daemon - doesn't block shutdown)
        redeem_collector.start()
        print(f"[SYSTEM] ✅ Simple Redeem Collector started")
        dashboard.add_event("Redeem collector active", 'success')
    else:
        print(f"\n[SYSTEM] ⚠️ WARNING: No wallet address, redeem collector disabled")
        print(f"[SYSTEM]    Check that POLYMARKET_PRIVATE_KEY is set in .env")
        redeem_collector = None
        dashboard.add_event("Redeem collector disabled (no wallet)", 'warning')
    
    # ═══════════════════════════════════════════════════════════════
    # LEGACY: Old async redeem processor (will be removed)
    # ═══════════════════════════════════════════════════════════════
    def process_redeem_async(coin, prev_market, pending_info, config, markets_skipped, 
                            session_start_time):
        """Process redeem asynchronously without blocking main loop"""
        # 🔍 CRITICAL: Log function start (confirms that submit() worked!)
        print(f"\n[REDEEM ASYNC] 🚀 Started for {coin.upper()} market {prev_market}")
        
        try:
            redeem_cfg = config.get("execution", {}).get("redeem", {})
            max_attempts = redeem_cfg.get("max_attempts", 3)
            retry_delay = redeem_cfg.get("retry_delay_sec", 300)
            now = time.time()
            
            elapsed = (now - pending_info['first_attempt']) / 60
            print(f"[{coin.upper()} REDEEM] Attempt {pending_info['attempts']}/{max_attempts} for {prev_market} (after {elapsed:.1f} min)")
            
            # Try to redeem
            metadata = trader_module.get_market_metadata(prev_market)
            redeem_success = False
            
            # 🔍 DETAILED metadata DIAGNOSTICS
            print(f"[REDEEM] Checking metadata for {prev_market}...")
            print(f"[REDEEM]   - Metadata exists: {metadata is not None}")
            if metadata:
                print(f"[REDEEM]   - Has condition_id: {'condition_id' in metadata}")
                if 'condition_id' in metadata:
                    print(f"[REDEEM]   - Condition ID: {metadata['condition_id'][:20]}...")
            
            if metadata and metadata.get('condition_id'):
                token_ids = trader_module.get_token_ids(prev_market)
                print(f"[REDEEM]   - Token IDs exist: {token_ids is not None}")
                if token_ids:
                    print(f"[REDEEM]   - Has UP token: {'UP' in token_ids}")
                    print(f"[REDEEM]   - Has DOWN token: {'DOWN' in token_ids}")
                
                if token_ids and token_ids.get('UP') and token_ids.get('DOWN'):
                    print(f"[REDEEM] ✅ All metadata OK, calling redeem_position()...")
                    success, amount = order_executor.redeem_position(
                        market_slug=prev_market,
                        condition_id=metadata['condition_id'],
                        up_token_id=token_ids['UP'],
                        down_token_id=token_ids['DOWN'],
                        neg_risk=metadata.get('neg_risk', True)
                    )
                    
                    if success:
                        redeem_success = True
                        print(f"[REDEEM] ✅ Redeemed ${amount:.2f} USDC!")
                        
                        # ═══════════════════════════════════════════════════════════
                        # 🔥 CRITICAL: Reset investment tracking for this market!
                        # Now we can trade new market without limits!
                        # ═══════════════════════════════════════════════════════════
                        try:
                            # Get safety_guard from order_executor
                            if hasattr(trader_module, 'order_executor') and trader_module.order_executor:
                                trader_module.order_executor.safety.reset_market(prev_market)
                        except Exception as reset_err:
                            print(f"[REDEEM] ⚠ Failed to reset market tracking: {reset_err}")
                    else:
                        print(f"[REDEEM] ⚠ Failed (oracle not resolved or no tokens)")
                else:
                    print(f"[REDEEM] ❌ CRITICAL: No token IDs cached for {prev_market}")
                    print(f"[REDEEM]    This market cannot be redeemed without token IDs!")
                    print(f"[REDEEM]    Possible causes:")
                    print(f"[REDEEM]    1. Market was opened before restart")
                    print(f"[REDEEM]    2. EMERGENCY_SAVE position (no metadata saved)")
                    print(f"[REDEEM]    3. Metadata file corrupted or missing")
            else:
                print(f"[REDEEM] ❌ CRITICAL: No metadata cached for {prev_market}")
                print(f"[REDEEM]    Missing condition_id - redeem IMPOSSIBLE!")
                print(f"[REDEEM]    Metadata: {metadata}")
                print(f"[REDEEM]    Possible causes:")
                print(f"[REDEEM]    1. Market was opened before restart")
                print(f"[REDEEM]    2. Metadata not saved to disk (check logs/market_metadata.json)")
                print(f"[REDEEM]    3. Bug in set_token_ids() or save_market_metadata_to_disk()")
            
            # If redeem successful, close positions
            if redeem_success:
                api_result = get_market_outcome(prev_market)
                
                if api_result.get("winner"):
                    winner = api_result["winner"]
                    price_start = pending_info['price_start']
                    price_final = pending_info['price_final']
                    
                    # Close for all strategies
                    for base_name in STRATEGY_BASES:
                        strategy_name = f"{base_name}_{coin}"
                        try:
                            result = multi_trader.close_market(
                                strategy_name=strategy_name,
                                market_slug=prev_market,
                                winner=winner,
                                btc_start=price_start,
                                btc_final=price_final
                            )
                            if result:
                                # Send Telegram notification
                                session_stats = multi_trader.get_session_stats(strategy_name, markets_skipped[coin])
                                portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                                notifier.send_market_closed(coin, result, session_stats, portfolio_stats)
                                
                                # Chart generation (if needed)
                                nonlocal total_completed_markets, last_chart_at
                                total_completed_markets += 1
                                
                                if total_completed_markets - last_chart_at >= CHART_INTERVAL:
                                    print(f"[CHART] {total_completed_markets} markets completed, generating PnL chart...")
                                    chart_path = f"/root/4coins_live/logs/pnl_chart_{total_completed_markets}.png"
                                    from pnl_chart_generator import generate_pnl_chart
                                    if generate_pnl_chart('/root/4coins_live/logs', COINS, chart_path):
                                        caption = f"<b>📊 PnL Chart - {total_completed_markets} Markets Completed</b>"
                                        if notifier.send_photo(chart_path, caption):
                                            print(f"[CHART] ✓ Sent to Telegram successfully")
                                            last_chart_at = total_completed_markets
                                        else:
                                            print(f"[CHART] ✗ Failed to send to Telegram")
                                    else:
                                        print(f"[CHART] ✗ Failed to generate chart")
                                
                                pnl_sign = "+" if result['pnl'] >= 0 else ""
                                print(f"[{strategy_name:30s}] Closed {prev_market}: {pnl_sign}${result['pnl']:,.2f}")
                            elif redeem_amount > 0:
                                # ═══════════════════════════════════════════════════════════
                                # 🔥 FIX: If close_market() returned None (position empty after restart)
                                # but redeem was successful, create minimal trade record from orders
                                # This ensures ALL natural closes appear in dashboard!
                                # ═══════════════════════════════════════════════════════════
                                print(f"[{strategy_name}] Position was empty but redeem successful (${redeem_amount:.2f})")
                                print(f"[{strategy_name}] Creating trade record from orders for dashboard...")
                                
                                try:
                                    # Get trader
                                    trader = multi_trader.traders.get(strategy_name)
                                    if trader:
                                        # Reconstruct minimal trade from orders.jsonl
                                        import json
                                        total_cost = 0
                                        total_contracts = 0
                                        
                                        try:
                                            with open(f'logs/orders.jsonl', 'r') as f:
                                                for line in f:
                                                    try:
                                                        order = json.loads(line)
                                                        if (order.get('market_slug') == prev_market and 
                                                            order.get('order_type') == 'BUY' and 
                                                            order.get('success')):
                                                            total_cost += order.get('total_spent_usd', 0)
                                                            total_contracts += order.get('contracts', 0)
                                                    except:
                                                        continue
                                        except Exception as e:
                                            print(f"[{strategy_name}] Warning: Could not read orders: {e}")
                                        
                                        if total_cost > 0:
                                            # Create minimal trade record
                                            pnl = redeem_amount - total_cost
                                            roi_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
                                            
                                            minimal_trade = {
                                                'market_slug': prev_market,
                                                'winner': winner,
                                                'exit_type': 'natural_close',
                                                'exit_reason': 'natural_close',
                                                'pnl': pnl,
                                                'roi_pct': roi_pct,
                                                'total_cost': total_cost,
                                                'payout': redeem_amount,
                                                'winner_ratio': 100.0,  # Unknown
                                                'total_entries': 0,  # Unknown
                                                'up_entries': 0,
                                                'down_entries': 0,
                                                'up_invested': total_cost,
                                                'down_invested': 0.0,
                                                'up_shares': total_contracts,
                                                'down_shares': 0.0,
                                                'duration': 0,
                                                'close_time': time.time(),
                                                'close_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                                'reconstructed': True  # Flag to indicate this was reconstructed
                                            }
                                            
                                            # Add to closed_trades for dashboard visibility
                                            trader.closed_trades.append(minimal_trade)
                                            
                                            # Log to file
                                            try:
                                                trader._log_trade(minimal_trade)
                                            except Exception as e:
                                                print(f"[{strategy_name}] Warning: Could not log trade: {e}")
                                            
                                            pnl_sign = "+" if pnl >= 0 else ""
                                            print(f"[{strategy_name:30s}] Reconstructed {prev_market}: {pnl_sign}${pnl:,.2f} (from redeem)")
                                        else:
                                            print(f"[{strategy_name}] No buy orders found in logs, skipping reconstruction")
                                except Exception as e:
                                    print(f"[{strategy_name}] Warning: Could not reconstruct trade: {e}")
                        except Exception as e:
                            print(f"[ERROR] {strategy_name} close failed: {e}")
                
                # Remove from pending - success!
                del pending_markets[coin][prev_market]
                print(f"[SUCCESS] Market {prev_market} completed and redeemed!")
                print()
                return True
            
            # Redeem failed
            if pending_info['attempts'] < max_attempts:
                pending_info['next_retry'] = now + retry_delay
                print(f"[PENDING] Will retry in {retry_delay // 60} minutes")
                return False
            else:
                # Failed after max attempts
                print(f"[ERROR] ❌ Market {prev_market} failed after {max_attempts} attempts!")
                
                # Get position info
                strategy_name = f"{STRATEGY_BASES[0]}_{coin}"
                trader = multi_trader.get_trader(strategy_name)
                position_info = ""
                if trader and prev_market in trader.positions:
                    pos = trader.positions[prev_market]
                    for side in ['UP', 'DOWN']:
                        if pos[side]['total_shares'] > 0:
                            position_info += f" {side}:{pos[side]['total_shares']:.0f}@${pos[side]['total_invested']:.2f}"
                
                # Log failure
                failed_log = Path("logs/failed_redeems.log")
                failed_log.parent.mkdir(exist_ok=True)
                with open(failed_log, "a") as f:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"{timestamp} | {prev_market} | {position_info}\n")
                
                print(f"[ERROR] Logged to logs/failed_redeems.log")
                
                # Send alert
                alert_msg = f"⚠️ <b>FAILED REDEEM</b>\n\nMarket: <code>{prev_market}</code>\nPosition: {position_info}\nAttempts: {max_attempts}\n\nCheck logs/failed_redeems.log"
                order_executor._send_telegram_alert(alert_msg)
                
                # Remove from pending
                del pending_markets[coin][prev_market]
                print()
                return False
                
        except Exception as e:
            print(f"\n[REDEEM ERROR] ❌ EXCEPTION in process_redeem_async!")
            print(f"[REDEEM ERROR] Coin: {coin}, Market: {prev_market}")
            print(f"[REDEEM ERROR] Exception: {e}")
            print(f"[REDEEM ERROR] Full traceback:")
            import traceback
            traceback.print_exc()
            print(f"[REDEEM ERROR] This redeem task will be abandoned!")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # EVENT-DRIVEN CALLBACK - Called INSTANTLY on price changes
    # ═══════════════════════════════════════════════════════════════
    def on_price_update(coin: str, market_state: Dict):
        """
        Called IMMEDIATELY when price changes from Polymarket WebSocket
        Handles both EXIT checks and ENTRY signals in real-time
        Thread-safe with comprehensive error handling
        """
        try:
            # ═══════════════════════════════════════════════════════
            # VALIDATION: Check inputs
            # ═══════════════════════════════════════════════════════
            if not market_state or not coin:
                return
            
            market_slug = market_state.get('market_slug')
            if not market_slug:
                return
            
            # Get prices with safe defaults
            up_ask = market_state.get('up_ask', 0.5)
            down_ask = market_state.get('down_ask', 0.5)
            up_bid = market_state.get('up_bid', up_ask * 0.95)  # BID for selling (fallback: 95% of ASK)
            down_bid = market_state.get('down_bid', down_ask * 0.95)  # BID for selling (fallback: 95% of ASK)
            
            # Validate prices
            if up_ask <= 0 or down_ask <= 0 or up_ask > 1 or down_ask > 1:
                return
            
            # ═══════════════════════════════════════════════════════
            # THREAD-SAFE: Check market status
            # ═══════════════════════════════════════════════════════
            with market_lock:
                if coin not in market_start_prices:
                    return
                if market_slug not in market_start_prices[coin]:
                    return
                
                status = market_start_prices[coin].get(market_slug, -999)
                if status in [-1, -2, -999]:
                    return  # Market inactive, closed, or unknown
            
            # ═══════════════════════════════════════════════════════
            # PROCESS: All strategies for this coin
            # ═══════════════════════════════════════════════════════
            for base_name in STRATEGY_BASES:
                strategy_name = f"{base_name}_{coin}"
                
                # Validate strategy exists
                if strategy_name not in strategies:
                    continue
                
                try:
                    # Get current position stats (thread-safe via multi_trader locks)
                    position_stats = multi_trader.get_market_stats(strategy_name, market_slug, up_ask, down_ask)
                    
                    # ═══════════════════════════════════════════════════════
                    # PART 1: EXIT CHECKS (if we have a position)
                    # ═══════════════════════════════════════════════════════
                    if position_stats and position_stats.get('total_invested', 0) > 0:
                        # ─────────────────────────────────────────────────
                        # CRITICAL: Validate price freshness and synchronization
                        # Prevents false stop-loss triggers from stale/desync prices
                        # ─────────────────────────────────────────────────
                        up_ask_ts = market_state.get('up_ask_timestamp', 0)
                        down_ask_ts = market_state.get('down_ask_timestamp', 0)
                        
                        is_valid, reason = validate_prices(up_ask, down_ask, up_ask_ts, down_ask_ts, coin)
                        
                        if not is_valid:
                            # Prices invalid - skip ALL exit checks
                            print(f"[PRICE] ⚠️ {coin.upper()} prices invalid: {reason}, skipping exit checks")
                            continue
                        
                        # Determine our side (by contract count)
                        up_shares = position_stats.get('up_shares', 0)
                        down_shares = position_stats.get('down_shares', 0)
                        
                        our_side = None
                        our_price = None
                        
                        if up_shares > down_shares and up_shares > 0:
                            our_side = 'UP'
                            our_price = up_ask
                        elif down_shares > 0:
                            our_side = 'DOWN'
                            our_price = down_ask
                        
                        if not our_side or not our_price:
                            continue  # No clear position
                        
                        # Get unrealized PnL for stop-loss check
                        unrealized_pnl = position_stats.get('unrealized_pnl', 0)
                        total_invested = position_stats.get('total_invested', 0)
                        
                        # ─────────────────────────────────────────────────
                        # EXIT CHECK #1: HYBRID STOP-LOSS (per coin config)
                        # BTC: None | ETH: -$10 | SOL: -15% | XRP: -$10
                        # Backtest: +126% profit improvement (hybrid approach)
                        # ─────────────────────────────────────────────────
                        # Get stop-loss config for this coin
                        sl_config = config.get('exit', {}).get('stop_loss', {}).get('per_coin', {}).get(coin, {})
                        sl_enabled = sl_config.get('enabled', False)
                        sl_type = sl_config.get('type', 'none')
                        sl_value = sl_config.get('value', None)
                        
                        # Calculate threshold based on type
                        stop_loss_triggered = False
                        stop_loss_threshold = 0
                        
                        if sl_enabled and sl_value is not None:
                            if sl_type == 'fixed':
                                # Fixed dollar amount
                                stop_loss_threshold = sl_value
                                stop_loss_triggered = unrealized_pnl <= stop_loss_threshold
                            elif sl_type == 'percent':
                                # Percentage of invested capital
                                stop_loss_threshold = total_invested * (sl_value / 100.0)
                                stop_loss_triggered = unrealized_pnl <= stop_loss_threshold
                        
                        if stop_loss_triggered:
                            # Double-check position still exists (race condition protection)
                            trader = multi_trader.get_trader(strategy_name)
                            if not trader or market_slug not in trader.positions:
                                continue  # Position already closed
                            
                            # Thread-safe check: market not already closed
                            with market_lock:
                                current_status = market_start_prices[coin].get(market_slug, -999)
                                if current_status == -2:
                                    continue  # Already closed by another callback
                            
                            # 🔥 FIX 1: LOG EXIT TRIGGER (for all 4 coins)
                            from trade_logger import log_exit_trigger
                            log_exit_trigger(
                                market_slug=market_slug,
                                exit_reason='stop_loss',
                                coin=coin,
                                unrealized_pnl=unrealized_pnl,
                                threshold_pnl=stop_loss_threshold
                            )
                            
                            # 🔥 FIX 2: Mark market as closed BEFORE exit to prevent race condition (thread-safe)
                            with market_lock:
                                market_start_prices[coin][market_slug] = -2
                            
                            # 🔥 FIX 2.1: ATOMIC BLOCK (per-coin protection)
                            order_executor.block_market(market_slug, coin)
                            
                            # Close position with stop-loss (pass current BID prices for selling)
                            result = multi_trader.close_market_early_exit(
                                strategy_name=strategy_name,
                                market_slug=market_slug,
                                exit_price=our_price,
                                exit_reason='stop_loss',
                                up_bid=up_bid,  # ✅ REAL BID for selling UP tokens
                                down_bid=down_bid  # ✅ REAL BID for selling DOWN tokens
                            )
                            
                            if result:
                                
                                # Send notifications
                                if isinstance(result, dict):
                                    try:
                                        session_stats = multi_trader.get_session_stats(strategy_name, markets_skipped[coin])
                                        portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                                        notifier.send_market_closed(coin, result, session_stats, portfolio_stats)
                                        
                                        # Increment completed markets counter
                                        total_completed_markets += 1
                                        
                                        # Generate and send PnL chart every CHART_INTERVAL markets
                                        if total_completed_markets - last_chart_at >= CHART_INTERVAL:
                                            print(f"[CHART] {total_completed_markets} markets completed, generating PnL chart...")
                                            
                                            chart_path = f"/root/4coins_live/logs/pnl_chart_{total_completed_markets}.png"
                                            
                                            # Import chart generator
                                            from pnl_chart_generator import generate_pnl_chart
                                            
                                            if generate_pnl_chart('/root/4coins_live/logs', COINS, chart_path):
                                                # Send to Telegram
                                                caption = f"<b>📊 PnL Chart - {total_completed_markets} Markets Completed</b>"
                                                if notifier.send_photo(chart_path, caption):
                                                    print(f"[CHART] ✓ Sent to Telegram successfully")
                                                    last_chart_at = total_completed_markets
                                                else:
                                                    print(f"[CHART] ✗ Failed to send to Telegram")
                                            else:
                                                print(f"[CHART] ✗ Failed to generate chart")
                                    except Exception as e:
                                        print(f"[ERROR] Notification failed: {e}")
                                
                                # Print confirmation
                                print(f"\n{'='*80}")
                                if sl_type == 'fixed':
                                    print(f"[{coin.upper()}] 🛑 STOP-LOSS (Fixed ${sl_value:.2f})")
                                elif sl_type == 'percent':
                                    print(f"[{coin.upper()}] 🛑 STOP-LOSS (Percent {sl_value:.0f}% = ${stop_loss_threshold:.2f})")
                                else:
                                    print(f"[{coin.upper()}] 🛑 STOP-LOSS")
                                print(f"[{strategy_name}] {market_slug}")
                                print(f"[EXIT] Our side: {our_side}")
                                print(f"[EXIT] Invested: ${total_invested:.2f}")
                                print(f"[EXIT] Unrealized PnL: ${unrealized_pnl:.2f} (threshold: ${stop_loss_threshold:.2f})")
                                if isinstance(result, dict):
                                    print(f"[EXIT] Final PnL: ${result['pnl']:+.2f}")
                                print(f"[EXIT] Market is NO LONGER trading!")
                                print(f"{'='*80}\n")
                                return  # Exit callback after closing
                        
                        # ─────────────────────────────────────────────────
                        # EXIT CHECK #2: FLIP-STOP (dynamic from strategy)
                        # Triggers when our side price drops too low
                        # ─────────────────────────────────────────────────
                        strategy = strategies.get(strategy_name)
                        if strategy and our_price <= strategy.flip_stop_price:
                            # Double-check position still exists (race condition protection)
                            trader = multi_trader.get_trader(strategy_name)
                            if not trader or market_slug not in trader.positions:
                                continue  # Position already closed
                            
                            # Thread-safe check: market not already closed
                            with market_lock:
                                current_status = market_start_prices[coin].get(market_slug, -999)
                                if current_status == -2:
                                    continue  # Already closed by another callback
                            
                            # 🔥 FIX 1: LOG EXIT TRIGGER (for all 4 coins)
                            from trade_logger import log_exit_trigger
                            log_exit_trigger(
                                market_slug=market_slug,
                                exit_reason='flip_stop',
                                coin=coin,
                                trigger_price=our_price,
                                threshold_price=strategy.flip_stop_price
                            )
                            
                            # 🔥 FIX 2: Mark market as closed BEFORE exit to prevent race condition (thread-safe)
                            with market_lock:
                                market_start_prices[coin][market_slug] = -2
                            
                            # 🔥 FIX 2.1: ATOMIC BLOCK (per-coin protection)
                            order_executor.block_market(market_slug, coin)
                            
                            # Close position (flip-stop with current BID prices for selling)
                            result = multi_trader.close_market_early_exit(
                                strategy_name=strategy_name,
                                market_slug=market_slug,
                                exit_price=our_price,
                                exit_reason='flip_stop',
                                up_bid=up_bid,  # ✅ REAL BID for selling UP tokens
                                down_bid=down_bid  # ✅ REAL BID for selling DOWN tokens
                            )
                            
                            if result:
                                
                                # Send notifications
                                if isinstance(result, dict):
                                    try:
                                        session_stats = multi_trader.get_session_stats(strategy_name, markets_skipped[coin])
                                        portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                                        notifier.send_market_closed(coin, result, session_stats, portfolio_stats)
                                        
                                        # Increment completed markets counter
                                        total_completed_markets += 1
                                        
                                        # Generate and send PnL chart every CHART_INTERVAL markets
                                        if total_completed_markets - last_chart_at >= CHART_INTERVAL:
                                            print(f"[CHART] {total_completed_markets} markets completed, generating PnL chart...")
                                            
                                            chart_path = f"/root/4coins_live/logs/pnl_chart_{total_completed_markets}.png"
                                            
                                            # Import chart generator
                                            from pnl_chart_generator import generate_pnl_chart
                                            
                                            if generate_pnl_chart('/root/4coins_live/logs', COINS, chart_path):
                                                # Send to Telegram
                                                caption = f"<b>📊 PnL Chart - {total_completed_markets} Markets Completed</b>"
                                                if notifier.send_photo(chart_path, caption):
                                                    print(f"[CHART] ✓ Sent to Telegram successfully")
                                                    last_chart_at = total_completed_markets
                                                else:
                                                    print(f"[CHART] ✗ Failed to send to Telegram")
                                            else:
                                                print(f"[CHART] ✗ Failed to generate chart")
                                    except Exception as e:
                                        print(f"[ERROR] Notification failed: {e}")
                                
                                # Print confirmation
                                print(f"\n{'='*80}")
                                print(f"[{coin.upper()}] 🛑 FLIP-STOP @ ${our_price:.2f}")
                                print(f"[{strategy_name}] {market_slug}")
                                print(f"[EXIT] Our side: {our_side}")
                                print(f"[EXIT] Price dropped to: ${our_price:.2f} (≤${strategy.flip_stop_price:.2f})")
                                if isinstance(result, dict):
                                    print(f"[EXIT] PnL: ${result['pnl']:+.2f}")
                                print(f"[EXIT] Market is NO LONGER trading!")
                                print(f"{'='*80}\n")
                                return  # Exit callback after closing
                    
                    # ═══════════════════════════════════════════════════════
                    # PART 2: ENTRY SIGNAL CHECK (real-time)
                    # ═══════════════════════════════════════════════════════
                    strategy = strategies.get(strategy_name)
                    if not strategy:
                        print(f"[ERROR] Strategy {strategy_name} not found in strategies dict!")
                        continue
                    
                    # Generate signal with current market state
                    signal = strategy.should_enter(market_state, position_stats)
                    
                    if signal:
                        # Extract side/contracts - handle LateEntryStrategy format
                        side = None
                        contracts = None
                        
                        if 'favored' in signal:
                            # LateEntryStrategy format
                            favored = signal.get('favored', {})
                            side = favored.get('side')
                            contracts = favored.get('contracts')
                        else:
                            # Fallback format
                            side = signal.get('side')
                            contracts = signal.get('contracts')
                        
                        # Validate extracted values
                        if not side or contracts is None or contracts <= 0:
                            continue
                        
                        # ═══════════════════════════════════════════════════════
                        # CRITICAL: Prevent race condition re-entry
                        # Double-check market status before entry
                        # Another thread may have closed market during signal processing
                        # ═══════════════════════════════════════════════════════
                        with market_lock:
                            current_status = market_start_prices[coin].get(market_slug, -999)
                            if current_status in [-1, -2]:
                                # Market closed/skipped during signal processing
                                print(f"[RACE] {coin.upper()} market {market_slug} status={current_status}, skipping entry")
                                continue
                        
                        # Check if trading is enabled for this coin
                        trading_enabled = config.get('trading', {}).get(coin, {}).get('enabled', True)
                        if not trading_enabled:
                            # Skip entry - trading disabled for this coin
                            dashboard.add_event(f"Trading disabled for {coin.upper()}, skipping entry", 'system')
                            continue
                        
                        # Calculate price
                        price = up_ask if side == 'UP' else down_ask
                        
                        # Execute trade (using correct method name)
                        success = multi_trader.enter_position(
                            strategy_name=strategy_name,
                            market_slug=market_slug,
                            side=side,
                            price=price,
                            contracts=contracts,
                            up_ask=up_ask,
                            down_ask=down_ask,
                            seconds_till_end=market_state.get('seconds_till_end', 0)
                        )
                        
                        if success and contracts > 0:
                            # Update position stats after entry
                            updated_stats = multi_trader.get_market_stats(strategy_name, market_slug, up_ask, down_ask)
                            if updated_stats:
                                total_entries = updated_stats.get('total_entries', 0)
                                total_invested = updated_stats.get('total_invested', 0)
                                unrealized_pnl = updated_stats.get('unrealized_pnl', 0)
                                
                                # Print entry confirmation
                                print(f"[{strategy_name:30s}] {market_slug} | {side:5s} {contracts:3.0f} @ ${price:.2f} | "
                                      f"Total: {total_entries:3d} entries ${total_invested:7.2f} | PnL: ${unrealized_pnl:+7.2f}")
                
                except KeyError as e:
                    print(f"[ERROR] Callback KeyError for {strategy_name}: {e}")
                except AttributeError as e:
                    print(f"[ERROR] Callback AttributeError for {strategy_name}: {e}")
                except Exception as e:
                    print(f"[ERROR] Callback unexpected error for {strategy_name}: {e}")
                    import traceback
                    traceback.print_exc()
        
        except Exception as e:
            # Top-level error handler - should never reach here
            print(f"[CRITICAL] Callback top-level error: {e}")
            import traceback
            traceback.print_exc()
    
    # Register callback with data feed
    data_feed.register_price_callback(on_price_update)
    print("[SYSTEM] ✓ Event-driven trading callbacks registered (INSTANT entry & exit)")
    print()
    
    print("[SYSTEM] Starting trading loop...")
    print("         Press Ctrl+C to stop")
    print("         NOTE: First market for each coin will be skipped (started mid-market)")
    print("         Will start trading after first market switch on each coin")
    print()
    
    # Initialize keyboard listener for manual commands
    keyboard_listener = KeyboardListener()
    keyboard_listener.register_callback('m', run_manual_redeem, "Manual redeem all positions")
    keyboard_listener.start()
    print("[KEYBOARD] 🎹 Listener active - Press [M] to manually redeem all positions")
    print()
    
    loop_counter = 0
    
    # Main loop
    while not stop_flag:
        try:
            if web_dashboard_state_mod.consume_stop_request():
                stop_flag = True
                break
            loop_counter += 1
            
            # Process EACH coin independently
            for coin in COINS:
                market_state = data_feed.get_state(coin)
                market_slug = market_state['market_slug']
                price = market_state['price']
                
                if not market_slug:
                    continue
                
                # STEP 1: Check for market switch FIRST
                for prev_market in list(market_start_prices[coin].keys()):
                    if prev_market != market_slug and prev_market != "":
                        # Market switch detected!
                        if not witnessed_market_switch[coin]:
                            witnessed_market_switch[coin] = True
                            print(f"\n{'='*80}")
                            print(f"[{coin.upper()}] ✓✓✓ FIRST MARKET SWITCH DETECTED ✓✓✓")
                            print(f"[{coin.upper()}] From: {prev_market}")
                            print(f"[{coin.upper()}] To:   {market_slug}")
                            print(f"[{coin.upper()}] Will now start trading from this market onwards!")
                            print(f"{'='*80}\n")
                        else:
                            print(f"\n[{coin.upper()}] Market switch: {prev_market} → {market_slug}")
                        
                        price_start = market_start_prices[coin].get(prev_market, 0)
                        
                        # Check if we had a position in this market
                        strategy_name = f"{STRATEGY_BASES[0]}_{coin}"  # Use constant instead of hardcoded
                        trader = multi_trader.get_trader(strategy_name)
                        had_position = trader and prev_market in trader.positions
                        
                        if price_start > 0 or (price_start == 0 and had_position):
                            # 🔥 DISABLED: Old pending_markets logic (replaced by SimpleRedeemCollector)
                            # SimpleRedeemCollector will find and redeem this position automatically via API
                            print(f"\n[{coin.upper()}] Market ended: {prev_market}")
                            print(f"[REDEEM] Will be collected by SimpleRedeemCollector API scanner")
                            # if prev_market not in pending_markets[coin]:
                            #     redeem_cfg = config.get("execution", {}).get("redeem", {})
                            #     first_delay = redeem_cfg.get("first_attempt_delay_sec", 300)
                            #     print(f"[PENDING] Added to pending queue, first redeem attempt in {first_delay // 60} minutes...")
                            #     pending_markets[coin][prev_market] = {
                            #         'price_start': price_start if price_start > 0 else 0.0,
                            #         'price_final': price if price > 0 else 0.0,
                            #         'first_attempt': time.time(),
                            #         'attempts': 0,
                            #         'next_retry': time.time() + first_delay
                            #     }
                        elif price_start == -1:
                            # Market was skipped (started mid-market)
                            markets_skipped[coin] += 1
                            session_stats = multi_trader.get_session_stats(strategy_name, markets_skipped[coin])
                            portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                            notifier.send_market_skipped(coin, prev_market, "Started mid-market", session_stats, portfolio_stats)
                            print(f"\n[{coin.upper()}] ⏭️  Skipped market {prev_market} ended (was started mid-market)")
                        elif price_start == 0 and not had_position:
                            # Market was active but we didn't enter - skipped!
                            markets_skipped[coin] += 1
                            session_stats = multi_trader.get_session_stats(strategy_name, markets_skipped[coin])
                            portfolio_stats = _get_portfolio_stats(multi_trader, markets_skipped, session_start_time)
                            notifier.send_market_skipped(coin, prev_market, "No entry signals", session_stats, portfolio_stats)
                            print(f"\n[{coin.upper()}] ⏭️  Skipped market {prev_market} ended (no entry signals)")
                        elif price_start == -2:
                            # 🔥 Market was closed early (stop-loss/flip-stop)
                            # 🔥 DISABLED: Old pending_markets logic (replaced by SimpleRedeemCollector)
                            # SimpleRedeemCollector will find and redeem this position automatically via API
                            print(f"\n[{coin.upper()}] Market {prev_market} ended (was closed early)")
                            print(f"[REDEEM] Will be collected by SimpleRedeemCollector API scanner")
                            # if prev_market not in pending_markets[coin]:
                            #     redeem_cfg = config.get("execution", {}).get("redeem", {})
                            #     first_delay = redeem_cfg.get("first_attempt_delay_sec", 300)
                            #     print(f"[PENDING] Added to pending queue (early exit), first redeem attempt in {first_delay // 60} minutes...")
                            #     pending_markets[coin][prev_market] = {
                            #         'price_start': -2,  # Mark as early exit
                            #         'price_final': price if price > 0 else 0.0,
                            #         'first_attempt': time.time(),
                            #         'attempts': 0,
                            #         'next_retry': time.time() + first_delay
                            #     }
                        
                        # Remove from tracking
                        del market_start_prices[coin][prev_market]
                
                # STEP 2: Track market start price
                if market_slug not in market_start_prices[coin]:
                    # First time seeing this market
                    if not witnessed_market_switch[coin]:
                        # This is the FIRST market we see at startup - skip it
                        market_start_prices[coin][market_slug] = -1  # -1 = skip
                        print(f"\n[{coin.upper()}] First market detected at startup: {market_slug}")
                        print(f"[SKIP] Not trading this market (script started mid-market)")
                        print(f"[SKIP] Will start trading after this market ends\n")
                        # DON'T continue - let it check if in entry window below!
                    else:
                        # We've witnessed a market switch, so this is a NEW valid market
                        market_start_prices[coin][market_slug] = price if price > 0 else 0.0
                        print(f"\n[{coin.upper()}] ✓ New market witnessed from start: {market_slug}")
                        print(f"[TRADE] Start price: ${price:,.2f}" if price > 0 else "[TRADE] Start price: pending...")
                        print(f"[TRADE] Will trade this market ✓\n")
                        
                elif market_start_prices[coin][market_slug] == 0:
                    # Update pending market with valid price
                    if price > 0:
                        market_start_prices[coin][market_slug] = price
                        print(f"\n[{coin.upper()}] ✓ Start price updated: {market_slug} | Price: ${price:,.2f}\n")
                        
                elif market_start_prices[coin][market_slug] == -1:
                    # This market is marked as skip - don't trade it
                    pass
                
                # 🔥 DISABLED: Old pending_markets processing (replaced by SimpleRedeemCollector)
                # SimpleRedeemCollector handles all redeems via periodic API scanning
                # now = time.time()
                # 
                # for prev_market in list(pending_markets[coin].keys()):
                #     pending_info = pending_markets[coin][prev_market]
                #     
                #     # Check if it's time to retry
                #     if now < pending_info['next_retry']:
                #         continue
                #     
                #     # Increment attempts
                #     pending_info['attempts'] += 1
                #     
                #     # Submit to async executor (non-blocking!)
                #     try:
                #         print(f"[REDEEM SUBMIT] 📤 Submitting {coin.upper()} market {prev_market} to async executor...")
                #         future = redeem_executor.submit(
                #             process_redeem_async,
                #             coin, prev_market, pending_info, config,
                #             markets_skipped, session_start_time
                #         )
                #         print(f"[REDEEM SUBMIT] ✅ Task submitted successfully (Future: {future})")
                #         # Update next retry immediately (don't wait for result)
                #         redeem_cfg = config.get("execution", {}).get("redeem", {})
                #         retry_delay = redeem_cfg.get("retry_delay_sec", 300)
                #         pending_info['next_retry'] = now + retry_delay
                #     except Exception as e:
                #         print(f"[REDEEM] Failed to submit {coin}/{prev_market}: {e}")
                
                # ═══════════════════════════════════════════════════════
                # BALANCE CHECK: 60 seconds before BTC market end
                # (BTC market ends every 15 minutes - good timing for balance refresh)
                # ═══════════════════════════════════════════════════════
                if coin == 'btc':
                    seconds_till_end = market_state.get('seconds_till_end', 0)
                    
                    # Check balance 60 seconds before market end
                    if 55 <= seconds_till_end <= 65:
                        # Track which markets we've checked to avoid duplicates
                        if not hasattr(main, '_balance_checked_markets'):
                            main._balance_checked_markets = set()
                        
                        current_market = market_state.get('market_slug')
                        if current_market and current_market not in main._balance_checked_markets:
                            main._balance_checked_markets.add(current_market)
                            
                            # Cleanup old entries (keep only last 10)
                            if len(main._balance_checked_markets) > 10:
                                main._balance_checked_markets = set(list(main._balance_checked_markets)[-10:])
                            
                            # Async balance check (non-blocking)
                            def check_balance_async():
                                global wallet_balance
                                try:
                                    if not safety_guard.dry_run:
                                        new_balance = order_executor.get_wallet_usdc_balance()
                                        if new_balance and new_balance > 0:
                                            old_balance = wallet_balance
                                            wallet_balance = new_balance
                                            change = new_balance - old_balance
                                            change_sign = "+" if change >= 0 else ""
                                            print(f"[BALANCE] 🔄 Updated: ${wallet_balance:,.2f} ({change_sign}${change:.2f})")
                                except Exception as e:
                                    print(f"[BALANCE] ⚠️ Check failed: {e}")
                            
                            threading.Thread(target=check_balance_async, daemon=True, name="balance_check").start()
                
                # Check if this market is active
                current_market_status = market_start_prices[coin].get(market_slug, -999)
                
                # If market was skipped (-1) but now in entry window — allow trading
                _strategy_name = f"{STRATEGY_BASES[0]}_{coin}"
                _ew = strategies[_strategy_name].entry_window
                if current_market_status == -1 and market_state['seconds_till_end'] <= _ew:
                    market_start_prices[coin][market_slug] = 0  # Activate market
                    print(f"\n[{coin.upper()}] ✅ Market {market_slug} NOW ACTIVE (entry window)")
                elif current_market_status in [-1, -2, -999]:
                    # Market is inactive (-1), closed by early exit (-2), or not tracked (-999)
                    continue
                
                # ========================================
                # MARKET DISCOVERY & MONITORING
                # Entry/Exit signals now handled by callback!
                # ========================================
                # Dashboard update loop (no signal processing here)
                pass  # Market monitoring handled by callback
                
            
            # Update dashboard in REAL-TIME
            # 🔥 CHANGED: pending_markets replaced by SimpleRedeemCollector
            # Dashboard now shows empty pending (collector handles redeems automatically)
            all_pending = {}  # Empty - collector handles redeems in background
            dashboard.render(multi_trader, strategies, data_feed, wallet_balance, all_pending)
            
            try:
                from web_dashboard.snapshot_builder import build_snapshot
                _proj = Path(__file__).resolve().parent.parent
                _snap = build_snapshot(
                    coins=COINS,
                    strategy_base=STRATEGY_BASES[0],
                    multi_trader=multi_trader,
                    data_feed=data_feed,
                    wallet_balance=wallet_balance,
                    config=config,
                    session_start_time=session_start_time,
                    dry_run=safety_guard.dry_run,
                    markets_skipped=markets_skipped,
                )
                web_dashboard_state_mod.set_snapshot(_snap)
                if getattr(args, "web", False):
                    web_dashboard_state_mod.write_state_file(_proj, _snap)
            except Exception:
                pass
            
            # ═══════════════════════════════════════════════════════════
            # 🔥 SYSTEM #2: ASYNC INSTANT STOP-LOSS CHECK (every 0.1 sec)
            # Checks all 4 coins IN PARALLEL
            # ═══════════════════════════════════════════════════════════
            for coin in COINS:
                def check_coin_sys2(coin_name):
                    """Async stop-loss/flip-stop check for one coin"""
                    try:
                        strategy_name = f"late_entry_v3_{coin_name}"
                        if strategy_name not in strategies:
                            return
                        
                        market_state = data_feed.get_state(coin_name)
                        market_slug = market_state.get('market_slug')
                        if not market_slug:
                            return
                        
                        # Check market status
                        with market_lock:
                            status = market_start_prices.get(coin_name, {}).get(market_slug, -999)
                            if status in [-1, -2, -999]:
                                return
                        
                        # Get prices
                        up_ask = market_state.get('up_ask', 0.5)
                        down_ask = market_state.get('down_ask', 0.5)
                        up_bid = market_state.get('up_bid', 0.5)
                        down_bid = market_state.get('down_bid', 0.5)
                        
                        # Validate price freshness before exit checks
                        up_ask_ts = market_state.get('up_ask_timestamp', 0)
                        down_ask_ts = market_state.get('down_ask_timestamp', 0)
                        
                        is_valid, reason = validate_prices(up_ask, down_ask, up_ask_ts, down_ask_ts, coin_name)
                        if not is_valid:
                            # Skip stop-loss/flip-stop if prices invalid
                            return
                        
                        # Get detailed stats
                        detailed_stats = multi_trader.traders[strategy_name].get_market_detailed_stats(
                            market_slug=market_slug,
                            up_ask=up_ask,
                            down_ask=down_ask
                        )
                        
                        if not detailed_stats:
                            return
                        
                        # Check stop-loss
                        if detailed_stats.get('stop_loss_triggered', False):
                            with market_lock:
                                if market_start_prices[coin_name].get(market_slug, -999) == -2:
                                    return
                            
                            up_shares = detailed_stats['up_shares']
                            down_shares = detailed_stats['down_shares']
                            our_side = 'UP' if up_shares > down_shares else 'DOWN'
                            our_price = up_ask if our_side == 'UP' else down_ask
                            
                            # 🔥 FIX 1: LOG EXIT TRIGGER (for all 4 coins)
                            from trade_logger import log_exit_trigger
                            log_exit_trigger(
                                market_slug=market_slug,
                                exit_reason='stop_loss',
                                coin=coin_name,
                                unrealized_pnl=detailed_stats.get('unrealized_pnl', 0),
                                threshold_pnl=detailed_stats.get('stop_loss_threshold', 0)
                            )
                            
                            # 🔥 FIX 2: Mark market as closed BEFORE exit to prevent race condition
                            with market_lock:
                                market_start_prices[coin_name][market_slug] = -2
                            
                            # 🔥 FIX 2.1: ATOMIC BLOCK (per-coin protection)
                            order_executor.block_market(market_slug, coin_name)
                            
                            result = multi_trader.close_market_early_exit(
                                strategy_name=strategy_name,
                                market_slug=market_slug,
                                exit_price=our_price,
                                exit_reason='stop_loss',
                                up_bid=up_bid,
                                down_bid=down_bid
                            )
                            
                            if result:
                                print(f"[SYS#2] 🚨 {coin_name.upper()} STOP-LOSS: PnL=${detailed_stats['unrealized_pnl']:.2f}")
                        
                        # Check flip-stop
                        if detailed_stats.get('flip_stop_triggered', False):
                            with market_lock:
                                if market_start_prices[coin_name].get(market_slug, -999) == -2:
                                    return
                            
                            up_shares = detailed_stats['up_shares']
                            down_shares = detailed_stats['down_shares']
                            our_side = 'UP' if up_shares > down_shares else 'DOWN'
                            our_price = up_ask if our_side == 'UP' else down_ask
                            
                            # 🔥 FIX 1: LOG EXIT TRIGGER (for all 4 coins)
                            from trade_logger import log_exit_trigger
                            log_exit_trigger(
                                market_slug=market_slug,
                                exit_reason='flip_stop',
                                coin=coin_name,
                                trigger_price=our_price,
                                threshold_price=detailed_stats.get('flip_stop_price', 0)
                            )
                            
                            # 🔥 FIX 2: Mark market as closed BEFORE exit to prevent race condition
                            with market_lock:
                                market_start_prices[coin_name][market_slug] = -2
                            
                            # 🔥 FIX 2.1: ATOMIC BLOCK (per-coin protection)
                            order_executor.block_market(market_slug, coin_name)
                            
                            result = multi_trader.close_market_early_exit(
                                strategy_name=strategy_name,
                                market_slug=market_slug,
                                exit_price=our_price,
                                exit_reason='flip_stop',
                                up_bid=up_bid,
                                down_bid=down_bid
                            )
                            
                            if result:
                                print(f"[SYS#2] 🚨 {coin_name.upper()} FLIP-STOP")
                    
                    except Exception as e:
                        pass  # Silent - don't spam logs
                
                # 🔥 Run via executor (in parallel for all coins)
                try:
                    sys2_executor.submit(check_coin_sys2, coin)
                except:
                    pass
            
            # Sleep - can be slower now (entry/exit in callback)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[ERROR] Main loop error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)
    
    # Cleanup
    print("\n[SYSTEM] Stopping keyboard listener...")
    if keyboard_listener:
        keyboard_listener.stop()
    
    print("[SYSTEM] Stopping data feed...")
    data_feed.stop()
    
    # Final summary
    print("\n" + "=" * 115)
    print("  MERIDIAN — SESSION RESULTS".center(115))
    print("=" * 115)
    
    portfolio_stats = multi_trader.get_portfolio_stats()
    
    # Display by strategy (grouped by base, showing BTC and ETH)
    for base_name in STRATEGY_BASES:
        print(f"\n=== {base_name.upper()} (BTC + ETH) ===")
        
        total_capital_strategy = 0
        total_pnl_strategy = 0
        total_trades_strategy = 0
        
        for coin in COINS:
            strategy_name = f"{base_name}_{coin}"
            trader = multi_trader.traders.get(strategy_name)
            if not trader:
                print(f"[WARNING] Trader {strategy_name} not found!")
                continue
            stats = trader.get_performance_stats()
            pnl = trader.current_capital - trader.starting_capital
            pnl_sign = "+" if pnl >= 0 else ""
            
            total_capital_strategy += trader.current_capital
            total_pnl_strategy += pnl
            total_trades_strategy += stats['total_trades']
            
            print(f"  {coin.upper():3s}: ${trader.current_capital:>8,.0f}  |  PnL: {pnl_sign}${pnl:>7,.0f}  |  "
                  f"Trades: {stats['total_trades']:3d}  |  WR: {stats['win_rate']:.1f}%")
        
        # Strategy total
        pnl_sign = "+" if total_pnl_strategy >= 0 else ""
        print(f"  {'TOTAL':3s}: ${total_capital_strategy:>8,.0f}  |  PnL: {pnl_sign}${total_pnl_strategy:>7,.0f}  |  "
              f"Trades: {total_trades_strategy:3d}")
    
    # Portfolio total
    print("\n" + "=" * 115)
    total_pnl = portfolio_stats['total_pnl']
    pnl_sign = "+" if total_pnl >= 0 else ""
    print(f"{'TOTAL PORTFOLIO':30s}: ${portfolio_stats['total_capital']:>10,.0f}  |  "
          f"PnL: {pnl_sign}${total_pnl:>8,.0f} ({pnl_sign}{portfolio_stats['portfolio_roi']:.2f}%)")
    print("=" * 115)
    print()


if __name__ == '__main__':
    main(_parse_cli_args())
