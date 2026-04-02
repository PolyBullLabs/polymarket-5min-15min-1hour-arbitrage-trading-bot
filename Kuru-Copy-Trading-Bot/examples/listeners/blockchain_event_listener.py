#!/usr/bin/env python3
"""
Standalone Blockchain Event Listener - Listen to OrderBook Contract Events

This script connects directly to the blockchain RPC WebSocket and listens to
smart contract events using eth_subscribe. It prints raw event logs with
basic parsing to understand the data structure.

Events monitored:
- OrderCreated: New limit orders placed on-chain
- Trade: Orders filled (partially or fully) on-chain
- OrdersCanceled: Orders cancelled on-chain

Configuration:
- Uses MONAD_RPC_URL environment variable (or provide --rpc-ws-url)
- Uses MARKET_ADDRESS environment variable (or provide --market)

Usage:
    # Use environment variables from .env
    python examples/listeners/blockchain_event_listener.py

    # Override with command line arguments
    python examples/listeners/blockchain_event_listener.py \
        --market 0x... \
        --rpc-ws-url wss://...
"""

import asyncio
import contextlib
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

from web3 import Web3
from websockets import connect

DEFAULT_MARKET_ADDRESS = "0x122C0D8683Cab344163fB73E28E741754257e3Fa"
DEFAULT_RPC_URL = os.getenv("MONAD_RPC_URL")
DEFAULT_RPC_WS_URL = DEFAULT_RPC_URL.replace("https://", "wss://")
DEFAULT_ABI_PATH = "src/kuru_copytr_bot/config/abis/OrderBook.json"


