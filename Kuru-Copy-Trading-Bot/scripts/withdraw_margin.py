#!/usr/bin/env python3
"""Withdraw tokens from Kuru margin account."""

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

# Token to withdraw ("USDC" or "AUSD")
TOKEN = "USDC"

# Amount to withdraw
AMOUNT = "10.0"

# Margin Account contract address
# Mainnet: 0x2A68ba1833cDf93fa9Da1EEbd7F46242aD8E90c5
# Testnet: 0xdDDaBd30785bA8b45e434a1f134BDf304d6125d9
MARGIN_ACCOUNT_ADDRESS = "0x2A68ba1833cDf93fa9Da1EEbd7F46242aD8E90c5"

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
    """Withdraw tokens from margin account."""
    if not RPC_URL:
        print("❌ Error: MONAD_RPC_URL not found in environment")
        return

    if not PRIVATE_KEY:
        print("❌ Error: WALLET_PRIVATE_KEY not found in environment")
        return

    if TOKEN not in TOKENS:
        print(f"❌ Error: Unknown token '{TOKEN}'. Must be one of: {list(TOKENS.keys())}")
        return

    token_address = TOKENS[TOKEN]
    amount = Decimal(AMOUNT)

    print(f"💸 Withdrawing {amount} {TOKEN} from margin account")
    print(f"📍 Margin Account: {MARGIN_ACCOUNT_ADDRESS}")
    print(f"🪙  Token: {token_address}\n")

    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f"❌ Error: Failed to connect to RPC: {RPC_URL}")
        return

    # Get wallet address from private key
    account = w3.eth.account.from_key(PRIVATE_KEY)
    wallet_address = account.address

    print(f"👤 Wallet: {wallet_address}\n")

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

    # Check margin balance
    print("🔍 Checking margin balance...")
    try:
        margin_balance_wei = margin_contract.functions.getBalance(
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(token_address),
        ).call()
        margin_balance = Decimal(margin_balance_wei) / Decimal(10**6)  # 6 decimals
        print(f"   Margin balance: {margin_balance} {TOKEN}")

        if margin_balance < amount:
            print(f"❌ Error: Insufficient margin balance. Need {amount}, have {margin_balance}")
            return

    except Exception as e:
        print(f"❌ Error checking balance: {e}")
        return

    amount_wei = int(amount * Decimal(10**6))  # 6 decimals for USDC/AUSD

    # Withdraw from margin account
    print(f"\n💰 Withdrawing {amount} {TOKEN} from margin...")
    try:
        # Build withdraw transaction: withdraw(amount, token)
        withdraw_tx = margin_contract.functions.withdraw(
            amount_wei, Web3.to_checksum_address(token_address)
        ).build_transaction(
            {
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address, "pending"),
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            }
        )

        signed_withdraw = account.sign_transaction(withdraw_tx)
        withdraw_hash = w3.eth.send_raw_transaction(signed_withdraw.raw_transaction)
        print(f"   ✅ Withdrawal tx sent: {withdraw_hash.hex()}")

        # Wait for withdrawal
        print("   ⏳ Waiting for confirmation...")
        withdraw_receipt = w3.eth.wait_for_transaction_receipt(withdraw_hash, timeout=120)
        if withdraw_receipt["status"] != 1:
            print("   ❌ Withdrawal transaction failed!")
            return
        print("   ✅ Withdrawal confirmed")

    except Exception as e:
        print(f"   ❌ Error during withdrawal: {e}")
        return

    # Verify new balance
    print("\n✅ Verifying new margin balance...")
    try:
        new_balance_wei = margin_contract.functions.getBalance(
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(token_address),
        ).call()
        new_balance = Decimal(new_balance_wei) / Decimal(10**6)
        print(f"   New margin balance: {new_balance} {TOKEN}")
        print(f"\n🎉 Success! Withdrew {amount} {TOKEN} from margin account")

    except Exception as e:
        print(f"   ⚠️  Could not verify balance: {e}")
        print(f"   But withdrawal transaction succeeded: {withdraw_hash.hex()}")


if __name__ == "__main__":
    main()
