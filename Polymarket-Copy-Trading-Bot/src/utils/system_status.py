"""
System status and diagnostics utilities
"""
import sys
from typing import Dict, Any
from colorama import init, Fore, Style

init(autoreset=True)

from ..config.env import ENV
from ..utils.get_my_balance import get_my_balance_async


async def check_system_status() -> Dict[str, Any]:
    """Perform comprehensive system status check"""
    results = {
        'healthy': True,
        'checks': {},
        'summary': {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0
        }
    }
    
    # Check MongoDB connection
    results['summary']['total_checks'] += 1
    try:
        from ..config.db import get_client, get_database_name
        client = get_client()
        client.admin.command('ping')
        db_name = get_database_name()
        results['checks']['mongodb'] = {
            'status': 'ok',
            'message': 'Connected',
            'details': f'Database: {db_name}'
        }
        results['summary']['passed'] += 1
    except Exception as e:
        results['healthy'] = False
        results['checks']['mongodb'] = {
            'status': 'error',
            'message': 'Connection failed',
            'details': str(e)
        }
        results['summary']['failed'] += 1
    
    # Check RPC connection
    results['summary']['total_checks'] += 1
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
        if w3.is_connected():
            chain_id = w3.eth.chain_id
            block_number = w3.eth.block_number
            results['checks']['rpc'] = {
                'status': 'ok',
                'message': 'Connected',
                'details': f'Chain ID: {chain_id}, Block: {block_number}'
            }
            results['summary']['passed'] += 1
        else:
            results['healthy'] = False
            results['checks']['rpc'] = {
                'status': 'error',
                'message': 'Not connected',
                'details': 'Unable to establish connection'
            }
            results['summary']['failed'] += 1
    except Exception as e:
        results['healthy'] = False
        results['checks']['rpc'] = {
            'status': 'error',
            'message': 'Connection failed',
            'details': str(e)
        }
        results['summary']['failed'] += 1
    
    # Check wallet balance
    results['summary']['total_checks'] += 1
    try:
        balance = await get_my_balance_async(ENV.PROXY_WALLET)
        wallet_short = f"{ENV.PROXY_WALLET[:6]}...{ENV.PROXY_WALLET[-4:]}"
        
        if balance < 10:
            results['checks']['balance'] = {
                'status': 'warning',
                'message': f'${balance:.2f} USDC',
                'details': f'Wallet: {wallet_short} - Low balance warning'
            }
            results['summary']['warnings'] += 1
        else:
            results['checks']['balance'] = {
                'status': 'ok',
                'message': f'${balance:.2f} USDC',
                'details': f'Wallet: {wallet_short}'
            }
            results['summary']['passed'] += 1
    except Exception as e:
        results['healthy'] = False
        results['checks']['balance'] = {
            'status': 'error',
            'message': 'Balance check failed',
            'details': str(e)
        }
        results['summary']['failed'] += 1
    
    # Check CLOB endpoints
    results['summary']['total_checks'] += 1
    try:
        clob_http = ENV.CLOB_HTTP_URL
        clob_ws = ENV.CLOB_WS_URL
        if clob_http and clob_ws:
            results['checks']['clob'] = {
                'status': 'ok',
                'message': 'Configured',
                'details': f'HTTP: {clob_http[:30]}..., WS: {clob_ws[:30]}...'
            }
            results['summary']['passed'] += 1
        else:
            results['checks']['clob'] = {
                'status': 'warning',
                'message': 'Partially configured',
                'details': 'Some CLOB endpoints missing'
            }
            results['summary']['warnings'] += 1
    except Exception as e:
        results['checks']['clob'] = {
            'status': 'error',
            'message': 'Configuration error',
            'details': str(e)
        }
        results['summary']['failed'] += 1
    
    # Check trader addresses
    results['summary']['total_checks'] += 1
    try:
        if hasattr(ENV, 'USER_ADDRESSES') and ENV.USER_ADDRESSES:
            if isinstance(ENV.USER_ADDRESSES, list):
                trader_count = len(ENV.USER_ADDRESSES)
            else:
                trader_count = len([a for a in ENV.USER_ADDRESSES.split(',') if a.strip()])
            
            if trader_count > 0:
                results['checks']['traders'] = {
                    'status': 'ok',
                    'message': f'{trader_count} trader(s) configured',
                    'details': 'Traders loaded successfully'
                }
                results['summary']['passed'] += 1
            else:
                results['checks']['traders'] = {
                    'status': 'warning',
                    'message': 'No traders configured',
                    'details': 'USER_ADDRESSES is empty'
                }
                results['summary']['warnings'] += 1
        else:
            results['checks']['traders'] = {
                'status': 'warning',
                'message': 'Not configured',
                'details': 'USER_ADDRESSES not set'
            }
            results['summary']['warnings'] += 1
    except Exception as e:
        results['checks']['traders'] = {
            'status': 'error',
            'message': 'Configuration error',
            'details': str(e)
        }
        results['summary']['failed'] += 1
    
    # Trading strategy (informational - from COPY_STRATEGY_CONFIG)
    try:
        cfg = ENV.COPY_STRATEGY_CONFIG
        strategy_name = getattr(cfg.strategy, 'name', str(cfg.strategy))
        copy_size = cfg.copy_size
        if strategy_name == 'PERCENTAGE':
            copy_display = f'{copy_size}%'
        elif strategy_name == 'FIXED':
            copy_display = f'${copy_size:.2f}'
        else:
            copy_display = f'{copy_size}%'  # ADAPTIVE base
        multiplier = getattr(cfg, 'trade_multiplier', None) or 1.0
        tiered = bool(getattr(cfg, 'tiered_multipliers', None))
        results['strategy'] = {
            'name': strategy_name,
            'copy_display': copy_display,
            'multiplier': multiplier,
            'tiered_multipliers': tiered,
        }
    except Exception:
        results['strategy'] = None
    
    # Risk limits (informational)
    try:
        cfg = ENV.COPY_STRATEGY_CONFIG
        results['risk_limits'] = {
            'max_order_usd': getattr(cfg, 'max_order_size_usd', 100.0),
            'min_order_usd': getattr(cfg, 'min_order_size_usd', 1.0),
            'max_position_usd': getattr(cfg, 'max_position_size_usd'),
            'max_daily_volume_usd': getattr(cfg, 'max_daily_volume_usd'),
        }
    except Exception:
        results['risk_limits'] = None
    
    return results


