#!/usr/bin/env python3
"""
Run comprehensive batch simulations

This script runs multiple simulations with different configurations
to find optimal trading parameters.
"""
import sys
import asyncio
import os
import importlib
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV

init(autoreset=True)

# Import the module (will be reloaded for each simulation)
import src.scripts.simulation.simulate_profitability as sim_module

# Default traders
DEFAULT_TRADERS = [
    '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
    '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
]

# Simulation presets
PRESETS = {
    'quick': {
        'history_days': 7,
        'max_trades': 500,
        'multipliers': [1.0, 2.0],
        'tag': 'quick',
    },
    'standard': {
        'history_days': 30,
        'max_trades': 2000,
        'multipliers': [0.5, 1.0, 2.0],
        'tag': 'std',
    },
    'full': {
        'history_days': 90,
        'max_trades': 5000,
        'multipliers': [0.5, 1.0, 2.0, 3.0],
        'tag': 'full',
    },
}


class SimulationConfig:
    """Configuration for a single simulation"""
    def __init__(
        self,
        trader_address: str,
        history_days: int,
        multiplier: float,
        min_order_size: float = 1.0,
        max_trades: Optional[int] = None,
        tag: Optional[str] = None
    ):
        self.trader_address = trader_address
        self.history_days = history_days
        self.multiplier = multiplier
        self.min_order_size = min_order_size
        self.max_trades = max_trades
        self.tag = tag or ''


async def run_simulation(config: SimulationConfig) -> Dict[str, Any]:
    """Run a single simulation with given configuration"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Starting simulation...")
    print(f"{Fore.YELLOW}  Trader: {config.trader_address[:10]}...")
    print(f"  Days: {config.history_days}, Multiplier: {config.multiplier}x, MinOrder: ${config.min_order_size}")
    print()
    
    # Set environment variables for the simulation
    original_env = {}
    env_vars = {
        'SIM_TRADER_ADDRESS': config.trader_address,
        'SIM_HISTORY_DAYS': str(config.history_days),
        'SIM_MIN_ORDER_USD': str(config.min_order_size),
        'TRADE_MULTIPLIER': str(config.multiplier),
    }
    
    if config.max_trades:
        env_vars['SIM_MAX_TRADES'] = str(config.max_trades)
    
    if config.tag:
        env_vars['SIM_RESULT_TAG'] = config.tag
    
    # Save original values and set new ones
    for key, value in env_vars.items():
        original_env[key] = os.getenv(key)
        os.environ[key] = value
    
    try:
        # Reload the module to pick up new environment variables
        importlib.reload(sim_module)
        
        # Run simulation using the reloaded module
        result = await sim_module.simulate_trader(config.trader_address)
        result['config'] = {
            'trader_address': config.trader_address,
            'history_days': config.history_days,
            'multiplier': config.multiplier,
            'min_order_size': config.min_order_size,
            'tag': config.tag,
        }
        
        print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Simulation completed")
        print()
        return result
    
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Simulation failed: {e}")
        print()
        return {
            'error': str(e),
            'config': {
                'trader_address': config.trader_address,
                'history_days': config.history_days,
                'multiplier': config.multiplier,
            }
        }
    
    finally:
        # Restore original environment variables
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def run_batch(configs: List[SimulationConfig]) -> List[Dict[str, Any]]:
    """Run a batch of simulations"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  BATCH SIMULATION RUNNER{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    print(f"{Fore.YELLOW}Total simulations to run: {len(configs)}")
    print()
    
    results = []
    
    for i, config in enumerate(configs, 1):
        print(f"{Style.BRIGHT}[{i}/{len(configs)}]{Style.RESET_ALL} Running simulation...")
        try:
            result = await run_simulation(config)
            results.append(result)
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Simulation {i} failed: {e}")
            print()
            results.append({'error': str(e), 'config': config.__dict__})
        
        # Small delay between simulations
        if i < len(configs):
            await asyncio.sleep(1)
    
    print('=' * 80)
    print(f"{Fore.GREEN}{Style.BRIGHT}  ALL SIMULATIONS COMPLETED{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    return results


def generate_configs(preset: str, traders: Optional[List[str]] = None) -> List[SimulationConfig]:
    """Generate simulation configurations from preset"""
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESETS.keys())}")
    
    preset_config = PRESETS[preset]
    trader_list = traders if traders and len(traders) > 0 else DEFAULT_TRADERS
    
    # Get default min order size from environment
    min_order_size = float(os.getenv('SIM_MIN_ORDER_USD', '1.0'))
    
    configs = []
    
    for trader in trader_list:
        for multiplier in preset_config['multipliers']:
            tag = f"{preset_config['tag']}_m{str(multiplier).replace('.', 'p')}"
            configs.append(SimulationConfig(
                trader_address=trader.lower(),
                history_days=preset_config['history_days'],
                multiplier=multiplier,
                min_order_size=min_order_size,
                max_trades=preset_config['max_trades'],
                tag=tag
            ))
    
    return configs


