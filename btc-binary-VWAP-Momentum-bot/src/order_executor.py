#!/usr/bin/env python3
"""
Order Executor

Executes FAK (Fill-And-Kill) orders with retry logic.

Features:
- FAK orders for immediate fills
- Configurable retry attempts
- Price tracking to avoid overpaying
- Contract counting to prevent overbuying
- WebSocket fill monitoring
- Detailed logging for analysis
"""

import asyncio
import logging
import math
import time
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds, OrderType
from py_clob_client.order_builder.constants import BUY

logger = logging.getLogger("btc_live.executor")

# Separate logger for detailed order tracking
order_logger = logging.getLogger("btc_live.orders")
order_logger.setLevel(logging.DEBUG)

# Polymarket minimums
MIN_ORDER_USD = 1.0
MIN_CONTRACTS = 5


@dataclass
class OrderResult:
    """Result of an order execution attempt."""
    success: bool
    order_id: str = ""
    contracts_filled: int = 0
    avg_price: float = 0.0
    total_cost: float = 0.0
    attempts: int = 0
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    was_timeout: bool = False  # True если был сетевой таймаут (status unknown)


@dataclass
class ExecutionConfig:
    """Configuration for order execution."""
    bet_amount_usd: float = 10.0
    price_offset: float = 0.01
    max_retries: int = 5
    retry_delay_ms: int = 300
    fill_timeout_ms: int = 2000
    min_contracts: int = 5
    min_order_usd: float = 1.0
    max_entry_price: float = 0.91


