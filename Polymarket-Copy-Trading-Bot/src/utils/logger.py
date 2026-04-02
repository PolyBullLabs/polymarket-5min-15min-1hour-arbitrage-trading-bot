"""
Logger utility with colored output and file logging
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    USE_COLORS = True
except ImportError:
    USE_COLORS = False
    # Fallback colors (empty strings if colorama not available)
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = BLACK = WHITE = ''
    class Style:
        RESET_ALL = BRIGHT = DIM = ''

logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)


def get_log_file_name() -> Path:
    """Get log file name for today"""
    date = datetime.now().strftime('%Y-%m-%d')
    return logs_dir / f'bot-{date}.log'


def write_to_file(message: str) -> None:
    """Write message to log file"""
    try:
        log_file = get_log_file_name()
        timestamp = datetime.now().isoformat()
        log_entry = f'[{timestamp}] {message}\n'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception:
        # Silently fail to avoid infinite loops
        pass


def format_address(address: str) -> str:
    """Format address for display"""
    return f'{address[:6]}...{address[-4:]}'


def mask_address(address: str) -> str:
    """Mask address for display"""
    return f'{address[:6]}{"*" * 34}{address[-4:]}'


def header(title: str) -> None:
    """Print header"""
    print(f'\n{Fore.CYAN}{Style.BRIGHT}{"=" * 70}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}  {title}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}{"=" * 70}{Style.RESET_ALL}\n')
    write_to_file(f'HEADER: {title}')


def info(message: str) -> None:
    """Print info message"""
    print(f'{Fore.BLUE}[INFO]{Style.RESET_ALL} {message}')
    write_to_file(f'INFO: {message}')


def success(message: str) -> None:
    """Print success message"""
    print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}')
    write_to_file(f'SUCCESS: {message}')


def warning(message: str) -> None:
    """Print warning message"""
    print(f'{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}')
    write_to_file(f'WARNING: {message}')


def error(message: str) -> None:
    """Print error message"""
    print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} {message}', file=sys.stderr)
    write_to_file(f'ERROR: {message}')


def trade(trader_address: str, action: str, details: dict) -> None:
    """Print trade information"""
    print(f'\n{Fore.MAGENTA}{"-" * 70}{Style.RESET_ALL}')
    print(f'{Fore.MAGENTA}{Style.BRIGHT}NEW TRADE DETECTED{Style.RESET_ALL}')
    print(f'{Fore.MAGENTA}{"-" * 70}{Style.RESET_ALL}')
    print(f'Trader: {Fore.CYAN}{format_address(trader_address)}{Style.RESET_ALL}')
    print(f'Action: {Style.BRIGHT}{action}{Style.RESET_ALL}')
    
    if details.get('asset'):
        print(f'Asset:  {Style.DIM}{format_address(details["asset"])}{Style.RESET_ALL}')
    if details.get('side'):
        side_color = Fore.GREEN if details['side'] == 'BUY' else Fore.RED
        print(f'Side:   {side_color}{Style.BRIGHT}{details["side"]}{Style.RESET_ALL}')
    if details.get('amount'):
        print(f'Amount: {Fore.YELLOW}${details["amount"]:.2f}{Style.RESET_ALL}')
    if details.get('price'):
        print(f'Price:  {Fore.CYAN}${details["price"]:.4f}{Style.RESET_ALL}')
    if details.get('eventSlug') or details.get('slug'):
        slug = details.get('eventSlug') or details.get('slug')
        market_url = f'https://polymarket.com/event/{slug}'
        print(f'Market: {Fore.BLUE}{market_url}{Style.RESET_ALL}')
    if details.get('transactionHash'):
        tx_url = f'https://polygonscan.com/tx/{details["transactionHash"]}'
        print(f'TX:     {Fore.BLUE}{tx_url}{Style.RESET_ALL}')
    
    print(f'{Fore.MAGENTA}{"-" * 70}{Style.RESET_ALL}\n')
    
    # Log to file
    trade_log = f'TRADE: {format_address(trader_address)} - {action}'
    if details.get('side'):
        trade_log += f' | Side: {details["side"]}'
    if details.get('amount'):
        trade_log += f' | Amount: ${details["amount"]:.2f}'
    if details.get('price'):
        trade_log += f' | Price: ${details["price"]:.4f}'
    if details.get('title'):
        trade_log += f' | Market: {details["title"]}'
    if details.get('transactionHash'):
        trade_log += f' | TX: {details["transactionHash"]}'
    write_to_file(trade_log)


def balance(my_balance: float, trader_balance: float, trader_address: str) -> None:
    """Print balance information"""
    print('Capital (USDC + Positions):')
    print(f'  Your total capital:   {Fore.GREEN}{Style.BRIGHT}${my_balance:.2f}{Style.RESET_ALL}')
    print(f'  Trader total capital: {Fore.BLUE}{Style.BRIGHT}${trader_balance:.2f}{Style.RESET_ALL} ({format_address(trader_address)})')


def order_result(success_flag: bool, message: str) -> None:
    """Print order result"""
    if success_flag:
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Order executed: {message}')
        write_to_file(f'ORDER SUCCESS: {message}')
    else:
        print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Order failed: {message}', file=sys.stderr)
        write_to_file(f'ORDER FAILED: {message}')


def monitoring(trader_count: int) -> None:
    """Print monitoring status"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f'{Style.DIM}[{timestamp}]{Style.RESET_ALL} {Fore.CYAN}[INFO]{Style.RESET_ALL} Monitoring {Fore.YELLOW}{trader_count}{Style.RESET_ALL} trader(s)')


