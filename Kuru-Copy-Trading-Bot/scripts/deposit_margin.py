#!/usr/bin/env python3
"""Deposit tokens to Kuru margin account."""

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

# Token to deposit ("USDC" or "AUSD")
TOKEN = "USDC"

# Amount to deposit
AMOUNT = "5.0"

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
    """Deposit tokens to margin account."""
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

    print(f"💸 Depositing {amount} {TOKEN} to margin account")
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

    # Load ABIs
    abi_dir = Path(__file__).parent.parent / "src" / "kuru_copytr_bot" / "config" / "abis"

    with open(abi_dir / "MarginAccount.json") as f:
        margin_abi = json.load(f)

    # Standard ERC20 ABI (for approve and balanceOf)
    erc20_abi = [
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        },
    ]

    # Create contract instances
    margin_contract = w3.eth.contract(
        address=Web3.to_checksum_address(MARGIN_ACCOUNT_ADDRESS), abi=margin_abi
    )
    token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=erc20_abi)

    # Check wallet balance
    print("🔍 Checking wallet balance...")
    wallet_balance_wei = token_contract.functions.balanceOf(wallet_address).call()
    wallet_balance = Decimal(wallet_balance_wei) / Decimal(10**6)  # 6 decimals
    print(f"   Wallet balance: {wallet_balance} {TOKEN}")

    amount_wei = int(amount * Decimal(10**6))  # 6 decimals for USDC/AUSD

    if wallet_balance < amount:
        print(f"❌ Error: Insufficient balance. Need {amount}, have {wallet_balance}")
        return

    # Step 1: Approve tokens for margin account
    print(f"\n📝 Step 1/2: Approving {amount} {TOKEN}...")
    try:
        approve_tx = token_contract.functions.approve(
            Web3.to_checksum_address(MARGIN_ACCOUNT_ADDRESS), amount_wei
        ).build_transaction(
            {
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address, "pending"),
                "gas": 100000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            }
        )

        signed_approve = account.sign_transaction(approve_tx)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        print(f"   ✅ Approval tx sent: {approve_hash.hex()}")

        # Wait for approval
        print("   ⏳ Waiting for confirmation...")
        approve_receipt = w3.eth.wait_for_transaction_receipt(approve_hash, timeout=120)
        if approve_receipt["status"] != 1:
            print("   ❌ Approval transaction failed!")
            return
        print("   ✅ Approval confirmed")

    except Exception as e:
        print(f"   ❌ Error during approval: {e}")
        return

    # Step 2: Call deposit function on margin account
    print(f"\n💰 Step 2/2: Depositing {amount} {TOKEN} to margin account...")
    try:
        # Call deposit(user, token, amount) on margin account
        deposit_tx = margin_contract.functions.deposit(
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(token_address),
            amount_wei,
        ).build_transaction(
            {
                "from": wallet_address,
                "nonce": w3.eth.get_transaction_count(wallet_address, "pending"),
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
                "chainId": w3.eth.chain_id,
            }
        )

        signed_tx = account.sign_transaction(deposit_tx)
        deposit_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"   ✅ Deposit tx sent: {deposit_hash.hex()}")

        # Wait for confirmation
        print("   ⏳ Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(deposit_hash, timeout=120)
        if receipt["status"] != 1:
            print("   ❌ Deposit transaction failed!")
            return
        print("   ✅ Deposit confirmed")

    except Exception as e:
        print(f"   ❌ Error during deposit: {e}")
        return

    # Verify deposit by checking margin balance
    print("\n✅ Step 3/3: Verifying margin balance...")
    try:
        new_balance_wei = margin_contract.functions.getBalance(
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(token_address),
        ).call()
        new_balance = Decimal(new_balance_wei) / Decimal(10**6)
        print(f"   New margin balance: {new_balance} {TOKEN}")
        print(f"\n🎉 Success! Deposited {amount} {TOKEN} to margin account")

    except Exception as e:
        print(f"   ⚠️  Could not verify balance: {e}")
        print(f"   But deposit transaction succeeded: {deposit_hash.hex()}")


if __name__ == "__main__":
    main()