class BlockchainEventListener:
    """Listen to blockchain contract events using eth_subscribe."""

    def __init__(
        self,
        rpc_ws_url: str,
        market_address: str,
        orderbook_abi_path: str,
    ):
        """Initialize the blockchain event listener.

        Args:
            rpc_ws_url: Blockchain RPC WebSocket URL (e.g., wss://monad-testnet.drpc.org)
            market_address: OrderBook contract address to monitor
            orderbook_abi_path: Path to OrderBook ABI JSON file
        """
        self.rpc_ws_url = rpc_ws_url
        self.market_address = market_address.lower()

        # Load ABI
        with open(orderbook_abi_path) as f:
            self.orderbook_abi = json.load(f)

        # WebSocket connection
        self.ws = None
        self.subscription_id = None
        self.running = False
        self.shutdown_event = asyncio.Event()

        # Web3 instance for event parsing (no provider needed)
        self.w3 = Web3()
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(market_address),
            abi=self.orderbook_abi,
        )

        # Compute event signature hashes from event ABIs
        self.event_signatures = {}
        for event_name in ["OrderCreated", "Trade", "OrdersCanceled"]:
            event = getattr(self.contract.events, event_name)
            event_abi = event._get_event_abi()
            # Build event signature string: EventName(type1,type2,...)
            input_types = ",".join([inp["type"] for inp in event_abi["inputs"]])
            event_signature = f"{event_abi['name']}({input_types})"
            # Compute keccak256 hash
            signature_hash = self.w3.keccak(text=event_signature).hex()
            # Remove 0x prefix for comparison
            if signature_hash.startswith("0x"):
                signature_hash = signature_hash[2:]
            self.event_signatures[event_name] = signature_hash

        # Statistics
        self.stats = {
            "orders_created": 0,
            "trades": 0,
            "orders_canceled": 0,
            "total_events": 0,
        }

    async def connect(self):
        """Connect to blockchain RPC and subscribe to contract logs."""
        print(f"Connecting to {self.rpc_ws_url}...")
        print(f"Market address: {self.market_address}")
        print("-" * 80)

        try:
            # Connect to WebSocket RPC
            self.ws = await connect(self.rpc_ws_url)

            # Subscribe to logs from the OrderBook contract
            subscribe_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": self.market_address,
                        # No topics filter - get all events from this contract
                    },
                ],
            }

            await self.ws.send(json.dumps(subscribe_request))
            response = await self.ws.recv()
            response_data = json.loads(response)

            if "result" in response_data:
                self.subscription_id = response_data["result"]
                print(f"✓ Subscription created: {self.subscription_id}")
                print("✓ Connected to blockchain RPC")
                print("-" * 80)
            else:
                error = response_data.get("error", "Unknown error")
                raise Exception(f"Failed to subscribe: {error}")

            # Start listening loop
            self.running = True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            raise

    async def disconnect(self):
        """Disconnect from blockchain RPC."""
        self.running = False

        if self.ws and self.subscription_id:
            try:
                # Unsubscribe
                unsubscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [self.subscription_id],
                }
                await self.ws.send(json.dumps(unsubscribe_request))
                await self.ws.close()
                print("\n✓ Disconnected from blockchain RPC")
            except Exception as e:
                print(f"⚠ Unsubscribe error: {e}")

    async def _listen_loop(self):
        """Listen for incoming log events."""
        try:
            while self.running and self.ws:
                message = await self.ws.recv()
                await self._process_message(message)
        except Exception as e:
            if self.running:
                print(f"✗ Listen error: {e}")

    async def _process_message(self, message: str) -> None:
        """Process incoming log message.

        Args:
            message: JSON-RPC notification message
        """
        try:
            data = json.loads(message)

            # Check if this is a subscription notification
            if "params" not in data or "result" not in data["params"]:
                return

            log_entry = data["params"]["result"]

            # Parse the log entry
            await self._parse_log(log_entry)

        except Exception as e:
            print(f"✗ Message parse error: {e}")

    async def _parse_log(self, log_entry: dict[str, Any]) -> None:
        """Parse log entry and print event details.

        Args:
            log_entry: Raw log entry from eth_subscribe
        """
        try:
            # Get the event signature (first topic)
            if not log_entry.get("topics") or len(log_entry["topics"]) == 0:
                return

            # Normalize event signature - remove 0x prefix if present for comparison
            event_signature = log_entry["topics"][0]
            if isinstance(event_signature, str) and event_signature.startswith("0x"):
                event_signature = event_signature[2:]

            # Identify which event this is
            if event_signature == self.event_signatures["OrderCreated"]:
                await self._handle_order_created(log_entry)
            elif event_signature == self.event_signatures["Trade"]:
                await self._handle_trade(log_entry)
            elif event_signature == self.event_signatures["OrdersCanceled"]:
                await self._handle_orders_canceled(log_entry)
            else:
                print(f"\n❓ Unknown event signature: {event_signature}")

        except Exception as e:
            print(f"✗ Log parse error: {e}")
            print(f"   Log entry: {json.dumps(log_entry, indent=6)}")

    async def _handle_order_created(self, log_entry: dict[str, Any]) -> None:
        """Handle OrderCreated event.

        OrderCreated ABI fields:
        - orderId (uint40)
        - owner (address)
        - size (uint96) - 18 decimals
        - price (uint32) - 6 decimals
        - isBuy (bool)

        Args:
            log_entry: Raw log entry
        """
        try:
            self.stats["orders_created"] += 1
            self.stats["total_events"] += 1

            print(f"\n🆕 OrderCreated Event #{self.stats['orders_created']}")
            print("   Raw Log Entry:")
            print(f"      Block: {log_entry.get('blockNumber')}")
            print(f"      Tx Hash: {log_entry.get('transactionHash')}")
            print(f"      Topics: {log_entry.get('topics')}")
            print(f"      Data: {log_entry.get('data')}")

            # Decode the event using Web3
            event = self.contract.events.OrderCreated().process_log(log_entry)
            args = event["args"]

            print("\n   Decoded Event:")
            print(f"      Order ID: {args['orderId']}")
            print(f"      Owner: {args['owner']}")
            print(f"      Side: {'BUY' if args['isBuy'] else 'SELL'}")
            print(f"      Price: {args['price'] / 1_000_000}")
            print(f"      Size: {args['size'] / 10**18}")

        except Exception as e:
            print(f"   ⚠ Parse error: {e}")

    async def _handle_trade(self, log_entry: dict[str, Any]) -> None:
        """Handle Trade event.

        Trade ABI fields:
        - orderId (uint40)
        - makerAddress (address)
        - isBuy (bool)
        - price (uint256) - 6 decimals
        - updatedSize (uint96) - remaining size, 18 decimals
        - takerAddress (address)
        - txOrigin (address)
        - filledSize (uint96) - 18 decimals

        Args:
            log_entry: Raw log entry
        """
        try:
            self.stats["trades"] += 1
            self.stats["total_events"] += 1

            print(f"\n💰 Trade Event #{self.stats['trades']}")
            print("   Raw Log Entry:")
            print(f"      Block: {log_entry.get('blockNumber')}")
            print(f"      Tx Hash: {log_entry.get('transactionHash')}")
            print(f"      Topics: {log_entry.get('topics')}")
            print(f"      Data: {log_entry.get('data')}")

            # Decode the event using Web3
            event = self.contract.events.Trade().process_log(log_entry)
            args = event["args"]

            print("\n   Decoded Event:")
            print(f"      Order ID: {args['orderId']}")
            print(f"      Maker: {args['makerAddress']}")
            print(f"      Taker: {args['takerAddress']}")
            print(f"      Side: {'BUY' if args['isBuy'] else 'SELL'}")
            print(f"      Price: {args['price'] / 1_000_000}")
            print(f"      Filled Size: {args['filledSize'] / 10**18}")
            print(f"      Updated Size: {args['updatedSize'] / 10**18}")

        except Exception as e:
            print(f"   ⚠ Parse error: {e}")

    async def _handle_orders_canceled(self, log_entry: dict[str, Any]) -> None:
        """Handle OrdersCanceled event.

        OrdersCanceled ABI fields:
        - orderId (uint40[]) - array of canceled order IDs (note: singular name)
        - owner (address) - wallet that canceled

        Args:
            log_entry: Raw log entry
        """
        try:
            self.stats["orders_canceled"] += 1
            self.stats["total_events"] += 1

            print(f"\n❌ OrdersCanceled Event #{self.stats['orders_canceled']}")
            print("   Raw Log Entry:")
            print(f"      Block: {log_entry.get('blockNumber')}")
            print(f"      Tx Hash: {log_entry.get('transactionHash')}")
            print(f"      Topics: {log_entry.get('topics')}")
            print(f"      Data: {log_entry.get('data')}")

            # Decode the event using Web3
            event = self.contract.events.OrdersCanceled().process_log(log_entry)
            args = event["args"]

            order_ids = list(args["orderId"])

            print("\n   Decoded Event:")
            print(f"      Owner: {args['owner']}")
            print(f"      Order IDs: {order_ids}")
            print(f"      Count: {len(order_ids)}")

        except Exception as e:
            print(f"   ⚠ Parse error: {e}")

    def _print_stats(self):
        """Print statistics summary."""
        print("\n" + "=" * 80)
        print("📊 Session Statistics:")
        print(f"   Total Events: {self.stats['total_events']}")
        print(f"   Orders Created: {self.stats['orders_created']}")
        print(f"   Trades: {self.stats['trades']}")
        print(f"   Orders Canceled: {self.stats['orders_canceled']}")
        print("=" * 80)

    async def run(self):
        """Run the listener indefinitely."""
        try:
            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._shutdown(s)))

            # Connect to blockchain RPC
            await self.connect()

            print("\n👂 Listening for blockchain events... Press Ctrl+C to exit\n")
            print("=" * 80)

            # Start listening for events
            listen_task = asyncio.create_task(self._listen_loop())

            # Wait for shutdown signal
            await self.shutdown_event.wait()

            # Cancel listening task
            listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listen_task

        except asyncio.CancelledError:
            print("\n⚠ Task cancelled")
        finally:
            await self.disconnect()
            self._print_stats()

    async def _shutdown(self, sig):
        """Handle shutdown signal."""
        print(f"\n\n🛑 Received signal {sig.name}, shutting down...")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Listen to blockchain contract events via eth_subscribe"
    )
    parser.add_argument(
        "--market",
        default=DEFAULT_MARKET_ADDRESS,
        help=f"OrderBook contract address to monitor (default: {DEFAULT_MARKET_ADDRESS})",
    )
    parser.add_argument(
        "--rpc-ws-url",
        default=DEFAULT_RPC_WS_URL,
        help=f"Blockchain RPC WebSocket URL (default: {DEFAULT_RPC_WS_URL})",
    )
    parser.add_argument(
        "--abi-path",
        default=DEFAULT_ABI_PATH,
        help=f"Path to OrderBook ABI JSON file (default: {DEFAULT_ABI_PATH})",
    )

    args = parser.parse_args()

    # Resolve ABI path
    abi_path = Path(args.abi_path)
    if not abi_path.exists():
        print(f"✗ Error: ABI file not found at {abi_path}")
        print(f"   Current directory: {Path.cwd()}")
        sys.exit(1)

    # Create and run listener
    listener = BlockchainEventListener(
        rpc_ws_url=args.rpc_ws_url,
        market_address=args.market,
        orderbook_abi_path=str(abi_path),
    )

    try:
        await listener.run()
    except KeyboardInterrupt:
        print("\n\n⚠ KeyboardInterrupt - exiting...")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