def display_system_status(results: Dict[str, Any]) -> None:
    """Display system status results with professional formatting"""
    print()
    print(f'{Fore.CYAN}{Style.BRIGHT}{"=" * 80}{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}  SYSTEM STATUS REPORT{Style.RESET_ALL}')
    print(f'{Fore.CYAN}{Style.BRIGHT}{"=" * 80}{Style.RESET_ALL}')
    print()
    
    # Display checks in a structured format
    check_order = ['mongodb', 'rpc', 'balance', 'clob', 'traders']
    
    for check_name in check_order:
        if check_name not in results['checks']:
            continue
        
        check_result = results['checks'][check_name]
        status = check_result['status']
        message = check_result['message']
        details = check_result.get('details', '')
        
        # Format check name
        check_display = check_name.upper().replace('_', ' ')
        
        # Status indicator
        if status == 'ok':
            status_indicator = f'{Fore.GREEN}{Style.BRIGHT}✓{Style.RESET_ALL}'
            status_text = f'{Fore.GREEN}OPERATIONAL{Style.RESET_ALL}'
        elif status == 'warning':
            status_indicator = f'{Fore.YELLOW}{Style.BRIGHT}⚠{Style.RESET_ALL}'
            status_text = f'{Fore.YELLOW}WARNING{Style.RESET_ALL}'
        else:
            status_indicator = f'{Fore.RED}{Style.BRIGHT}✗{Style.RESET_ALL}'
            status_text = f'{Fore.RED}FAILED{Style.RESET_ALL}'
        
        # Print check result
        print(f'  {status_indicator} {Fore.CYAN}{check_display:<15}{Style.RESET_ALL} {status_text:<12} {message}')
        if details:
            print(f'    {Fore.YELLOW}→{Style.RESET_ALL} {Fore.YELLOW}{details}{Style.RESET_ALL}')
    
    print()
    print(f'{Fore.CYAN}{Style.BRIGHT}{"-" * 80}{Style.RESET_ALL}')
    
    # Trading strategy
    strat = results.get('strategy')
    if strat:
        print(f'  {Fore.CYAN}Trading strategy (bot uses now):{Style.RESET_ALL}')
        name = strat.get('name', 'PERCENTAGE')
        copy_display = strat.get('copy_display', '10%')
        mult = strat.get('multiplier', 1.0)
        tiered = strat.get('tiered_multipliers', False)
        line = f'Strategy: {name}  |  Copy size: {copy_display}  |  Multiplier: {mult}x'
        if tiered:
            line += '  (tiered)'
        print(f'    {line}')
        print()
    
    # Risk limits
    limits = results.get('risk_limits')
    if limits:
        print(f'  {Fore.CYAN}Risk limits:{Style.RESET_ALL}')
        mx = limits.get('max_order_usd', 100.0)
        mn = limits.get('min_order_usd', 1.0)
        print(f'    Max order: ${mx:.2f}  |  Min order: ${mn:.2f}')
        mp = limits.get('max_position_usd')
        md = limits.get('max_daily_volume_usd')
        if mp is not None or md is not None:
            extras = []
            if mp is not None:
                extras.append(f'Max position: ${mp:.2f}')
            if md is not None:
                extras.append(f'Max daily volume: ${md:.2f}')
            print(f'    {Style.DIM}{"  |  ".join(extras)}{Style.RESET_ALL}')
        print()
    
    print(f'{Fore.CYAN}{Style.BRIGHT}{"-" * 80}{Style.RESET_ALL}')
    
    # Summary
    summary = results['summary']
    total = summary['total_checks']
    passed = summary['passed']
    failed = summary['failed']
    warnings = summary['warnings']
    
    print(f'  {Fore.CYAN}Summary:{Style.RESET_ALL}')
    print(f'    Total Checks:  {total}')
    print(f'    {Fore.GREEN}Passed:        {passed}{Style.RESET_ALL}')
    if warnings > 0:
        print(f'    {Fore.YELLOW}Warnings:      {warnings}{Style.RESET_ALL}')
    if failed > 0:
        print(f'    {Fore.RED}Failed:        {failed}{Style.RESET_ALL}')
    
    print()
    
    # Overall status
    if results['healthy']:
        print(f'  {Fore.GREEN}{Style.BRIGHT}✓ SYSTEM STATUS: HEALTHY{Style.RESET_ALL}')
        print(f'  {Fore.GREEN}All critical systems operational{Style.RESET_ALL}')
    else:
        print(f'  {Fore.RED}{Style.BRIGHT}✗ SYSTEM STATUS: UNHEALTHY{Style.RESET_ALL}')
        print(f'  {Fore.RED}Some critical systems require attention{Style.RESET_ALL}')
    
    print()
    print(f'{Fore.CYAN}{Style.BRIGHT}{"=" * 80}{Style.RESET_ALL}')
    print()


async def run_system_status_check():
    """Run system status check as a standalone script"""
    import asyncio
    from ..config.db import connect_db
    
    try:
        print(f'{Fore.CYAN}{Style.BRIGHT}Initializing system status check...{Style.RESET_ALL}')
        print()
        
        # Connect to database first
        try:
            await connect_db()
        except Exception as db_error:
            print(f'{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Could not connect to database: {db_error}')
            print(f'{Fore.YELLOW}[INFO]{Style.RESET_ALL} Continuing with other checks...')
            print()
        
        # Run system status check
        results = await check_system_status()
        display_system_status(results)
        
        # Exit with appropriate code
        sys.exit(0 if results['healthy'] else 1)
    except Exception as e:
        print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} System status check failed: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    import asyncio
    asyncio.run(run_system_status_check())