def startup(traders: List[str], my_wallet: str) -> None:
    """Print startup banner"""
    # Boxed banner with text
    title = "COPY TRADING BOT"
    tagline = "Copy the best, automate success"
    
    border = '=' * 70
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}{'':^68}{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL} {Fore.MAGENTA}{Style.BRIGHT}{title:^66}{Style.RESET_ALL} {Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}{'':^68}{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL} {Style.DIM}{tagline:^66}{Style.RESET_ALL} {Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}{'':^68}{Fore.CYAN}{Style.BRIGHT}={Style.RESET_ALL}
{Fore.CYAN}{Style.BRIGHT}{border}{Style.RESET_ALL}
"""
    print(banner)
    print(f'{Fore.CYAN}{Style.BRIGHT}{"─" * 70}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}Tracking Traders:{Style.RESET_ALL}')
    for index, address in enumerate(traders, 1):
        print(f'  {index}. {Style.DIM}{address}{Style.RESET_ALL}')
    print(f'\n{Fore.CYAN}{Style.BRIGHT}Your Wallet:{Style.RESET_ALL} {Style.DIM}{mask_address(my_wallet)}{Style.RESET_ALL}\n')


def db_connection(traders: List[str], counts: List[int]) -> None:
    """Print database connection status"""
    print(f'\n{Fore.CYAN}Database Status:{Style.RESET_ALL}')
    for address, count in zip(traders, counts):
        print(f'  {format_address(address)}: {Fore.YELLOW}{count}{Style.RESET_ALL} trades')
    print('')


def separator() -> None:
    """Print separator line"""
    print(f'{Style.DIM}{"-" * 70}{Style.RESET_ALL}')


def waiting(trader_count: int, extra_info: Optional[str] = None) -> None:
    """Print waiting message"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    message = f'Waiting for trades from {trader_count} trader(s)'
    if extra_info:
        message += f' ({extra_info})'
    
    print(f'{Style.DIM}[{timestamp}]{Style.RESET_ALL} {Fore.CYAN}[INFO]{Style.RESET_ALL} {message}', end='\r')
    sys.stdout.flush()


def clear_line() -> None:
    """Clear current line"""
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()


