"""
Trade executor service - executes trades based on monitored activity
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
from ..config.env import ENV
from ..models.user_history import get_user_activity_collection
from ..interfaces.user import UserActivityInterface, UserPositionInterface
from ..utils.fetch_data import fetch_data_async
from ..utils.get_my_balance import get_my_balance_async
from ..utils.post_order import post_order
from ..utils.logger import (
    success, info, warning, header, waiting, clear_line, separator, trade as log_trade, balance as log_balance
)

USER_ADDRESSES = ENV.USER_ADDRESSES
RETRY_LIMIT = ENV.RETRY_LIMIT
PROXY_WALLET = ENV.PROXY_WALLET
TRADE_AGGREGATION_ENABLED = ENV.TRADE_AGGREGATION_ENABLED
TRADE_AGGREGATION_WINDOW_SECONDS = ENV.TRADE_AGGREGATION_WINDOW_SECONDS
TRADE_AGGREGATION_MIN_TOTAL_USD = 1.0  # Polymarket minimum

is_running = True

# Type definitions (using Dict for flexibility)
TradeWithUser = Dict[str, Any]
AggregatedTrade = Dict[str, Any]


# Buffer for aggregating trades
trade_aggregation_buffer: Dict[str, AggregatedTrade] = {}


async def read_temp_trades() -> List[TradeWithUser]:
    """Read unprocessed trades from database"""
    all_trades: List[TradeWithUser] = []
    
    for address in USER_ADDRESSES:
        collection = get_user_activity_collection(address)
        # Only get trades that haven't been processed yet (bot: false AND botExcutedTime: 0)
        # This prevents processing the same trade multiple times
        trades = list(collection.find({
            'type': 'TRADE',
            'bot': False,
            'botExcutedTime': 0
        }))
        
        for trade in trades:
            trade['userAddress'] = address
            all_trades.append(trade)
    
    return all_trades


def get_aggregation_key(trade: TradeWithUser) -> str:
    """Generate a unique key for trade aggregation based on user, market, side"""
    return f"{trade['userAddress']}:{trade.get('conditionId', '')}:{trade.get('asset', '')}:{trade.get('side', 'BUY')}"


def add_to_aggregation_buffer(trade: TradeWithUser) -> None:
    """Add trade to aggregation buffer or update existing aggregation"""
    key = get_aggregation_key(trade)
    existing = trade_aggregation_buffer.get(key)
    now = int(time.time() * 1000)  # milliseconds
    
    if existing:
        # Update existing aggregation
        existing['trades'].append(trade)
        existing['totalUsdcSize'] += trade.get('usdcSize', 0)
        # Recalculate weighted average price
        total_value = sum(t.get('usdcSize', 0) * t.get('price', 0) for t in existing['trades'])
        existing['averagePrice'] = total_value / existing['totalUsdcSize'] if existing['totalUsdcSize'] > 0 else 0
        existing['lastTradeTime'] = now
    else:
        # Create new aggregation
        trade_aggregation_buffer[key] = {
            'userAddress': trade['userAddress'],
            'conditionId': trade.get('conditionId', ''),
            'asset': trade.get('asset', ''),
            'side': trade.get('side', 'BUY'),
            'slug': trade.get('slug'),
            'eventSlug': trade.get('eventSlug'),
            'trades': [trade],
            'totalUsdcSize': trade.get('usdcSize', 0),
            'averagePrice': trade.get('price', 0),
            'firstTradeTime': now,
            'lastTradeTime': now,
        }


def get_ready_aggregated_trades() -> List[AggregatedTrade]:
    """Check buffer and return ready aggregated trades
    Trades are ready if:
    1. Total size >= minimum AND
    2. Time window has passed since first trade
    """
    ready: List[AggregatedTrade] = []
    now = int(time.time() * 1000)  # milliseconds
    window_ms = TRADE_AGGREGATION_WINDOW_SECONDS * 1000
    
    keys_to_remove = []
    
    for key, agg in trade_aggregation_buffer.items():
        time_elapsed = now - agg['firstTradeTime']
        
        # Check if aggregation is ready
        if time_elapsed >= window_ms:
            if agg['totalUsdcSize'] >= TRADE_AGGREGATION_MIN_TOTAL_USD:
                # Aggregation meets minimum and window passed - ready to execute
                ready.append(agg)
            else:
                # Window passed but total too small - mark individual trades as skipped
                info(
                    f"Trade aggregation for {agg['userAddress']} on {agg.get('slug') or agg.get('asset', 'unknown')}: "
                    f"${agg['totalUsdcSize']:.2f} total from {len(agg['trades'])} trades below minimum "
                    f"(${TRADE_AGGREGATION_MIN_TOTAL_USD}) - skipping"
                )
                
                # Mark all trades in this aggregation as processed (bot: true)
                for trade in agg['trades']:
                    collection = get_user_activity_collection(trade['userAddress'])
                    collection.update_one({'_id': trade['_id']}, {'$set': {'bot': True}})
            
            # Remove from buffer either way
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del trade_aggregation_buffer[key]
    
    return ready


async def do_trading(clob_client: Any, trades: List[TradeWithUser]) -> None:
    """Execute trades"""
    for trade in trades:
        # Mark trade as being processed immediately to prevent duplicate processing
        collection = get_user_activity_collection(trade['userAddress'])
        collection.update_one(
            {'_id': trade['_id']},
            {'$set': {'botExcutedTime': 1}}
        )
        
        log_trade(
            trade['userAddress'],
            trade.get('side', 'UNKNOWN'),
            {
                'asset': trade.get('asset'),
                'side': trade.get('side'),
                'amount': trade.get('usdcSize'),
                'price': trade.get('price'),
                'slug': trade.get('slug'),
                'eventSlug': trade.get('eventSlug'),
                'transactionHash': trade.get('transactionHash'),
            }
        )
        
        my_positions_data = await fetch_data_async(f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}')
        user_positions_data = await fetch_data_async(f'https://data-api.polymarket.com/positions?user={trade["userAddress"]}')
        
        my_positions_list = my_positions_data if isinstance(my_positions_data, list) else []
        user_positions_list = user_positions_data if isinstance(user_positions_data, list) else []
        
        my_position = next(
            (p for p in my_positions_list if p.get('conditionId') == trade.get('conditionId')),
            None
        )
        user_position = next(
            (p for p in user_positions_list if p.get('conditionId') == trade.get('conditionId')),
            None
        )
        
        # Get USDC balance
        my_balance = await get_my_balance_async(PROXY_WALLET)
        
        # Calculate trader's total portfolio value from positions
        user_balance = sum(pos.get('currentValue', 0) or 0 for pos in user_positions_list)
        
        log_balance(my_balance, user_balance, trade['userAddress'])
        
        # Execute the trade
        await post_order(
            clob_client,
            'buy' if trade.get('side') == 'BUY' else 'sell',
            my_position,
            user_position,
            trade,
            my_balance,
            user_balance,
            trade['userAddress']
        )
        
        separator()


async def do_aggregated_trading(clob_client: Any, aggregated_trades: List[AggregatedTrade]) -> None:
    """Execute aggregated trades"""
    for agg in aggregated_trades:
        header(f"AGGREGATED TRADE ({len(agg['trades'])} trades combined)")
        info(f"Market: {agg.get('slug') or agg.get('asset', 'unknown')}")
        info(f"Side: {agg.get('side', 'BUY')}")
        info(f"Total volume: ${agg['totalUsdcSize']:.2f}")
        info(f"Average price: ${agg['averagePrice']:.4f}")
        
        # Mark all individual trades as being processed
        for trade in agg['trades']:
            collection = get_user_activity_collection(trade['userAddress'])
            collection.update_one(
                {'_id': trade['_id']},
                {'$set': {'botExcutedTime': 1}}
            )
        
        my_positions_data = await fetch_data_async(f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}')
        user_positions_data = await fetch_data_async(f'https://data-api.polymarket.com/positions?user={agg["userAddress"]}')
        
        my_positions_list = my_positions_data if isinstance(my_positions_data, list) else []
        user_positions_list = user_positions_data if isinstance(user_positions_data, list) else []
        
        my_position = next(
            (p for p in my_positions_list if p.get('conditionId') == agg.get('conditionId')),
            None
        )
        user_position = next(
            (p for p in user_positions_list if p.get('conditionId') == agg.get('conditionId')),
            None
        )
        
        # Get USDC balance
        my_balance = await get_my_balance_async(PROXY_WALLET)
        
        # Calculate trader's total portfolio value from positions
        user_balance = sum(pos.get('currentValue', 0) or 0 for pos in user_positions_list)
        
        log_balance(my_balance, user_balance, agg['userAddress'])
        
        # Create a synthetic trade object for postOrder using aggregated values
        synthetic_trade: TradeWithUser = {
            **agg['trades'][0],  # Use first trade as template
            'usdcSize': agg['totalUsdcSize'],
            'price': agg['averagePrice'],
            'side': agg.get('side', 'BUY'),
        }
        
        # Execute the aggregated trade
        await post_order(
            clob_client,
            'buy' if agg.get('side', 'BUY') == 'BUY' else 'sell',
            my_position,
            user_position,
            synthetic_trade,
            my_balance,
            user_balance,
            agg['userAddress']
        )
        
        separator()


def stop_trade_executor() -> None:
    """Stop the trade executor gracefully"""
    global is_running
    is_running = False
    info('Trade executor shutdown requested...')


async def trade_executor(clob_client: Any) -> None:
    """Main trade executor function"""
    success(f'Trade executor ready for {len(USER_ADDRESSES)} trader(s)')
    if TRADE_AGGREGATION_ENABLED:
        info(
            f'Trade aggregation enabled: {TRADE_AGGREGATION_WINDOW_SECONDS}s window, '
            f'${TRADE_AGGREGATION_MIN_TOTAL_USD} minimum'
        )
    
    last_check = time.time()
    
    while is_running:
        trades = await read_temp_trades()
        
        if TRADE_AGGREGATION_ENABLED:
            # Process with aggregation logic
            if trades:
                clear_line()
                info(f'{len(trades)} new trade{"s" if len(trades) > 1 else ""} detected')
                
                # Add trades to aggregation buffer
                for trade in trades:
                    # Only aggregate BUY trades below minimum threshold
                    if trade.get('side') == 'BUY' and trade.get('usdcSize', 0) < TRADE_AGGREGATION_MIN_TOTAL_USD:
                        info(
                            f"Adding ${trade.get('usdcSize', 0):.2f} {trade.get('side', 'BUY')} trade to aggregation buffer "
                            f"for {trade.get('slug') or trade.get('asset', 'unknown')}"
                        )
                        add_to_aggregation_buffer(trade)
                    else:
                        # Execute large trades immediately (not aggregated)
                        clear_line()
                        header('IMMEDIATE TRADE (above threshold)')
                        await do_trading(clob_client, [trade])
                
                last_check = time.time()
            
            # Check for ready aggregated trades
            ready_aggregations = get_ready_aggregated_trades()
            if ready_aggregations:
                clear_line()
                header(
                    f"{len(ready_aggregations)} AGGREGATED TRADE{'S' if len(ready_aggregations) > 1 else ''} READY"
                )
                await do_aggregated_trading(clob_client, ready_aggregations)
                last_check = time.time()
            
            # Update waiting message
            if not trades and not ready_aggregations:
                if time.time() - last_check > 0.3:
                    buffered_count = len(trade_aggregation_buffer)
                    if buffered_count > 0:
                        waiting(len(USER_ADDRESSES), f'{buffered_count} trade group(s) pending')
                    else:
                        waiting(len(USER_ADDRESSES))
                    last_check = time.time()
        else:
            # Original non-aggregation logic
            if trades:
                clear_line()
                header(f'{len(trades)} NEW TRADE{"S" if len(trades) > 1 else ""} TO COPY')
                await do_trading(clob_client, trades)
                last_check = time.time()
            else:
                # Update waiting message every 300ms for smooth animation
                if time.time() - last_check > 0.3:
                    waiting(len(USER_ADDRESSES))
                    last_check = time.time()
        
        if not is_running:
            break
        
        await asyncio.sleep(0.3)
    
    info('Trade executor stopped')
