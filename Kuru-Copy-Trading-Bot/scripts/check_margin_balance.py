#!/usr/bin/env python3
"""Check margin account balances for USDC and AUSD."""

import json
import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION - Edit these variables
# ============================================================================

# Margin Account contract address
# Mainnet: 0x2A68ba1833cDf93fa9Da1EEbd7F46242aD8E90c5
# Testnet: 0xdDDaBd30785bA8b45e434a1f134BDf304d6125d9
MARGIN_ACCOUNT_ADDRESS = "0x2A68ba1833cDf93fa9Da1EEbd7F46242aD8E90c5"

# Token addresses to check
# Token addresses (mainnet)
TOKENS = {
    "USDC": "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
    "AUSD": "0x00000000eFE302BEAA2b3e6e1b18d08D69a9012a",
}

# ============================================================================
# Environment variables (from .env file)
# ============================================================================
RPC_URL = os.getenv("MONAD_RPC_URL")
PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")

# ============================================================================
# Main Script
# ============================================================================


def main():
    """Check margin balances for all configured tokens."""
    if not RPC_URL:
        print("❌ Error: MONAD_RPC_URL not found in environment")
        return

    if not PRIVATE_KEY:
        print("❌ Error: WALLET_PRIVATE_KEY not found in environment")
        return

    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f"❌ Error: Failed to connect to RPC: {RPC_URL}")
        return

    # Get wallet address from private key
    account = w3.eth.account.from_key(PRIVATE_KEY)
    wallet_address = account.address

    print(f"🔍 Checking margin balances for: {wallet_address}")
    print(f"📍 Margin Account: {MARGIN_ACCOUNT_ADDRESS}\n")

    # Load MarginAccount ABI
    abi_path = (
        Path(__file__).parent.parent
        / "src"
        / "kuru_copytr_bot"
        / "config"
        / "abis"
        / "MarginAccount.json"
    )
    with open(abi_path) as f:
        margin_abi = json.load(f)

    # Create contract instance
    margin_contract = w3.eth.contract(
        address=Web3.to_checksum_address(MARGIN_ACCOUNT_ADDRESS), abi=margin_abi
    )

    # Check balance for each token
    print("=" * 60)
    for token_name, token_address in TOKENS.items():
        try:
            # Call getBalance(user, token)
            balance_wei = margin_contract.functions.getBalance(
                Web3.to_checksum_address(wallet_address),
                Web3.to_checksum_address(token_address),
            ).call()

            # Convert to human-readable (assuming 6 decimals for USDC/AUSD)
            decimals = 6
            balance = Decimal(balance_wei) / Decimal(10**decimals)

            print(f"💰 {token_name}: {balance:.2f}")
            print(f"   Address: {token_address}")
            print(f"   Raw: {balance_wei}")
            print("-" * 60)

        except Exception as e:
            print(f"❌ Error checking {token_name}: {e}")
            print("-" * 60)

    print("=" * 60)
    print("✅ Balance check complete")


if __name__ == "__main__":
    main()
