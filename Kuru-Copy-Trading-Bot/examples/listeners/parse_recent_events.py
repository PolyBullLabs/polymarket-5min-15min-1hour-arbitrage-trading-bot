#!/usr/bin/env python3
"""
Parse Recent Blockchain Events - Learning Example

This script fetches recent events from the Kuru OrderBook contract and parses them.
Use this to understand how event parsing works without waiting for live events.

Event types on this contract:
- Trade: When an order is filled (most common)
- OrderCreated: When a new limit order is placed
- OrdersCanceled: When orders are canceled

Configuration:
- Uses MONAD_RPC_URL environment variable (or provide --rpc-ws-url)
- Uses MARKET_ADDRESS environment variable (or provide --market)

Usage:
    # Use environment variables from .env
    python examples/listeners/parse_recent_events.py

    # Override with command line arguments
    python examples/listeners/parse_recent_events.py --blocks 5000
    python examples/listeners/parse_recent_events.py --limit 5
    python examples/listeners/parse_recent_events.py --raw-only  # Show only raw hex data
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from web3 import Web3
from websockets import connect

DEFAULT_MARKET_ADDRESS = "0x122C0D8683Cab344163fB73E28E741754257e3Fa"
DEFAULT_RPC_URL = os.getenv("MONAD_RPC_URL")
DEFAULT_RPC_WS_URL = DEFAULT_RPC_URL.replace("https://", "wss://")
DEFAULT_ABI_PATH = "src/kuru_copytr_bot/config/abis/OrderBook.json"


class EventParser:
    """Parse Kuru OrderBook events from raw blockchain logs."""

    def __init__(self, abi_path: str, market_address: str):
        """Initialize parser with contract ABI.

        Args:
            abi_path: Path to OrderBook ABI JSON file
            market_address: Contract address
        """
        with open(abi_path) as f:
            self.abi = json.load(f)

        self.w3 = Web3()
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(market_address),
            abi=self.abi,
        )

        # Build event signature mapping (without 0x prefix for consistent lookup)
        self.event_signatures = {}
        for event_name in ["OrderCreated", "Trade", "OrdersCanceled"]:
            event = getattr(self.contract.events, event_name)
            event_abi = event._get_event_abi()
            input_types = ",".join([inp["type"] for inp in event_abi["inputs"]])
            sig = f"{event_abi['name']}({input_types})"
            sig_hash = self.w3.keccak(text=sig).hex()
            # Store without 0x prefix
            if sig_hash.startswith("0x"):
                sig_hash = sig_hash[2:]
            self.event_signatures[sig_hash] = event_name

        print("Event signatures:")
        for sig_hash, name in self.event_signatures.items():
            print(f"  {name}: {sig_hash}")
        print()

    def identify_event(self, log: dict) -> str | None:
        """Identify event type from log entry.

        Args:
            log: Raw log entry from eth_getLogs

        Returns:
            Event name or None if unknown
        """
        if not log.get("topics"):
            return None
        topic0 = log["topics"][0]
        # Normalize: remove 0x prefix for comparison
        if topic0.startswith("0x"):
            topic0 = topic0[2:]
        return self.event_signatures.get(topic0)

    def parse_trade(self, log: dict) -> dict:
        """Parse Trade event.

        Trade ABI fields:
        - orderId (uint40): Order ID
        - makerAddress (address): Maker wallet
        - isBuy (bool): True for buy side
        - price (uint256): Price with 6 decimal precision
        - updatedSize (uint96): Remaining size after fill (18 decimals)
        - takerAddress (address): Taker wallet
        - txOrigin (address): Transaction origin
        - filledSize (uint96): Size filled in this trade (18 decimals)

        Args:
            log: Raw log entry

        Returns:
            Parsed trade data
        """
        event = self.contract.events.Trade().process_log(log)
        args = event["args"]

        return {
            "event": "Trade",
            "order_id": args["orderId"],
            "maker_address": args["makerAddress"],
            "is_buy": args["isBuy"],
            "side": "BUY" if args["isBuy"] else "SELL",
            "price_raw": args["price"],
            "price": args["price"] / 1_000_000,  # 6 decimal precision
            "updated_size_raw": args["updatedSize"],
            "updated_size": args["updatedSize"] / 10**18,  # 18 decimals (wei)
            "taker_address": args["takerAddress"],
            "tx_origin": args["txOrigin"],
            "filled_size_raw": args["filledSize"],
            "filled_size": args["filledSize"] / 10**18,  # 18 decimals (wei)
            "tx_hash": log["transactionHash"],
            "block_number": int(log["blockNumber"], 16),
        }

    def parse_order_created(self, log: dict) -> dict:
        """Parse OrderCreated event.

        Args:
            log: Raw log entry

        Returns:
            Parsed order data
        """
        event = self.contract.events.OrderCreated().process_log(log)
        args = event["args"]

        return {
            "event": "OrderCreated",
            "order_id": args["orderId"],
            "owner": args["owner"],
            "is_buy": args["isBuy"],
            "side": "BUY" if args["isBuy"] else "SELL",
            "price_raw": args["price"],
            "price": args["price"] / 1_000_000,
            "size_raw": args["size"],
            "size": args["size"] / 10**18,
            "remaining_size": args["remainingSize"] / 10**18,
            "is_canceled": args.get("isCanceled", False),
            "cloid": args.get("cloid", ""),
            "tx_hash": log["transactionHash"],
            "block_number": int(log["blockNumber"], 16),
        }

    def parse_orders_canceled(self, log: dict) -> dict:
        """Parse OrdersCanceled event.

        Args:
            log: Raw log entry

        Returns:
            Parsed cancellation data
        """
        event = self.contract.events.OrdersCanceled().process_log(log)
        args = event["args"]

        return {
            "event": "OrdersCanceled",
            "maker": args["maker"],
            "order_ids": list(args["orderIds"]),
            "cloids": list(args.get("cloids", [])),
            "count": len(args["orderIds"]),
            "tx_hash": log["transactionHash"],
            "block_number": int(log["blockNumber"], 16),
        }

    def parse_log(self, log: dict) -> dict | None:
        """Parse any supported event from log.

        Args:
            log: Raw log entry

        Returns:
            Parsed event data or None if unsupported
        """
        event_name = self.identify_event(log)
        if event_name == "Trade":
            return self.parse_trade(log)
        elif event_name == "OrderCreated":
            return self.parse_order_created(log)
        elif event_name == "OrdersCanceled":
            return self.parse_orders_canceled(log)
        return None


async def fetch_recent_logs(
    rpc_url: str,
    market_address: str,
    blocks_back: int = 10000,
) -> tuple[list[dict], int, float]:
    """Fetch recent logs from the blockchain.

    Args:
        rpc_url: WebSocket RPC URL
        market_address: Contract address to query
        blocks_back: How many blocks to look back

    Returns:
        Tuple of (logs, latest_block, block_time)
    """
    async with connect(rpc_url) as ws:
        # Get latest block number
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_blockNumber",
                    "params": [],
                }
            )
        )
        resp = json.loads(await ws.recv())
        latest_block = int(resp["result"], 16)

        # Get block timestamps for timing info
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_getBlockByNumber",
                    "params": [hex(latest_block), False],
                }
            )
        )
        resp = json.loads(await ws.recv())
        latest_ts = int(resp["result"]["timestamp"], 16)

        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "eth_getBlockByNumber",
                    "params": [hex(latest_block - 1000), False],
                }
            )
        )
        resp = json.loads(await ws.recv())
        older_ts = int(resp["result"]["timestamp"], 16)
        block_time = (latest_ts - older_ts) / 1000

        # Fetch logs in chunks (RPC has block range limits)
        all_logs = []
        chunk_size = 2000  # Safe chunk size for most RPCs
        request_id = 4

        from_block = latest_block - blocks_back
        current_from = from_block

        while current_from < latest_block:
            current_to = min(current_from + chunk_size, latest_block)

            await ws.send(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "method": "eth_getLogs",
                        "params": [
                            {
                                "address": market_address,
                                "fromBlock": hex(current_from),
                                "toBlock": hex(current_to),
                            }
                        ],
                    }
                )
            )
            resp = json.loads(await ws.recv())
            request_id += 1

            if "error" in resp:
                # If still too large, try smaller chunk
                if "block range" in str(resp["error"]).lower():
                    chunk_size = chunk_size // 2
                    if chunk_size < 100:
                        raise Exception(f"RPC error: {resp['error']}")
                    continue
                raise Exception(f"RPC error: {resp['error']}")

            all_logs.extend(resp.get("result", []))
            current_from = current_to + 1

        return all_logs, latest_block, block_time


def print_raw_log(log: dict, index: int):
    """Print raw log entry for learning purposes."""
    print(f"\n{'='*70}")
    print(f"RAW LOG #{index + 1}")
    print(f"{'='*70}")
    print(f"Block Number: {log.get('blockNumber')} ({int(log.get('blockNumber', '0x0'), 16)})")
    print(f"Tx Hash:      {log.get('transactionHash')}")
    print(f"Log Index:    {log.get('logIndex')}")
    print(f"\nTopics ({len(log.get('topics', []))}):")
    for i, topic in enumerate(log.get("topics", [])):
        label = (
            "event signature (keccak256 of event name+types)" if i == 0 else f"indexed param {i}"
        )
        print(f"  [{i}] {topic}  <- {label}")
    print("\nData (non-indexed params, each 32 bytes / 64 hex chars):")
    data = log.get("data", "0x")
    if len(data) > 2:
        # Split data into 32-byte chunks for readability
        data_hex = data[2:]  # Remove 0x
        chunks = [data_hex[i : i + 64] for i in range(0, len(data_hex), 64)]
        # Trade event field mapping (for reference)
        trade_fields = [
            "orderId (uint40)",
            "makerAddress (address)",
            "isBuy (bool)",
            "price (uint256, 6 decimals)",
            "updatedSize (uint96, 18 decimals)",
            "takerAddress (address)",
            "txOrigin (address)",
            "filledSize (uint96, 18 decimals)",
        ]
        for i, chunk in enumerate(chunks):
            field_hint = f" <- {trade_fields[i]}" if i < len(trade_fields) else ""
            print(f"  [{i}] 0x{chunk}{field_hint}")
    else:
        print("  (empty)")


def print_parsed_event(parsed: dict):
    """Print parsed event data."""
    print(f"\nPARSED EVENT: {parsed['event']}")
    print("-" * 40)
    for key, value in parsed.items():
        if key == "event":
            continue
        print(f"  {key}: {value}")


async def main():
    parser = argparse.ArgumentParser(description="Fetch and parse recent Kuru OrderBook events")
    parser.add_argument(
        "--market",
        default=DEFAULT_MARKET_ADDRESS,
        help=f"OrderBook contract address (default: {DEFAULT_MARKET_ADDRESS})",
    )
    parser.add_argument(
        "--rpc-ws-url",
        default=DEFAULT_RPC_WS_URL,
        help=f"RPC WebSocket URL (default: {DEFAULT_RPC_WS_URL})",
    )
    parser.add_argument(
        "--abi-path",
        default=DEFAULT_ABI_PATH,
        help=f"Path to ABI file (default: {DEFAULT_ABI_PATH})",
    )
    parser.add_argument(
        "--blocks",
        type=int,
        default=10000,
        help="Number of blocks to look back (default: 10000)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max events to display (default: 10)",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Only show raw logs, skip parsing",
    )

    args = parser.parse_args()

    # Verify ABI exists
    abi_path = Path(args.abi_path)
    if not abi_path.exists():
        print(f"Error: ABI file not found at {abi_path}")
        print(f"Current directory: {Path.cwd()}")
        return

    print(f"Fetching events from last {args.blocks} blocks...")
    print(f"Market: {args.market}")
    print(f"RPC: {args.rpc_ws_url}")
    print()

    # Initialize parser
    event_parser = EventParser(str(abi_path), args.market)

    # Fetch logs
    logs, latest_block, block_time = await fetch_recent_logs(
        args.rpc_ws_url,
        args.market,
        args.blocks,
    )

    print(f"Latest block: {latest_block}")
    print(f"Block time: ~{block_time:.2f} seconds")
    print(f"Time range: ~{args.blocks * block_time / 3600:.1f} hours")
    print(f"Total events found: {len(logs)}")

    if not logs:
        print("\nNo events found in this range. Try increasing --blocks")
        return

    # Count by event type
    event_counts = {}
    for log in logs:
        event_name = event_parser.identify_event(log) or "Unknown"
        event_counts[event_name] = event_counts.get(event_name, 0) + 1

    print("\nEvents by type:")
    for name, count in sorted(event_counts.items()):
        print(f"  {name}: {count}")

    # Display events (most recent first)
    display_logs = list(reversed(logs[-args.limit :]))
    print(f"\n\nShowing {len(display_logs)} most recent events:")

    for i, log in enumerate(display_logs):
        # Print raw log
        print_raw_log(log, i)

        # Parse and print
        if not args.raw_only:
            try:
                parsed = event_parser.parse_log(log)
                if parsed:
                    print_parsed_event(parsed)
                else:
                    print("\n(Unknown event type - cannot parse)")
            except Exception as e:
                print(f"\nParse error: {e}")

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
