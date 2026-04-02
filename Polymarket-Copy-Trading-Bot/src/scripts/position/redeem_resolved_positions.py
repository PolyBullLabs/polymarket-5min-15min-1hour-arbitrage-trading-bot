#!/usr/bin/env python3
"""
Redeem Resolved Positions (Production Ready)
Features:
- Gnosis Safe Integration
- Auto-Bitmasking for Index Sets
- Batch Listing before execution
- Force mode support
"""
import sys
import asyncio
import argparse
import time
from pathlib import Path
from collections import defaultdict
from hexbytes import HexBytes

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web3 import Web3
from eth_account import Account
from colorama import init, Fore, Style
from src.config.env import ENV

init(autoreset=True)

# --- IMPORTS ---
try:
    from safe_eth.safe import Safe
    from safe_eth.eth import EthereumClient
except ImportError:
    try:
        from gnosis.safe import Safe
        from gnosis.eth import EthereumClient
    except ImportError:
        print(f"{Fore.RED}[CRITICAL] Library 'safe-eth-py' missing.{Style.RESET_ALL}")
        sys.exit(1)

# --- CONFIGURATION ---
CTF_CONTRACT = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
# Use ENV variable if available, otherwise default
USDC_COLLATERAL = getattr(ENV, 'USDC_CONTRACT_ADDRESS', '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
HASH_ZERO = '0x0000000000000000000000000000000000000000000000000000000000000000'

CTF_ABI = [
    {"constant": False, "inputs": [{"name": "collateralToken", "type": "address"}, {"name": "parentCollectionId", "type": "bytes32"}, {"name": "conditionId", "type": "bytes32"}, {"name": "indexSets", "type": "uint256[]"}], "name": "redeemPositions", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]

async def redeem_resolved_positions():
    # 1. Parse Arguments
    parser = argparse.ArgumentParser(description='Redeem resolved positions')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args, _ = parser.parse_known_args()

    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Redeeming Resolved Positions")
    print('=' * 60 + '\n')
    
    # 2. Connection Setup
    w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
    if not w3.is_connected():
        print(f"{Fore.RED}[ERROR] Failed to connect to RPC{Style.RESET_ALL}")
        return

    account = Account.from_key(ENV.PRIVATE_KEY)
    signer = account.address
    proxy = Web3.to_checksum_address(ENV.PROXY_WALLET)
    usdc_addr = Web3.to_checksum_address(USDC_COLLATERAL)

    print(f"  Signer: {signer}")
    print(f"  Safe:   {proxy}")
    
    # Initialize Safe Helper
    try:
        eth_client = EthereumClient(ENV.RPC_URL)
        safe = Safe(proxy, eth_client)
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Safe initialization failed: {e}{Style.RESET_ALL}")
        return

    # 3. Fetch Data
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching positions...")
    
    try:
        url = f'https://data-api.polymarket.com/positions?user={proxy}'
        from src.utils.fetch_data import fetch_data_async
        positions = await fetch_data_async(url)
        
        if not isinstance(positions, list): return
        
        # Filter: Redeemable AND Value > $0.01 (to avoid dust)
        redeemable = [p for p in positions if p.get('redeemable', False) and float(p.get('currentValue', 0) or 0) > 0.01]
        
        if not redeemable:
            print(f"{Fore.GREEN}[SUCCESS] No redeemable positions found.{Style.RESET_ALL}")
            return
        
        # Group by Condition ID for processing
        groups = defaultdict(list)
        for p in redeemable:
            if p.get('conditionId'):
                groups[p['conditionId']].append(p)

        # 4. Display List (Confirmation Step)
        total_val = sum(float(p.get('currentValue', 0) or 0) for p in redeemable)
        print(f"\n{Fore.YELLOW}Positions to Redeem:{Style.RESET_ALL}")
        print(f"{'Title':<60} | {'Tokens':<10} | {'Value ($)':<10}")
        print("-" * 90)
        
        for p in redeemable:
            title = p.get('title', 'Unknown')[:58]
            size = float(p.get('size', 0) or 0)
            val = float(p.get('currentValue', 0) or 0)
            print(f"{title:<60} | {size:<10.2f} | {val:<10.2f}")
        
        print("-" * 90)
        print(f"{Fore.CYAN}Total Estimated Value: {Fore.GREEN}${total_val:.2f}{Style.RESET_ALL}\n")

        # Prompt
        if not args.force:
            if input(f"{Fore.YELLOW}Proceed with redemption? (y/n): {Style.RESET_ALL}").lower() != 'y': 
                print("Operation cancelled.")
                return

        # 5. Execution Loop
        ctf = w3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)
        success_count = 0
        
        print(f"\n{Fore.CYAN}[INFO]{Style.RESET_ALL} Starting execution...")

        for cond, pos_list in groups.items():
            # Get details for logging
            title = pos_list[0].get('title', 'Unknown Title')
            val = sum(float(p.get('currentValue', 0) or 0) for p in pos_list)
            
            # Bitmask Logic: 
            # Polymarket uses Index Sets (Bitmasks). 
            # 0 -> 1 (binary 01), 1 -> 2 (binary 10).
            # We send [1, 2] to cover both binary outcomes. The contract picks the winner.
            target_index_sets = [1, 2]

            print(f"Redeeming: {Fore.WHITE}{title[:40]}...{Style.RESET_ALL} (${val:.2f})")
            
            try:
                # A. Prepare Internal Payload (CTF Contract)
                cond_b = bytes.fromhex(cond[2:].ljust(64,'0')[:64] if cond.startswith('0x') else cond.ljust(64,'0')[:64])
                
                # Use build_transaction to generate 'data' (Works across Web3 versions)
                dummy_tx = ctf.functions.redeemPositions(
                    usdc_addr, HASH_ZERO, cond_b, target_index_sets
                ).build_transaction({'from': signer, 'gas': 0, 'gasPrice': 0, 'nonce': 0, 'chainId': 137})
                
                call_data_hex = dummy_tx['data']
                
                # B. Build Gnosis Safe Transaction
                safe_tx = safe.build_multisig_tx(
                    to=CTF_CONTRACT,
                    value=0,
                    data=HexBytes(call_data_hex),
                    operation=0, # Call
                    safe_tx_gas=0,
                    base_gas=0,
                    gas_price=0,
                    gas_token="0x0000000000000000000000000000000000000000",
                    refund_receiver="0x0000000000000000000000000000000000000000"
                )
                
                # C. Sign Transaction (EOA)
                safe_tx.sign(account.key)
                
                # D. Execute Transaction
                # Calculate dynamic gas price
                fee = w3.eth.fee_history(1, 'latest')
                prio = int(fee['baseFeePerGas'][0] * 1.5) if fee.get('baseFeePerGas') else w3.to_wei(50, 'gwei')

                tx_hash, _ = safe_tx.execute(
                    tx_sender_private_key=account.key,
                    tx_gas=800000, # Safe gas limit
                    tx_gas_price=prio
                )
                
                print(f"  > Tx Sent: https://polygonscan.com/tx/{tx_hash.hex()}")
                
                # Wait for receipt
                rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if rcpt.status == 1:
                    print(f"  > {Fore.GREEN}[SUCCESS] Confirmed.{Style.RESET_ALL}\n")
                    success_count += 1
                else:
                    print(f"  > {Fore.RED}[FAILURE] Reverted on-chain.{Style.RESET_ALL}\n")
                
                # Small pause to allow nonce propagation on Polygon
                time.sleep(1)

            except Exception as e:
                print(f"  > {Fore.RED}[ERROR] {e}{Style.RESET_ALL}\n")

        print('='*60)
        print(f"Completed. Successfully Redeemed: {success_count}/{len(groups)}")

    except Exception as e:
        print(f"{Fore.RED}[CRITICAL ERROR] {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    asyncio.run(redeem_resolved_positions())