class OrderExecutor:
    """
    Executes orders with retry logic.
    
    Flow:
    1. Get best BID price
    2. Place FAK order at BID + offset
    3. Wait for fill via WebSocket
    4. If partial/unfilled, retry with updated price
    5. Track total contracts to prevent overbuying
    """
    
    def __init__(
        self,
        private_key: str,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        clob_host: str = "https://clob.polymarket.com",
        chain_id: int = 137,
        signature_type: int = 0,
        funder_address: Optional[str] = None,
        user_ws: Optional[Any] = None,  # UserWebSocket for fill tracking
        simulation_mode: bool = False,
    ):
        self.private_key = private_key
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.clob_host = clob_host
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder_address = funder_address
        self.user_ws = user_ws
        self.simulation_mode = simulation_mode

        # Initialize client
        self._client: Optional[ClobClient] = None
        self._initialized = False
        
        # Stats
        self.orders_placed = 0
        self.orders_filled = 0
        self.total_contracts = 0
        self.total_spent = 0.0
    
    async def initialize(self) -> bool:
        """Initialize the CLOB client."""
        try:
            logger.info("Initializing CLOB client...")
            order_logger.info("=" * 60)
            order_logger.info("CLOB CLIENT INITIALIZATION")
            order_logger.info(f"  Host: {self.clob_host}")
            order_logger.info(f"  Chain ID: {self.chain_id}")
            order_logger.info(f"  Signature Type: {self.signature_type}")
            order_logger.info(f"  Funder Address: {self.funder_address}")
            order_logger.info(f"  API Key: {self.api_key[:8]}...")
            
            self._client = ClobClient(
                host=self.clob_host,
                key=self.private_key,
                chain_id=self.chain_id,
                signature_type=self.signature_type,
                funder=self.funder_address
            )
            
            # Set API credentials
            api_creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase
            )
            self._client.set_api_creds(api_creds)
            
            self._initialized = True
            logger.info("CLOB client initialized")
            order_logger.info("CLOB CLIENT INITIALIZED SUCCESSFULLY")
            order_logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"CLOB client init error: {e}")
            order_logger.error(f"CLOB CLIENT INIT FAILED: {e}")
            return False
    
    def _calculate_contracts(self, amount_usd: float, price: float) -> int:
        """
        Calculate number of contracts for given amount.
        
        Args:
            amount_usd: Amount in USD to spend
            price: Price per contract
        
        Returns:
            Number of contracts (minimum MIN_CONTRACTS)
        """
        if price <= 0:
            return MIN_CONTRACTS
        
        contracts = int(amount_usd / price)
        return max(contracts, MIN_CONTRACTS)
    
    def _validate_order_size(self, contracts: int, price: float) -> Tuple[int, bool]:
        """
        Validate and adjust order size to meet minimums.
        
        Args:
            contracts: Desired number of contracts
            price: Price per contract
        
        Returns:
            Tuple of (adjusted_contracts, is_valid)
        """
        order_value = contracts * price
        
        # Must be at least MIN_CONTRACTS
        if contracts < MIN_CONTRACTS:
            contracts = MIN_CONTRACTS
        
        # Must be at least MIN_ORDER_USD
        if order_value < MIN_ORDER_USD:
            contracts = math.ceil(MIN_ORDER_USD / price)
        
        return contracts, True

    def _simulate_fill(
        self,
        config: ExecutionConfig,
        websocket_price: float,
    ) -> OrderResult:
        """
        Instant hypothetical fill at limit (WS ask + offset), same sizing rules as live.
        """
        initial_price = websocket_price
        order_price = initial_price + config.price_offset
        if order_price > config.max_entry_price:
            order_logger.warning(
                f"SIMULATION: price {order_price:.4f} > max_entry {config.max_entry_price:.4f}"
            )
            return OrderResult(success=False, error="Price exceeded max entry")

        contracts_needed = self._calculate_contracts(config.bet_amount_usd, initial_price)
        order_size, _ = self._validate_order_size(contracts_needed, order_price)
        total_cost = order_size * order_price
        oid = f"SIM-{uuid.uuid4().hex[:12]}"
        order_logger.info("=" * 60)
        order_logger.info("SIMULATION ENTRY (no CLOB order sent)")
        order_logger.info(f"  Hypothetical fill: {order_size} @ {order_price:.4f}  cost ${total_cost:.2f}")
        order_logger.info(f"  Order ID: {oid}")
        order_logger.info("=" * 60)
        logger.info(f"Simulation fill: {order_size} contracts @ {order_price:.4f}")
        return OrderResult(
            success=True,
            order_id=oid,
            contracts_filled=order_size,
            avg_price=order_price,
            total_cost=total_cost,
            attempts=1,
            error="",
        )

    async def get_best_bid(self, token_id: str) -> Optional[float]:
        """
        Get best BID price for token.
        
        Args:
            token_id: Token to get price for
        
        Returns:
            Best bid price or None
        """
        if not self._client:
            order_logger.warning("get_best_bid: Client not initialized")
            return None
        
        start_time = time.time()
        try:
            # Use CLOB API to get orderbook
            book = await asyncio.to_thread(
                self._client.get_order_book,
                token_id
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            # Handle OrderBookSummary object from py-clob-client
            bids = None
            
            # Try object attribute access first
            if hasattr(book, 'bids'):
                bids = book.bids
            # Try dict-like access
            elif isinstance(book, dict):
                bids = book.get("bids", [])
            
            # Convert bids to list if needed
            if bids is None:
                bids = []
            
            if bids:
                # Handle OrderSummary objects or dicts
                first_bid = bids[0]
                if hasattr(first_bid, 'price'):
                    best_bid = float(first_bid.price)
                elif isinstance(first_bid, dict):
                    best_bid = float(first_bid.get("price", 0))
                else:
                    # Try direct conversion
                    best_bid = float(first_bid)
                
                order_logger.debug(
                    f"ORDERBOOK: token={token_id[:20]}... | "
                    f"best_bid={best_bid:.4f} | bids={len(bids)} | "
                    f"latency={elapsed:.0f}ms"
                )
                return best_bid
            
            order_logger.warning(f"ORDERBOOK: No bids for token={token_id[:20]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error getting best bid: {e}")
            order_logger.error(f"ORDERBOOK ERROR: {e} | book_type={type(book).__name__}")
            return None
    
    async def get_best_ask(self, token_id: str) -> Optional[float]:
        """
        Get best ASK price for token.
        
        Args:
            token_id: Token to get price for
        
        Returns:
            Best ask price or None
        """
        if not self._client:
            order_logger.warning("get_best_ask: Client not initialized")
            return None
        
        start_time = time.time()
        try:
            # Use CLOB API to get orderbook
            book = await asyncio.to_thread(
                self._client.get_order_book,
                token_id
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            # Handle OrderBookSummary object from py-clob-client
            asks = None
            
            # Try object attribute access first
            if hasattr(book, 'asks'):
                asks = book.asks
            # Try dict-like access
            elif isinstance(book, dict):
                asks = book.get("asks", [])
            
            # Convert asks to list if needed
            if asks is None:
                asks = []
            
            if asks:
                # Handle OrderSummary objects or dicts
                first_ask = asks[0]
                if hasattr(first_ask, 'price'):
                    best_ask = float(first_ask.price)
                elif isinstance(first_ask, dict):
                    best_ask = float(first_ask.get("price", 0))
                else:
                    # Try direct conversion
                    best_ask = float(first_ask)
                
                order_logger.debug(
                    f"ORDERBOOK ASK: token={token_id[:20]}... | "
                    f"best_ask={best_ask:.4f} | asks={len(asks)} | "
                    f"latency={elapsed:.0f}ms"
                )
                return best_ask
            
            order_logger.warning(f"ORDERBOOK: No asks for token={token_id[:20]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error getting best ask: {e}")
            order_logger.error(f"ORDERBOOK ASK ERROR: {e} | book_type={type(book).__name__}")
            return None
    
    async def place_fak_order(
        self,
        token_id: str,
        price: float,
        size: int
    ) -> Tuple[bool, str, Dict]:
        """
        Place a FAK (Fill-And-Kill) order.
        
        Args:
            token_id: Token to buy
            price: Order price
            size: Number of contracts
        
        Returns:
            Tuple of (success, order_id, response)
        """
        if not self._client:
            order_logger.error("PLACE_ORDER: Client not initialized")
            return False, "", {"error": "Client not initialized"}
        
        order_value = size * price
        order_logger.info("-" * 50)
        order_logger.info(f"PLACING ORDER")
        order_logger.info(f"  Token: {token_id[:30]}...")
        order_logger.info(f"  Side: BUY")
        order_logger.info(f"  Price: {price:.4f}")
        order_logger.info(f"  Size: {size} contracts")
        order_logger.info(f"  Value: ${order_value:.2f}")
        order_logger.info(f"  Type: FAK (Fill-And-Kill)")
        
        start_time = time.time()
        
        try:
            # Create order
            sign_start = time.time()
            signed_order = await asyncio.to_thread(
                self._client.create_order,
                OrderArgs(
                    price=price,
                    size=size,
                    side=BUY,
                    token_id=token_id
                )
            )
            sign_elapsed = (time.time() - sign_start) * 1000
            order_logger.debug(f"  Order signed in {sign_elapsed:.0f}ms")
            
            # Post FAK order (Fill-And-Kill: fill what you can, cancel rest)
            post_start = time.time()
            response = await asyncio.to_thread(
                self._client.post_order,
                signed_order,
                OrderType.FAK
            )
            post_elapsed = (time.time() - post_start) * 1000
            total_elapsed = (time.time() - start_time) * 1000
            
            # Handle response
            if isinstance(response, dict):
                success = response.get("success", False)
                order_id = response.get("orderID", "")
                status = response.get("status", "")
                error_msg = response.get("errorMsg", "")
                taking_amount = response.get("takingAmount", "")
                making_amount = response.get("makingAmount", "")
            else:
                success = getattr(response, 'success', False)
                order_id = getattr(response, 'orderID', "")
                status = getattr(response, 'status', "")
                error_msg = getattr(response, 'errorMsg', "")
                taking_amount = getattr(response, 'takingAmount', "")
                making_amount = getattr(response, 'makingAmount', "")
            
            self.orders_placed += 1
            
            order_logger.info(f"ORDER RESPONSE:")
            order_logger.info(f"  Success: {success}")
            order_logger.info(f"  Order ID: {order_id[:40] if order_id else 'N/A'}...")
            order_logger.info(f"  Status: {status}")
            if taking_amount:
                order_logger.info(f"  Taking Amount: {taking_amount}")
            if making_amount:
                order_logger.info(f"  Making Amount: {making_amount}")
            if error_msg:
                order_logger.warning(f"  Error: {error_msg}")
            order_logger.info(f"  Latency: sign={sign_elapsed:.0f}ms, post={post_elapsed:.0f}ms, total={total_elapsed:.0f}ms")
            order_logger.info("-" * 50)
            
            logger.info(f"Order placed: {success}, ID: {order_id[:20] if order_id else 'N/A'}...")
            
            return success, order_id, response if isinstance(response, dict) else {"success": success, "orderID": order_id, "status": status}
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"Order placement error: {e}")
            order_logger.error(f"ORDER FAILED: {e}")
            order_logger.error(f"  Elapsed: {elapsed:.0f}ms")
            order_logger.info("-" * 50)
            return False, "", {"error": str(e)}
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self._client:
            return False
        
        try:
            await asyncio.to_thread(
                self._client.cancel,
                order_id
            )
            logger.info(f"Order cancelled: {order_id[:20]}...")
            order_logger.info(f"  ✅ Cancelled order: {order_id[:30]}...")
            return True
        except Exception as e:
            # Ордер мог уже исполниться или не существует - это нормально
            logger.debug(f"Cancel order note: {e}")
            order_logger.debug(f"  Cancel note: {e}")
            return False
    
    async def cancel_orders(self, order_ids: List[str]) -> Dict[str, bool]:
        """
        Cancel multiple orders.
        Returns dict of order_id -> cancelled (True/False)
        """
        if not self._client or not order_ids:
            return {}
        
        results = {}
        order_logger.info(f"  Cancelling {len(order_ids)} previous order(s)...")
        
        try:
            # Используем batch cancel если доступен
            resp = await asyncio.to_thread(
                self._client.cancel_orders,
                order_ids
            )
            
            # Парсим ответ
            cancelled = resp.get('canceled', []) if isinstance(resp, dict) else []
            not_cancelled = resp.get('not_canceled', {}) if isinstance(resp, dict) else {}
            
            for oid in order_ids:
                if oid in cancelled:
                    results[oid] = True
                    order_logger.info(f"    ✅ Cancelled: {oid[:25]}...")
                else:
                    results[oid] = False
                    reason = not_cancelled.get(oid, "unknown/already filled")
                    order_logger.info(f"    ⚠️ Not cancelled: {oid[:25]}... ({reason})")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch cancel error: {e}")
            order_logger.warning(f"  Batch cancel failed: {e}, trying individual cancels...")
            
            # Fallback: отменяем по одному
            for oid in order_ids:
                results[oid] = await self.cancel_order(oid)
            
            return results
    
    async def get_order_fills(self, order_id: str) -> int:
        """
        Check how many contracts were filled for an order.
        Returns number of contracts filled (0 if not filled or error).
        """
        if not self._client:
            return 0
        
        try:
            # Пробуем получить ордер через API
            order = await asyncio.to_thread(
                self._client.get_order,
                order_id
            )
            
            if order:
                size_matched = getattr(order, 'size_matched', None) or order.get('size_matched', 0)
                filled = int(float(size_matched)) if size_matched else 0
                order_logger.info(f"    Order {order_id[:20]}... filled: {filled} contracts")
                return filled
                
        except Exception as e:
            logger.debug(f"Get order fills error: {e}")
            order_logger.debug(f"    Could not get fills for {order_id[:20]}...: {e}")
        
        return 0
    
    async def wait_for_fill(
        self,
        order_id: str,
        timeout_ms: int = 2000
    ) -> Tuple[int, float]:
        """
        Wait for order fill via WebSocket.
        
        Args:
            order_id: Order to wait for
            timeout_ms: Timeout in milliseconds
        
        Returns:
            Tuple of (contracts_filled, avg_price)
        """
        if self.user_ws:
            try:
                order = await self.user_ws.wait_for_fill(
                    order_id,
                    timeout=timeout_ms / 1000
                )
                
                if order:
                    filled = int(order.size_matched)
                    price = order.price
                    return filled, price
                    
            except Exception as e:
                logger.error(f"Wait for fill error: {e}")
        
        # Fallback - assume order didn't fill
        return 0, 0.0
    
    async def execute_entry(
        self,
        token_id: str,
        config: ExecutionConfig,
        websocket_price: Optional[float] = None
    ) -> OrderResult:
        """
        Execute entry order with retry logic.
        
        Args:
            token_id: Token to buy
            config: Execution configuration
            websocket_price: Current price from WebSocket (ASK for buying)
        
        Returns:
            OrderResult with execution details
        """
        if self.simulation_mode:
            if not websocket_price:
                return OrderResult(success=False, error="Could not get price")
            return self._simulate_fill(config, websocket_price)

        entry_start = time.time()
        
        order_logger.info("=" * 60)
        order_logger.info("ENTRY EXECUTION STARTED")
        order_logger.info(f"  Timestamp: {datetime.now().isoformat()}")
        order_logger.info(f"  Token: {token_id[:40]}...")
        order_logger.info(f"  Budget: ${config.bet_amount_usd}")
        order_logger.info(f"  Price Offset: {config.price_offset}")
        order_logger.info(f"  Max Retries: {config.max_retries}")
        order_logger.info(f"  Max Entry Price: {config.max_entry_price}")
        order_logger.info(f"  WebSocket Price: {websocket_price}")
        
        if not self._initialized:
            order_logger.warning("  Client not initialized, initializing...")
            if not await self.initialize():
                order_logger.error("ENTRY FAILED: Could not initialize client")
                return OrderResult(success=False, error="Failed to initialize")
        
        # Calculate contracts needed - use WebSocket price
        initial_price = websocket_price
        if not initial_price:
            order_logger.error("ENTRY FAILED: Could not get initial price")
            return OrderResult(success=False, error="Could not get price")
        
        contracts_needed = self._calculate_contracts(config.bet_amount_usd, initial_price)
        contracts_bought = 0
        total_cost = 0.0
        attempt = 0
        last_error = ""
        fills_log = []
        
        order_logger.info(f"  Initial Price: {initial_price:.4f}")
        order_logger.info(f"  Contracts Needed: {contracts_needed}")
        order_logger.info(f"  Estimated Cost: ${contracts_needed * initial_price:.2f}")
        order_logger.info("-" * 40)
        
        logger.info(
            f"Starting entry: need {contracts_needed} contracts, "
            f"budget ${config.bet_amount_usd}"
        )
        
        # Calculate order price once
        order_price = initial_price + config.price_offset
        
        # Check max price limit
        if order_price > config.max_entry_price:
            order_logger.warning(
                f"  PRICE LIMIT: {order_price:.4f} > max {config.max_entry_price:.4f}"
            )
            return OrderResult(success=False, error="Price exceeded max entry")
        
        order_logger.info(f"  Order Price: {order_price:.4f} (price + {config.price_offset})")
        
        # Список всех размещённых order_id для отслеживания через WebSocket
        placed_order_ids = []
        
        while contracts_bought < contracts_needed and attempt < config.max_retries:
            attempt += 1
            attempt_start = time.time()
            
            order_logger.info(f"ATTEMPT {attempt}/{config.max_retries}")
            
            # Рассчитываем ОСТАВШЕЕСЯ количество контрактов
            # (FAK ордера сразу возвращают takingAmount, так что contracts_bought уже актуален)
            remaining = contracts_needed - contracts_bought
            
            # Если уже купили достаточно - выходим
            if remaining <= 0:
                order_logger.info(f"  ✅ Already filled {contracts_bought}/{contracts_needed} - no retry needed")
                break
            
            order_size, _ = self._validate_order_size(remaining, order_price)
            
            order_logger.info(f"  Contracts bought so far: {contracts_bought}")
            order_logger.info(f"  Remaining needed: {remaining}")
            order_logger.info(f"  Order size: {order_size}")
            
            logger.info(f"Attempt {attempt}: placing {order_size} contracts @ {order_price:.2f}")
            
            # Place order
            success, order_id, response = await self.place_fak_order(
                token_id,
                order_price,
                order_size
            )
            
            # Запоминаем order_id для отслеживания
            if order_id:
                placed_order_ids.append(order_id)
                order_logger.info(f"  Order ID: {order_id[:30]}...")
            
            # ============================================================
            # ЖЕЛЕЗНОЕ ПРАВИЛО: Если не знаем исполнился ли ордер - STOP
            # Retry ТОЛЬКО если точно знаем результат из API ответа
            # ============================================================
            
            if not success:
                error_msg = response.get("errorMsg", "") or response.get("error", "")
                
                # ============================================================
                # ЖЕЛЕЗНОЕ ПРАВИЛО v2: Определяем ТОЧНО был ли таймаут
                # status_code=None в ошибке = сетевой таймаут = НЕ ЗНАЕМ РЕЗУЛЬТАТ
                # status_code=400/etc = API ответил чётко = ордер НЕ исполнился
                # ============================================================
                
                is_network_timeout = False
                
                # Проверяем status_code в ошибке PolyApiException
                if "status_code=None" in error_msg:
                    is_network_timeout = True
                elif "Request exception" in error_msg and "status_code" not in error_msg:
                    is_network_timeout = True
                elif "timed out" in error_msg.lower() and "status_code=4" not in error_msg:
                    is_network_timeout = True
                
                if is_network_timeout:
                    last_error = f"🛑 STOP: Network timeout (status_code=None) - order status UNKNOWN. No retry."
                    order_logger.error(f"  {last_error}")
                    logger.error(last_error)
                    
                    entry_elapsed = (time.time() - entry_start) * 1000
                    order_logger.info(f"  Total execution time: {entry_elapsed:.0f}ms")
                    order_logger.info("=" * 60)
                    order_logger.info("ENTRY EXECUTION COMPLETE (TIMEOUT)")
                    order_logger.info(f"  Success: False")
                    order_logger.info(f"  Contracts Filled: {contracts_bought}/{contracts_needed}")
                    order_logger.info(f"  Error: {last_error}")
                    order_logger.info(f"  Fills: {json.dumps(fills_log)}")
                    order_logger.info("=" * 60)
                    
                    # Возвращаем с флагом таймаута - main.py должен заблокировать повторные попытки!
                    return OrderResult(
                        success=False,
                        contracts_filled=contracts_bought,
                        avg_price=total_cost / contracts_bought if contracts_bought > 0 else 0,
                        total_cost=total_cost,
                        attempts=attempt,
                        error=last_error,
                        was_timeout=True  # КРИТИЧНО: флаг таймаута для main.py
                    )
                
                # Чёткий отказ API (status_code=400, etc) = ордер НЕ исполнился = можно retry
                last_error = error_msg or "Order failed"
                order_logger.warning(f"  Order rejected (API): {last_error}")
                await asyncio.sleep(config.retry_delay_ms / 1000)
                continue
            
            # API ответил успешно - знаем точный результат
            status = response.get("status", "")
            
            if status == "matched":
                # Ордер исполнен - берём количество из ответа
                api_taking = response.get("takingAmount", "")
                filled = int(float(api_taking)) if api_taking else 0
                
                if filled > order_size:
                    order_logger.warning(f"  ⚠️ OVERFILL: got {filled}, ordered {order_size}")
                    logger.warning(f"Entry overfill: {filled} > {order_size}")
                
                fill_price = order_price
                
                contracts_bought += filled
                total_cost += filled * fill_price
                self.orders_filled += 1
                self.total_contracts += filled
                self.total_spent += filled * fill_price
                
                fills_log.append({
                    "attempt": attempt,
                    "filled": filled,
                    "price": fill_price,
                    "order_id": order_id[:20] if order_id else "N/A",
                    "source": "api_response",
                    "timestamp": datetime.now().isoformat()
                })
                
                order_logger.info(f"  ✅ FILLED: {filled} contracts @ {fill_price:.4f}")
                order_logger.info(f"  Progress: {contracts_bought}/{contracts_needed} ({contracts_bought/contracts_needed*100:.1f}%)")
                
                logger.info(f"Filled: {filled} @ {fill_price:.2f} (total: {contracts_bought}/{contracts_needed})")
            else:
                order_logger.info(f"  Status: {status} (not matched)")
                logger.info("No fill at this price level")
            
            attempt_elapsed = (time.time() - attempt_start) * 1000
            order_logger.info(f"  Attempt time: {attempt_elapsed:.0f}ms")
            
            # Короткая пауза перед следующей попыткой
            if contracts_bought < contracts_needed:
                await asyncio.sleep(config.retry_delay_ms / 1000)
        
        entry_elapsed = (time.time() - entry_start) * 1000
        order_logger.info(f"  Total execution time: {entry_elapsed:.0f}ms")
        
        # Calculate result
        avg_price = total_cost / contracts_bought if contracts_bought > 0 else 0
        entry_elapsed = (time.time() - entry_start) * 1000
        
        result = OrderResult(
            success=contracts_bought > 0,
            contracts_filled=contracts_bought,
            avg_price=avg_price,
            total_cost=total_cost,
            attempts=attempt,
            error=last_error if contracts_bought == 0 else ""
        )
        
        order_logger.info("=" * 60)
        order_logger.info("ENTRY EXECUTION COMPLETE")
        order_logger.info(f"  Success: {result.success}")
        order_logger.info(f"  Contracts Filled: {result.contracts_filled}/{contracts_needed}")
        order_logger.info(f"  Average Price: {result.avg_price:.4f}")
        order_logger.info(f"  Total Cost: ${result.total_cost:.2f}")
        order_logger.info(f"  Attempts: {result.attempts}")
        order_logger.info(f"  Total Time: {entry_elapsed:.0f}ms")
        if result.error:
            order_logger.info(f"  Error: {result.error}")
        order_logger.info(f"  Fills: {json.dumps(fills_log)}")
        order_logger.info("=" * 60)
        
        logger.info(
            f"Entry complete: {result.contracts_filled} contracts, "
            f"${result.total_cost:.2f}, {result.attempts} attempts"
        )
        
        return result
    
    def get_stats(self) -> Dict:
        """Get executor statistics."""
        return {
            "orders_placed": self.orders_placed,
            "orders_filled": self.orders_filled,
            "total_contracts": self.total_contracts,
            "total_spent": self.total_spent,
            "avg_price": self.total_spent / self.total_contracts if self.total_contracts > 0 else 0
        }