async def interactive_mode():
    """Interactive mode for selecting simulation parameters"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  INTERACTIVE SIMULATION SETUP{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    # Select preset
    print(f"{Fore.YELLOW}Select simulation preset:{Style.RESET_ALL}")
    print("  1. Quick (7 days, 2 multipliers, ~500 trades)")
    print("  2. Standard (30 days, 3 multipliers, ~2000 trades) [RECOMMENDED]")
    print("  3. Full (90 days, 4 multipliers, ~5000 trades)")
    print()
    
    preset_choice = input(f"{Fore.CYAN}Enter choice (1-3): {Style.RESET_ALL}").strip()
    preset_map = {
        '1': 'quick',
        '2': 'standard',
        '3': 'full',
    }
    preset = preset_map.get(preset_choice, 'standard')
    
    # Select traders
    print()
    print(f"{Fore.YELLOW}Trader addresses (leave empty for defaults):{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  Default: {', '.join([t[:10] + '...' for t in DEFAULT_TRADERS])}{Style.RESET_ALL}")
    print()
    
    traders_input = input(f"{Fore.CYAN}Enter addresses (comma-separated) or press Enter: {Style.RESET_ALL}").strip()
    
    traders = None
    if traders_input:
        traders = [t.strip().lower() for t in traders_input.split(',') if t.strip()]
        # Validate addresses
        for trader in traders:
            if not trader.startswith('0x') or len(trader) != 42:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Invalid address format: {trader}")
                return
    
    configs = generate_configs(preset, traders)
    await run_batch(configs)


async def run_simulations():
    """Main function to run simulations"""
    args = sys.argv[1:]
    
    if len(args) == 0:
        # Interactive mode
        await interactive_mode()
        return
    
    command = args[0].lower()
    
    if command == 'quick':
        configs = generate_configs('quick')
        await run_batch(configs)
    
    elif command in ['standard', 'std']:
        configs = generate_configs('standard')
        await run_batch(configs)
    
    elif command == 'full':
        configs = generate_configs('full')
        await run_batch(configs)
    
    elif command == 'custom':
        if len(args) < 2:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Trader address required for custom mode")
            print(f"{Fore.YELLOW}Usage: python -m src.scripts.simulation.run_simulations custom <trader_address> [days] [multiplier]{Style.RESET_ALL}")
            return
        
        trader = args[1].lower()
        days = int(args[2]) if len(args) > 2 else 30
        multiplier = float(args[3]) if len(args) > 3 else 1.0
        
        if not trader.startswith('0x') or len(trader) != 42:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Invalid Ethereum address format")
            return
        
        config = SimulationConfig(
            trader_address=trader,
            history_days=days,
            multiplier=multiplier,
            min_order_size=MIN_ORDER_SIZE,
            tag='custom'
        )
        
        await run_simulation(config)
    
    elif command in ['help', '--help', '-h']:
        print_help()
    
    else:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Unknown command: {command}")
        print()
        print_help()


def print_help():
    """Print usage help"""
    print(f"{Fore.CYAN}Simulation Runner - Usage{Style.RESET_ALL}")
    print()
    print("Interactive mode:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations{Style.RESET_ALL}")
    print()
    print("Preset modes:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations quick{Style.RESET_ALL}      # 7 days, 2 multipliers")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations standard{Style.RESET_ALL}   # 30 days, 3 multipliers (recommended)")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations full{Style.RESET_ALL}       # 90 days, 4 multipliers")
    print()
    print("Custom mode:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations custom <trader> [days] [multiplier]{Style.RESET_ALL}")
    print()
    print("Examples:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations custom 0x7c3d... 30 2.0{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations standard{Style.RESET_ALL}")
    print()


if __name__ == '__main__':
    try:
        asyncio.run(run_simulations())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
