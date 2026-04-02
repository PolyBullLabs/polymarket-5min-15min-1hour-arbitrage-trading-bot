#!/usr/bin/env python3
"""
Set token allowance for Polymarket trading (ERC1155 approval)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
from web3 import Web3
from eth_account import Account
from src.config.env import ENV
from colorama import init, Fore, Style

init(autoreset=True)

# Polymarket Exchange address where tokens need to be approved
POLYMARKET_EXCHANGE = '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E'

# CTF (Conditional Token Framework) contract address on Polygon
CTF_CONTRACT = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'

# ERC1155 approve for all ABI
CTF_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]


async def set_token_allowance():
    """Set token allowance for Polymarket trading"""
    print(f'{Fore.CYAN}Setting Token Allowance for Polymarket Trading{Style.RESET_ALL}')
    print('=' * 55 + '\n')
    
    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
    
    if not w3.is_connected():
        print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to connect to RPC endpoint')
        sys.exit(1)
    
    # Create wallet from private key
    account = Account.from_key(ENV.PRIVATE_KEY)
    wallet_address = Web3.to_checksum_address(ENV.PROXY_WALLET)
    exchange_address = Web3.to_checksum_address(POLYMARKET_EXCHANGE)
    ctf_address = Web3.to_checksum_address(CTF_CONTRACT)
    
    print(f'Wallet: {ENV.PROXY_WALLET}')
    print(f'CTF Contract: {CTF_CONTRACT}')
    print(f'Polymarket Exchange: {POLYMARKET_EXCHANGE}\n')
    
    try:
        # Create CTF contract instance
        ctf_contract = w3.eth.contract(address=ctf_address, abi=CTF_ABI)
        
        # Check current approval status
        print(f'{Fore.CYAN}[INFO]{Style.RESET_ALL} Checking current approval status...')
        is_approved = ctf_contract.functions.isApprovedForAll(wallet_address, exchange_address).call()
        
        if is_approved:
            print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Tokens are already approved for trading!')
            print('You can now sell your positions.\n')
            return
        
        print(f'{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Tokens are NOT approved for trading')
        print('Setting approval for all tokens...\n')
        
        # Get current gas price
        fee_data = w3.eth.fee_history(1, 'latest')
        if fee_data and fee_data.get('baseFeePerGas'):
            base_fee = fee_data['baseFeePerGas'][0]
            gas_price = int(base_fee * 1.5)  # 50% buffer
        else:
            gas_price = w3.to_wei(50, 'gwei')
        
        print(f'Gas Price: {w3.from_wei(gas_price, "gwei"):.2f} Gwei')
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(wallet_address)
        approve_txn = ctf_contract.functions.setApprovalForAll(exchange_address, True).build_transaction({
            'from': wallet_address,
            'gas': 100000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 137  # Polygon
        })
        
        # Sign transaction
        signed_txn = account.sign_transaction(approve_txn)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(f'Transaction sent: {tx_hash.hex()}')
        print('Waiting for confirmation...\n')
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt.status == 1:
            print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Success! Tokens are now approved for trading!')
            print(f'Transaction: https://polygonscan.com/tx/{tx_hash.hex()}\n')
            
            # Verify approval
            new_approval_status = ctf_contract.functions.isApprovedForAll(wallet_address, exchange_address).call()
            if new_approval_status:
                print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Verification: Approval confirmed on-chain')
                print('You can now run: python -m src.scripts.position.manual_sell\n')
        else:
            print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Transaction failed!')
        
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Done!')
        
    except Exception as error:
        print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        if 'insufficient funds' in str(error).lower():
            print(f'\n{Fore.YELLOW}[WARNING]{Style.RESET_ALL} You need MATIC for gas fees on Polygon!')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(set_token_allowance())