def my_positions(
    wallet: str,
    count: int,
    top_positions: List[dict],
    overall_pnl: float,
    total_value: float,
    initial_value: float,
    current_balance: float
) -> None:
    """Print my positions information"""
    print(f'\n{Fore.MAGENTA}{Style.BRIGHT}Your Positions{Style.RESET_ALL}')
    print(f'{Fore.MAGENTA}{"-" * 70}{Style.RESET_ALL}')
    print(f'Wallet: {Style.DIM}{format_address(wallet)}{Style.RESET_ALL}')
    print('')
    
    # Show balance and portfolio overview
    total_portfolio = current_balance + total_value
    
    print(f'Available Cash:    {Fore.YELLOW}{Style.BRIGHT}${current_balance:.2f}{Style.RESET_ALL}')
    print(f'Total Portfolio:   {Fore.CYAN}{Style.BRIGHT}${total_portfolio:.2f}{Style.RESET_ALL}')
    
    if count == 0:
        print(f'\n{Style.DIM}No open positions{Style.RESET_ALL}')
    else:
        pnl_sign = '+' if overall_pnl >= 0 else ''
        pnl_color = Fore.GREEN if overall_pnl >= 0 else Fore.RED
        
        print('')
        print(f'Open Positions:    {Fore.GREEN}{count}{Style.RESET_ALL}')
        print(f'Invested:          {Style.DIM}${initial_value:.2f}{Style.RESET_ALL}')
        print(f'Current Value:     {Fore.CYAN}${total_value:.2f}{Style.RESET_ALL}')
        print(f'Profit/Loss:       {pnl_color}{pnl_sign}{overall_pnl:.1f}%{Style.RESET_ALL}')
        
        # Show top positions
        if top_positions:
            print(f'\n{Style.DIM}Top Positions:{Style.RESET_ALL}')
            for pos in top_positions:
                pnl_sign = '+' if pos.get('percentPnl', 0) >= 0 else ''
                avg_price = pos.get('avgPrice', 0)
                cur_price = pos.get('curPrice', 0)
                title = pos.get('title', '')[:45]
                if len(pos.get('title', '')) > 45:
                    title += '...'
                print(f'  {pos.get("outcome", "")} - {Style.DIM}{title}{Style.RESET_ALL}')
                pnl_value = pos.get('percentPnl', 0)
                pnl_color_pos = Fore.CYAN if pnl_value >= 0 else Fore.RED
                print(f'    Value: ${pos.get("currentValue", 0):.2f} | PnL: {pnl_color_pos}{pnl_sign}{pnl_value:.1f}%{Style.RESET_ALL}')
                print(f'    Bought @ {(avg_price * 100):.1f}¢ | Current @ {(cur_price * 100):.1f}¢')
    print('')


def traders_positions(
    traders: List[str],
    position_counts: List[int],
    position_details: Optional[List[List[dict]]] = None,
    profitabilities: Optional[List[float]] = None
) -> None:
    """Print traders positions information"""
    print(f'\n{Fore.CYAN}{Style.BRIGHT}Traders You Are Copying{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{"-" * 70}{Style.RESET_ALL}')
    for index, address in enumerate(traders):
        count = position_counts[index]
        count_str = (
            f'{count} position{"s" if count > 1 else ""}' if count > 0
            else '0 positions'
        )
        
        # Add profitability if available
        profit_str = ''
        if profitabilities and profitabilities[index] is not None and count > 0:
            pnl = profitabilities[index]
            pnl_sign = '+' if pnl >= 0 else ''
            pnl_color = Fore.GREEN if pnl >= 0 else Fore.RED
            profit_str = f' | PnL: {pnl_color}{pnl_sign}{pnl:.1f}%{Style.RESET_ALL}'
        
        print(f'  {Style.DIM}{format_address(address)}{Style.RESET_ALL}: {count_str}{profit_str}')
        
        # Show position details if available
        if position_details and position_details[index]:
            for pos in position_details[index]:
                pnl_sign = '+' if pos.get('percentPnl', 0) >= 0 else ''
                avg_price = pos.get('avgPrice', 0)
                cur_price = pos.get('curPrice', 0)
                title = pos.get('title', '')[:40]
                if len(pos.get('title', '')) > 40:
                    title += '...'
                print(f'    {pos.get("outcome", "")} - {Style.DIM}{title}{Style.RESET_ALL}')
                pnl_value = pos.get('percentPnl', 0)
                pnl_color_pos = Fore.CYAN if pnl_value >= 0 else Fore.RED
                print(f'      Value: ${pos.get("currentValue", 0):.2f} | PnL: {pnl_color_pos}{pnl_sign}{pnl_value:.1f}%{Style.RESET_ALL}')
                print(f'      Bought @ {(avg_price * 100):.1f}¢ | Current @ {(cur_price * 100):.1f}¢')
    print('')
