#!/usr/bin/env python3
"""
Sell large positions
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV

init(autoreset=True)


async def sell_large_positions():
    """
    Sell large positions
    
    This script identifies and sells positions above a certain value threshold.
    """
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Selling Large Positions")
    print()
    
    # Get threshold from user or use default
    threshold_input = input(f"Minimum position value to sell (default: $1000): ").strip()
    threshold = float(threshold_input) if threshold_input else 1000.0
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching positions...")
    
    try:
        wallet = ENV.PROXY_WALLET
        url = f'https://data-api.polymarket.com/positions?user={wallet}'
        
        from src.utils.fetch_data import fetch_data_async
        positions = await fetch_data_async(url)
        
        if not isinstance(positions, list):
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch positions")
            return
        
        # Filter large positions
        large_positions = [
            p for p in positions
            if p.get('currentValue', 0) >= threshold
        ]
        
        if not large_positions:
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} No positions found above ${threshold}")
            return
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Found {len(large_positions)} large positions:")
        for pos in large_positions:
            size = pos.get('size', 0)
            value = pos.get('currentValue', 0)
            price = pos.get('curPrice', 0)
            print(f"  - {pos.get('title', 'Unknown')[:50]}: {size:.4f} tokens @ ${price:.4f} = ${value:.2f}")
        
        print()
        
        # Ask for confirmation
        confirm = input(f"{Fore.YELLOW}Proceed with selling {len(large_positions)} position(s)? (y/n): {Style.RESET_ALL}").strip().lower()
        if confirm != 'y':
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Cancelled by user")
            return
        
        print()
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Initializing CLOB client...")
        
        # Create CLOB client
        from src.utils.create_clob_client import create_clob_client
        clob_client = await create_clob_client()
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Selling positions...\n")
        
        # Minimum order size in tokens
        MIN_ORDER_SIZE_TOKENS = 1.0
        
        total_sold = 0
        total_value = 0
        failed_sells = []
        
        for i, pos in enumerate(large_positions, 1):
            token_id = pos.get('asset') or pos.get('tokenId')
            title = pos.get('title', 'Unknown')
            position_size = pos.get('size', 0)
            current_value = pos.get('currentValue', 0)
            current_price = pos.get('curPrice', 0)
            
            if not token_id:
                print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Position {i}/{len(large_positions)}: No token ID found, skipping")
                print(f"  Title: {title[:50]}\n")
                failed_sells.append({'title': title, 'reason': 'No token ID'})
                continue
            
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Selling position {i}/{len(large_positions)}: {title[:50]}")
            print(f"  Token ID: {token_id}")
            print(f"  Position size: {position_size:.4f} tokens")
            print(f"  Current price: ${current_price:.4f}")
            print(f"  Current value: ${current_value:.2f}")
            
            try:
                # Get order book for this token
                order_book = await clob_client.get_order_book(token_id)
                
                if not order_book.get('bids') or len(order_book['bids']) == 0:
                    print(f"  {Fore.YELLOW}[WARNING]{Style.RESET_ALL} No bids available, skipping\n")
                    failed_sells.append({'title': title, 'reason': 'No bids'})
                    continue
                
                # Find best bid (highest price)
                best_bid = max(order_book['bids'], key=lambda x: float(x['price']))
                bid_price = float(best_bid['price'])
                bid_size = float(best_bid['size'])
                
                print(f"  Best bid: {bid_size:.4f} @ ${bid_price:.4f}")
                
                # Determine amount to sell (full position or what the market can take)
                sell_amount = min(position_size, bid_size)
                
                # Check minimum order size
                if sell_amount < MIN_ORDER_SIZE_TOKENS:
                    print(f"  {Fore.YELLOW}[WARNING]{Style.RESET_ALL} Amount {sell_amount:.4f} below minimum {MIN_ORDER_SIZE_TOKENS}, skipping\n")
                    failed_sells.append({'title': title, 'reason': f'Amount too small ({sell_amount:.4f})'})
                    continue
                
                # Create sell order
                order_args = {
                    'side': 'SELL',
                    'tokenID': token_id,
                    'amount': sell_amount,
                    'price': bid_price,
                }
                
                print(f"  Creating sell order: {sell_amount:.4f} tokens @ ${bid_price:.4f}")
                
                # Create and post order
                signed_order = await clob_client.create_market_order(order_args)
                response = await clob_client.post_order(signed_order, 'FOK')
                
                if response.get('success') is True:
                    print(f"  {Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Order executed successfully!")
                    estimated_value = sell_amount * bid_price
                    print(f"  Estimated value received: ${estimated_value:.2f}\n")
                    
                    total_sold += 1
                    total_value += estimated_value
                else:
                    error_msg = response.get('error') or response.get('errorMsg') or response.get('message') or 'Unknown error'
                    print(f"  {Fore.RED}[ERROR]{Style.RESET_ALL} Order failed: {error_msg}\n")
                    failed_sells.append({'title': title, 'reason': error_msg})
                
            except Exception as e:
                print(f"  {Fore.RED}[ERROR]{Style.RESET_ALL} Failed to sell position: {e}\n")
                failed_sells.append({'title': title, 'reason': str(e)})
                continue
        
        # Summary
        print('=' * 60)
        if total_sold > 0:
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Sales completed!")
            print(f"  Positions sold: {total_sold}/{len(large_positions)}")
            print(f"  Estimated total value received: ${total_value:.2f}")
        else:
            print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No positions were sold")
        
        if failed_sells:
            print(f"\n{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Failed to sell {len(failed_sells)} position(s):")
            for failed in failed_sells:
                print(f"  - {failed['title'][:50]}: {failed['reason']}")
        print('=' * 60 + '\n')
        
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to process positions: {e}")


if __name__ == '__main__':
    asyncio.run(sell_large_positions())

