#!/usr/bin/env python3
"""
Help script - displays available commands and usage information
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style

init(autoreset=True)

def print_help():
    """Print comprehensive help information"""
    print(f"""
{Fore.CYAN}{Style.BRIGHT}{'=' * 80}{Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}  POLYMARKET COPY TRADING BOT - COMMAND REFERENCE{Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}{'=' * 80}{Style.RESET_ALL}

{Fore.YELLOW}{Style.BRIGHT}📖 GETTING STARTED{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.setup.setup{Style.RESET_ALL}              Interactive configuration wizard (npm: setup)
  {Fore.GREEN}python -m src.scripts.setup.system_status{Style.RESET_ALL}     Verify system status and configuration (npm: health-check)
  {Fore.GREEN}python -m src.scripts.setup.help{Style.RESET_ALL}               Show this help message (npm: help)
  {Fore.GREEN}python -m src.main{Style.RESET_ALL}                      Start the trading bot (npm: start/dev)

{Fore.YELLOW}{Style.BRIGHT}💰 WALLET & BALANCE MANAGEMENT{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.wallet.check_proxy_wallet{Style.RESET_ALL}        Check proxy wallet balance and positions (npm: check-proxy)
  {Fore.GREEN}python -m src.scripts.wallet.check_both_wallets{Style.RESET_ALL}         Compare two wallet addresses (npm: check-both)
  {Fore.GREEN}python -m src.scripts.wallet.check_my_stats{Style.RESET_ALL}            View trading statistics (npm: check-stats)
  {Fore.GREEN}python -m src.scripts.wallet.check_recent_activity{Style.RESET_ALL}     See recent trading activity (npm: check-activity)
  {Fore.GREEN}python -m src.scripts.wallet.check_positions_detailed{Style.RESET_ALL}  View detailed position information
  {Fore.GREEN}python -m src.scripts.wallet.check_pnl_discrepancy{Style.RESET_ALL}     Check P&L discrepancy analysis (npm: check-pnl)
  {Fore.GREEN}python -m src.scripts.wallet.verify_allowance{Style.RESET_ALL}          Verify USDC token allowance (npm: verify-allowance)
  {Fore.GREEN}python -m src.scripts.wallet.check_allowance{Style.RESET_ALL}           Check and set USDC allowance (npm: check-allowance)
  {Fore.GREEN}python -m src.scripts.wallet.set_token_allowance{Style.RESET_ALL}       Set ERC1155 token allowance (npm: set-token-allowance)
  {Fore.GREEN}python -m src.scripts.wallet.find_my_eoa{Style.RESET_ALL}                Find and analyze EOA wallet
  {Fore.GREEN}python -m src.scripts.wallet.find_gnosis_safe_proxy{Style.RESET_ALL}    Find Gnosis Safe proxy wallet

{Fore.YELLOW}{Style.BRIGHT}📊 POSITION MANAGEMENT{Style.RESET_ALL}
{Fore.YELLOW}  ⚠️  Note: These require full CLOB client implementation{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.position.manual_sell{Style.RESET_ALL}              Manually sell a specific position (npm: manual-sell)
  {Fore.GREEN}python -m src.scripts.position.sell_large_positions{Style.RESET_ALL}       Sell large positions (npm: sell-large)
  {Fore.GREEN}python -m src.scripts.position.close_stale_positions{Style.RESET_ALL}     Close stale/old positions (npm: close-stale)
  {Fore.GREEN}python -m src.scripts.position.close_resolved_positions{Style.RESET_ALL}  Close resolved positions (npm: close-resolved)
  {Fore.GREEN}python -m src.scripts.position.redeem_resolved_positions{Style.RESET_ALL} Redeem resolved positions (npm: redeem-resolved)

{Fore.YELLOW}{Style.BRIGHT}🔍 TRADER RESEARCH & ANALYSIS{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.research.find_best_traders{Style.RESET_ALL}          Find best performing traders (npm: find-traders)
  {Fore.GREEN}python -m src.scripts.research.find_low_risk_traders{Style.RESET_ALL}     Find low-risk traders with good metrics (npm: find-low-risk)
  {Fore.GREEN}python -m src.scripts.research.scan_best_traders{Style.RESET_ALL}          Scan and analyze top traders (npm: scan-traders)
  {Fore.GREEN}python -m src.scripts.research.scan_traders_from_markets{Style.RESET_ALL}  Scan traders from active markets (npm: scan-markets)

{Fore.YELLOW}{Style.BRIGHT}📈 SIMULATION & BACKTESTING{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.simulation.simulate_profitability{Style.RESET_ALL}     Simulate profitability for a trader (npm: simulate)
  {Fore.GREEN}python -m src.scripts.simulation.simulate_profitability_old{Style.RESET_ALL} Old simulation logic (npm: simulate-old)
  {Fore.GREEN}python -m src.scripts.simulation.run_simulations{Style.RESET_ALL}             Run comprehensive batch simulations (npm: sim)
  {Fore.GREEN}python -m src.scripts.simulation.compare_results{Style.RESET_ALL}             Compare simulation results (npm: compare)
  {Fore.GREEN}python -m src.scripts.simulation.aggregate_results{Style.RESET_ALL}          Aggregate trading results across strategies (npm: aggregate)
  {Fore.GREEN}python -m src.scripts.simulation.audit_copy_trading{Style.RESET_ALL}         Audit copy trading algorithm (npm: audit)
  {Fore.GREEN}python -m src.scripts.simulation.fetch_historical_trades{Style.RESET_ALL}    Fetch and cache historical trade data (npm: fetch-history)

{Fore.YELLOW}{Style.BRIGHT}🔧 UTILITIES{Style.RESET_ALL}

  {Fore.GREEN}python -m src.scripts.setup.help{Style.RESET_ALL}                       Show this help message
  {Fore.GREEN}python -m src.scripts.setup.system_status{Style.RESET_ALL}              Check system status and diagnostics

{Fore.YELLOW}{Style.BRIGHT}📚 DOCUMENTATION{Style.RESET_ALL}

  {Fore.CYAN}README_PYTHON.md{Style.RESET_ALL}                    Python-specific documentation
  {Fore.CYAN}README.md{Style.RESET_ALL}                           Full project documentation
  {Fore.CYAN}PYTHON_SCRIPTS_STATUS.md{Style.RESET_ALL}            Script conversion status
  {Fore.CYAN}PROJECT_STRUCTURE.md{Style.RESET_ALL}                 Detailed project structure
  {Fore.CYAN}docs/QUICK_START.md{Style.RESET_ALL}                 5-minute quick start guide
  {Fore.CYAN}docs/GETTING_STARTED.md{Style.RESET_ALL}             Complete beginner's guide

{Fore.BLUE}{Style.BRIGHT}{'─' * 80}{Style.RESET_ALL}

{Fore.YELLOW}{Style.BRIGHT}💡 QUICK START GUIDE{Style.RESET_ALL}

  1. {Fore.CYAN}Setup Configuration:{Style.RESET_ALL}
     {Fore.GREEN}python -m src.scripts.setup.setup{Style.RESET_ALL}

  2. {Fore.CYAN}Verify System Status:{Style.RESET_ALL}
     {Fore.GREEN}python -m src.scripts.setup.system_status{Style.RESET_ALL}

  3. {Fore.CYAN}Start Trading Bot:{Style.RESET_ALL}
     {Fore.GREEN}python -m src.main{Style.RESET_ALL}

  4. {Fore.CYAN}Monitor Performance:{Style.RESET_ALL}
     {Fore.GREEN}python -m src.scripts.wallet.check_my_stats{Style.RESET_ALL}
     {Fore.GREEN}python -m src.scripts.wallet.check_recent_activity{Style.RESET_ALL}

{Fore.BLUE}{Style.BRIGHT}{'─' * 80}{Style.RESET_ALL}

{Fore.YELLOW}{Style.BRIGHT}⚠️  IMPORTANT REMINDERS{Style.RESET_ALL}

  • Always start with small amounts to test the bot
  • Monitor the bot regularly, especially during initial runs
  • Verify system status before starting: {Fore.CYAN}python -m src.scripts.setup.system_status{Style.RESET_ALL}
  • Check wallet balance and allowances before trading
  • Review trader performance before adding to USER_ADDRESSES
  • Use simulation tools to test strategies before live trading
  • Emergency stop: Press {Fore.RED}Ctrl+C{Style.RESET_ALL}

{Fore.BLUE}{Style.BRIGHT}{'─' * 80}{Style.RESET_ALL}

{Fore.YELLOW}{Style.BRIGHT}📖 COMMAND CATEGORIES{Style.RESET_ALL}

  {Fore.CYAN}Setup & Config{Style.RESET_ALL}     → setup, system_status, help
  {Fore.CYAN}Wallet Management{Style.RESET_ALL}   → check_proxy_wallet, check_my_stats, verify_allowance
  {Fore.CYAN}Position Management{Style.RESET_ALL} → manual_sell, close_stale_positions, redeem_resolved_positions
  {Fore.CYAN}Trader Research{Style.RESET_ALL}    → find_best_traders, find_low_risk_traders, scan_best_traders
  {Fore.CYAN}Simulation{Style.RESET_ALL}         → simulate_profitability, run_simulations, compare_results
  {Fore.CYAN}Analysis{Style.RESET_ALL}            → aggregate_results, audit_copy_trading, fetch_historical_trades

{Fore.BLUE}{Style.BRIGHT}{'─' * 80}{Style.RESET_ALL}

{Fore.CYAN}For more information, visit:{Style.RESET_ALL} {Fore.YELLOW}README_PYTHON.md{Style.RESET_ALL}
{Fore.CYAN}For npm command equivalents, see:{Style.RESET_ALL} {Fore.YELLOW}package.json{Style.RESET_ALL}

{Fore.CYAN}{Style.BRIGHT}{'=' * 80}{Style.RESET_ALL}
""")

if __name__ == '__main__':
    print_help()
