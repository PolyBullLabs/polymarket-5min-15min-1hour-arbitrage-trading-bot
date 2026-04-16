#!/usr/bin/env python3
"""
Async Auto-Redeemer

Runs every 3 minutes in background, checks for redeemable positions
and automatically redeems them.

Fully async - does not block main event loop.
"""

import os
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

import aiohttp
from web3 import Web3
from eth_account import Account

logger = logging.getLogger("btc_live.redeemer")

# Dedicated thread pool for web3 operations to avoid blocking main thread pool
_WEB3_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="web3_redeemer")

# Contract addresses
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

DATA_API = "https://data-api.polymarket.com"

CTF_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"}
        ],
        "name": "payoutDenominator",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "indexSets", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]''')

NEG_RISK_ABI = json.loads('''[
    {
        "inputs": [
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]''')

GNOSIS_SAFE_ABI = json.loads('''[
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "signatures", "type": "bytes"}
        ],
        "name": "execTransaction",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "nonce",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "_nonce", "type": "uint256"}
        ],
        "name": "getTransactionHash",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    }
]''')


class AsyncAutoRedeemer:
    """
    Async auto-redeemer that runs in background every N minutes.
    
    Features:
    - Fully async (aiohttp for API, asyncio.to_thread for web3)
    - File lock to prevent concurrent redemptions
    - Supports both EOA and Proxy (Gnosis Safe) wallets
    - Telegram notifications on successful redeem
    """
    
    def __init__(
        self,
        private_key: str,
        rpc_url: str,
        funder_address: Optional[str] = None,
        signature_type: int = 0,
        interval_seconds: int = 180,  # 3 minutes
        telegram_notifier: Optional[Any] = None
    ):
        self.private_key = private_key
        self.rpc_url = rpc_url
        self.funder_address = funder_address
        self.signature_type = signature_type
        self.interval = interval_seconds
        self.telegram = telegram_notifier
        
        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Add POA middleware for Polygon
        from web3.middleware import ExtraDataToPOAMiddleware
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        # Account
        self.account = Account.from_key(private_key)
        self.signer_address = self.account.address
        
        # Wallet to check for positions
        if signature_type in [1, 2] and funder_address:
            self.wallet_address = funder_address
        else:
            self.wallet_address = self.signer_address
        
        # Contracts
        self.ctf = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_ADDRESS),
            abi=CTF_ABI
        )
        
        # Stats
        self.total_redeemed = 0
        self.total_value = 0.0
        self._running = False
        self._lock_fd = None
        
        # Semaphore to limit concurrent web3 operations (prevents thread pool saturation)
        self._redeem_semaphore = asyncio.Semaphore(1)  # Only 1 redemption at a time
    
    async def _fetch_positions(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Fetch all positions from Polymarket Data API (async)."""
        active = []
        pending = []
        redeemable = []
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{DATA_API}/positions"
                params = {
                    "user": self.wallet_address,
                    "limit": 500,
                    "sizeThreshold": 0.01
                }
                
                async with session.get(url, params=params, timeout=30) as resp:
                    if resp.status != 200:
                        logger.error(f"Data API returned {resp.status}")
                        return active, pending, redeemable
                    
                    positions = await resp.json()
            
            if not positions:
                return active, pending, redeemable
            
            # Group by conditionId
            positions_by_condition = {}
            for pos in positions:
                condition_id = pos.get("conditionId")
                if not condition_id:
                    continue
                
                if condition_id not in positions_by_condition:
                    positions_by_condition[condition_id] = {
                        "slug": pos.get("slug", "unknown"),
                        "title": pos.get("title", "Unknown Market"),
                        "condition_id": condition_id,
                        "neg_risk": pos.get("negativeRisk", False),
                        "end_date": pos.get("endDate"),
                        "redeemable": pos.get("redeemable", False),
                        "outcomes": {}
                    }
                
                outcome = pos.get("outcome", "")
                positions_by_condition[condition_id]["outcomes"][outcome] = {
                    "asset": pos.get("asset"),
                    "size": int(float(pos.get("size", 0)) * 1e6),
                    "cur_price": pos.get("curPrice", 0),
                }
            
            # Categorize
            import time
            now = int(time.time())
            
            for condition_id, pos_data in positions_by_condition.items():
                outcomes = pos_data["outcomes"]
                
                up_data = outcomes.get("Up") or outcomes.get("YES") or outcomes.get("Higher")
                down_data = outcomes.get("Down") or outcomes.get("NO") or outcomes.get("Lower")
                
                if not up_data and not down_data:
                    outcome_list = list(outcomes.values())
                    up_data = outcome_list[0] if len(outcome_list) > 0 else None
                    down_data = outcome_list[1] if len(outcome_list) > 1 else None
                
                up_balance = up_data.get("size", 0) if up_data else 0
                down_balance = down_data.get("size", 0) if down_data else 0
                
                if up_balance == 0 and down_balance == 0:
                    continue
                
                position_data = {
                    "slug": pos_data["slug"],
                    "title": pos_data["title"],
                    "condition_id": condition_id,
                    "up_token_id": up_data.get("asset") if up_data else None,
                    "down_token_id": down_data.get("asset") if down_data else None,
                    "up_balance": up_balance,
                    "down_balance": down_balance,
                    "neg_risk": pos_data["neg_risk"],
                }
                
                end_date = pos_data.get("end_date")
                is_closed = False
                if end_date:
                    try:
                        end_timestamp = datetime.fromisoformat(
                            end_date.replace('Z', '+00:00')
                        ).timestamp()
                        is_closed = now >= end_timestamp
                    except:
                        pass
                
                if pos_data["redeemable"]:
                    redeemable.append(position_data)
                elif is_closed:
                    pending.append(position_data)
                else:
                    active.append(position_data)
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
        
        return active, pending, redeemable
    
    def _check_oracle_resolution(self, condition_id: str) -> bool:
        """Check if oracle has resolved (sync, runs in thread)."""
        try:
            condition_bytes = Web3.to_bytes(hexstr=condition_id)
            payout_denom = self.ctf.functions.payoutDenominator(condition_bytes).call()
            return payout_denom > 0
        except Exception as e:
            logger.error(f"Oracle check error: {e}")
            return False
    
    def _redeem_position_sync(self, position: Dict) -> bool:
        """Redeem a single position (sync, runs in thread)."""
        import fcntl
        import time
        
        condition_id = position["condition_id"]
        up_balance = position["up_balance"]
        down_balance = position["down_balance"]
        is_neg_risk = position.get("neg_risk", False)
        
        logger.info(f"Redeeming: {position['slug']}")
        
        # Check oracle first
        if not self._check_oracle_resolution(condition_id):
            logger.warning(f"Skipping {position['slug']} - oracle not resolved")
            return False
        
        # File lock
        lock_file = "/tmp/btc_live_redeem.lock"
        try:
            self._lock_fd = open(lock_file, 'w')
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            logger.warning("Another redeem in progress, skipping")
            return False
        
        try:
            use_proxy = self.signature_type in [1, 2] and self.funder_address
            
            time.sleep(0.5)
            
            if use_proxy:
                # Gnosis Safe proxy wallet
                return self._redeem_via_safe(condition_id, up_balance, down_balance, is_neg_risk)
            else:
                # Direct EOA
                return self._redeem_direct(condition_id, up_balance, down_balance, is_neg_risk)
                
        except Exception as e:
            logger.error(f"Redeem error: {e}")
            return False
        finally:
            if self._lock_fd:
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    self._lock_fd.close()
                except:
                    pass
                self._lock_fd = None
    
    def _redeem_direct(
        self, 
        condition_id: str, 
        up_balance: int, 
        down_balance: int, 
        is_neg_risk: bool
    ) -> bool:
        """Direct EOA redeem."""
        import time
        
        nonce = self.w3.eth.get_transaction_count(self.signer_address)
        time.sleep(0.3)
        gas_price = self.w3.eth.gas_price
        
        if is_neg_risk:
            adapter = self.w3.eth.contract(
                address=Web3.to_checksum_address(NEG_RISK_ADAPTER),
                abi=NEG_RISK_ABI
            )
            tx = adapter.functions.redeemPositions(
                Web3.to_bytes(hexstr=condition_id),
                [up_balance, down_balance]
            ).build_transaction({
                "chainId": 137,
                "from": self.signer_address,
                "nonce": nonce,
                "gas": 500000,
                "gasPrice": int(gas_price * 1.2),
            })
        else:
            tx = self.ctf.functions.redeemPositions(
                Web3.to_checksum_address(USDC_ADDRESS),
                bytes(32),
                Web3.to_bytes(hexstr=condition_id),
                [1, 2]
            ).build_transaction({
                "chainId": 137,
                "from": self.signer_address,
                "nonce": nonce,
                "gas": 500000,
                "gasPrice": int(gas_price * 1.2),
            })
        
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        logger.info(f"TX sent: {tx_hash.hex()}")
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.get("status") == 1:
            logger.info(f"Redeem successful! Gas: {receipt.get('gasUsed')}")
            return True
        else:
            logger.error(f"TX reverted: {tx_hash.hex()}")
            return False
    
    def _redeem_via_safe(
        self,
        condition_id: str,
        up_balance: int,
        down_balance: int,
        is_neg_risk: bool
    ) -> bool:
        """Redeem via Gnosis Safe proxy wallet."""
        import time
        
        safe_address = Web3.to_checksum_address(self.funder_address)
        safe = self.w3.eth.contract(address=safe_address, abi=GNOSIS_SAFE_ABI)
        
        # Build inner redeem call
        if is_neg_risk:
            adapter = self.w3.eth.contract(
                address=Web3.to_checksum_address(NEG_RISK_ADAPTER),
                abi=NEG_RISK_ABI
            )
            temp_tx = adapter.functions.redeemPositions(
                Web3.to_bytes(hexstr=condition_id),
                [up_balance, down_balance]
            ).build_transaction({"from": safe_address})
            redeem_data = temp_tx['data']
            target_contract = NEG_RISK_ADAPTER
        else:
            temp_tx = self.ctf.functions.redeemPositions(
                Web3.to_checksum_address(USDC_ADDRESS),
                bytes(32),
                Web3.to_bytes(hexstr=condition_id),
                [1, 2]
            ).build_transaction({"from": safe_address})
            redeem_data = temp_tx['data']
            target_contract = CTF_ADDRESS
        
        time.sleep(0.5)
        eoa_nonce = self.w3.eth.get_transaction_count(self.signer_address)
        time.sleep(0.3)
        gas_price = self.w3.eth.gas_price
        safe_nonce = safe.functions.nonce().call()
        
        # Safe TX params
        to = Web3.to_checksum_address(target_contract)
        value = 0
        data = redeem_data
        operation = 0
        safeTxGas = 0
        baseGas = 0
        gasPrice_safe = 0
        gasToken = "0x0000000000000000000000000000000000000000"
        refundReceiver = "0x0000000000000000000000000000000000000000"
        
        # Get TX hash to sign
        tx_hash_to_sign = safe.functions.getTransactionHash(
            to, value, data, operation,
            safeTxGas, baseGas, gasPrice_safe,
            gasToken, refundReceiver, safe_nonce
        ).call()
        
        # Sign
        signed_msg = self.account.unsafe_sign_hash(tx_hash_to_sign)
        r = signed_msg.r.to_bytes(32, byteorder='big')
        s = signed_msg.s.to_bytes(32, byteorder='big')
        v = signed_msg.v
        signature = r + s + bytes([v])
        
        # Build execTransaction
        tx = safe.functions.execTransaction(
            to, value, data, operation,
            safeTxGas, baseGas, gasPrice_safe,
            gasToken, refundReceiver, signature
        ).build_transaction({
            "chainId": 137,
            "from": self.signer_address,
            "nonce": eoa_nonce,
            "gas": 1000000,
            "gasPrice": int(gas_price * 1.2),
        })
        
        time.sleep(0.5)
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        logger.info(f"Safe TX sent: {tx_hash.hex()}")
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.get("status") == 1:
            logger.info(f"Safe redeem successful! Gas: {receipt.get('gasUsed')}")
            return True
        else:
            logger.error(f"Safe TX reverted: {tx_hash.hex()}")
            return False
    
    async def redeem_all(self) -> Tuple[int, float]:
        """
        Check and redeem all redeemable positions.
        
        Returns:
            Tuple of (redeemed_count, total_value_usd)
        """
        logger.info("Starting auto-redeem check...")
        
        active, pending, redeemable = await self._fetch_positions()
        
        logger.info(f"Found: {len(active)} active, {len(pending)} pending, {len(redeemable)} redeemable")
        
        if not redeemable:
            return 0, 0.0
        
        redeemed_count = 0
        total_value = 0.0
        
        for position in redeemable:
            # Use semaphore to limit concurrent redemptions
            # Use dedicated thread pool to avoid blocking main pool
            async with self._redeem_semaphore:
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    _WEB3_EXECUTOR, 
                    self._redeem_position_sync, 
                    position
                )
            
            if success:
                redeemed_count += 1
                value = (position["up_balance"] + position["down_balance"]) / 1e6
                total_value += value
                
                self.total_redeemed += 1
                self.total_value += value
                
                # Telegram notification
                if self.telegram:
                    try:
                        await self.telegram.send_message(
                            f"💰 Redeemed: {position['slug']}\n"
                            f"Value: ${value:.2f} USDC"
                        )
                    except:
                        pass
            
            # Pause between redemptions
            await asyncio.sleep(2)
        
        logger.info(f"Redeemed {redeemed_count}/{len(redeemable)}, value: ${total_value:.2f}")
        
        return redeemed_count, total_value
    
    async def run_loop(self):
        """
        Main loop - runs every N seconds.
        Fully async, never blocks.
        """
        self._running = True
        logger.info(f"Auto-redeemer started (interval: {self.interval}s)")
        
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                
                redeemed, value = await self.redeem_all()
                
                if redeemed > 0:
                    logger.info(f"Auto-redeemed {redeemed} positions, ${value:.2f}")
                    
            except asyncio.CancelledError:
                logger.info("Auto-redeemer cancelled")
                break
            except Exception as e:
                logger.error(f"Auto-redeem loop error: {e}")
                # Continue running despite errors
                await asyncio.sleep(10)
        
        logger.info("Auto-redeemer stopped")
    
    def stop(self):
        """Stop the redeemer loop."""
        self._running = False
    
    @staticmethod
    def shutdown_executor():
        """Shutdown the dedicated thread pool on application exit."""
        global _WEB3_EXECUTOR
        if _WEB3_EXECUTOR:
            _WEB3_EXECUTOR.shutdown(wait=False)
            logger.info("Web3 executor shut down")


async def create_auto_redeemer(config: Dict) -> AsyncAutoRedeemer:
    """
    Factory function to create redeemer from config.
    
    Args:
        config: Dict with keys: private_key, rpc_url, funder_address, signature_type
    """
    return AsyncAutoRedeemer(
        private_key=config.get("private_key"),
        rpc_url=config.get("rpc_url", "https://polygon-rpc.com"),
        funder_address=config.get("funder_address"),
        signature_type=config.get("signature_type", 0),
        interval_seconds=config.get("redeem_interval", 180),
        telegram_notifier=config.get("telegram_notifier")
    )
