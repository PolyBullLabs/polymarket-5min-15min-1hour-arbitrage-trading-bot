"""
Trade monitor service - monitors trader activity via WebSocket
"""
import asyncio
import json
import websockets
from typing import List, Dict, Any, Optional
from ..config.env import ENV
from ..models.user_history import get_user_activity_collection, get_user_position_collection
from ..utils.fetch_data import fetch_data_async
from ..utils.logger import (
    info, success, warning, error, db_connection, my_positions,
    traders_positions, clear_line
)
from ..utils.get_my_balance import get_my_balance_async

USER_ADDRESSES = ENV.USER_ADDRESSES
TOO_OLD_TIMESTAMP = ENV.TOO_OLD_TIMESTAMP
RTDS_URL = 'wss://ws-live-data.polymarket.com'

if not USER_ADDRESSES or len(USER_ADDRESSES) == 0:
    raise ValueError('USER_ADDRESSES is not defined or empty')

# WebSocket connection state
ws: Optional[websockets.client.WebSocketClientProtocol] = None
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY = 5  # 5 seconds
is_running = True
position_update_task: Optional[asyncio.Task] = None
is_first_run = True


async def init():
    """Initialize monitor"""
    counts = []
    for address in USER_ADDRESSES:
        collection = get_user_activity_collection(address)
        count = collection.count_documents({})
        counts.append(count)
    
    clear_line()
    db_connection(USER_ADDRESSES, counts)
    
    # Show your own positions first
    try:
        my_positions_url = f'https://data-api.polymarket.com/positions?user={ENV.PROXY_WALLET}'
        my_positions_data = await fetch_data_async(my_positions_url)
        
        # Get current USDC balance
        current_balance = await get_my_balance_async(ENV.PROXY_WALLET)
        
        if isinstance(my_positions_data, list) and len(my_positions_data) > 0:
            # Calculate your overall profitability and initial investment
            total_value = sum(pos.get('currentValue', 0) or 0 for pos in my_positions_data)
            initial_value = sum(pos.get('initialValue', 0) or 0 for pos in my_positions_data)
            weighted_pnl = sum((pos.get('currentValue', 0) or 0) * (pos.get('percentPnl', 0) or 0) for pos in my_positions_data)
            my_overall_pnl = weighted_pnl / total_value if total_value > 0 else 0
            
            # Get top 5 positions by profitability (PnL)
            my_top_positions = sorted(
                my_positions_data,
                key=lambda x: x.get('percentPnl', 0) or 0,
                reverse=True
            )[:5]
            
            clear_line()
            my_positions(
                ENV.PROXY_WALLET,
                len(my_positions_data),
                my_top_positions,
                my_overall_pnl,
                total_value,
                initial_value,
                current_balance
            )
        else:
            clear_line()
            my_positions(ENV.PROXY_WALLET, 0, [], 0, 0, 0, current_balance)
    except Exception as e:
        error(f'Failed to fetch your positions: {e}')
    
    # Show current positions count with details for traders you're copying
    position_counts = []
    position_details = []
    profitabilities = []
    
    for address in USER_ADDRESSES:
        position_collection = get_user_position_collection(address)
        positions = list(position_collection.find())
        position_counts.append(len(positions))
        
        # Calculate overall profitability (weighted average by current value)
        total_value = sum(pos.get('currentValue', 0) or 0 for pos in positions)
        weighted_pnl = sum((pos.get('currentValue', 0) or 0) * (pos.get('percentPnl', 0) or 0) for pos in positions)
        overall_pnl = weighted_pnl / total_value if total_value > 0 else 0
        profitabilities.append(overall_pnl)
        
        # Get top 3 positions by profitability (PnL)
        top_positions = sorted(
            positions,
            key=lambda x: x.get('percentPnl', 0) or 0,
            reverse=True
        )[:3]
        position_details.append(top_positions)
    
    clear_line()
    traders_positions(USER_ADDRESSES, position_counts, position_details, profitabilities)


async def process_trade_activity(activity: Dict[str, Any], address: str):
    """Process incoming trade activity from RTDS"""
    activity_collection = get_user_activity_collection(address)
    position_collection = get_user_position_collection(address)
    
    try:
        # Skip if too old
        activity_timestamp = activity.get('timestamp', 0)
        if activity_timestamp > 1000000000000:
            activity_timestamp_ms = activity_timestamp
        else:
            activity_timestamp_ms = activity_timestamp * 1000
        
        import time
        hours_ago = (time.time() * 1000 - activity_timestamp_ms) / (1000 * 60 * 60)
        if hours_ago > TOO_OLD_TIMESTAMP:
            return
        
        # Check if this trade already exists in database
        existing = activity_collection.find_one({'transactionHash': activity.get('transactionHash')})
        if existing:
            return  # Already processed this trade
        
        # Save new trade to database
        new_activity = {
            'proxyWallet': activity.get('proxyWallet'),
            'timestamp': activity.get('timestamp'),
            'conditionId': activity.get('conditionId'),
            'type': 'TRADE',
            'size': activity.get('size'),
            'usdcSize': activity.get('price', 0) * activity.get('size', 0),
            'transactionHash': activity.get('transactionHash'),
            'price': activity.get('price'),
            'asset': activity.get('asset'),
            'side': activity.get('side'),
            'outcomeIndex': activity.get('outcomeIndex'),
            'title': activity.get('title'),
            'slug': activity.get('slug'),
            'icon': activity.get('icon'),
            'eventSlug': activity.get('eventSlug'),
            'outcome': activity.get('outcome'),
            'name': activity.get('name'),
            'pseudonym': activity.get('pseudonym'),
            'bio': activity.get('bio'),
            'profileImage': activity.get('profileImage'),
            'profileImageOptimized': activity.get('profileImageOptimized'),
            'bot': False,
            'botExcutedTime': 0,
        }
        
        activity_collection.insert_one(new_activity)
        info(f'New trade detected for {address[:6]}...{address[-4:]}')
    except Exception as e:
        error(f'Error processing trade activity for {address[:6]}...{address[-4:]}: {e}')


async def update_positions():
    """Fetch and update positions"""
    for address in USER_ADDRESSES:
        try:
            positions_url = f'https://data-api.polymarket.com/positions?user={address}'
            positions = await fetch_data_async(positions_url)
            
            if isinstance(positions, list) and len(positions) > 0:
                position_collection = get_user_position_collection(address)
                for position in positions:
                    # Update or create position
                    position_collection.update_one(
                        {'asset': position.get('asset'), 'conditionId': position.get('conditionId')},
                        {'$set': {
                            'proxyWallet': position.get('proxyWallet'),
                            'asset': position.get('asset'),
                            'conditionId': position.get('conditionId'),
                            'size': position.get('size'),
                            'avgPrice': position.get('avgPrice'),
                            'initialValue': position.get('initialValue'),
                            'currentValue': position.get('currentValue'),
                            'cashPnl': position.get('cashPnl'),
                            'percentPnl': position.get('percentPnl'),
                            'totalBought': position.get('totalBought'),
                            'realizedPnl': position.get('realizedPnl'),
                            'percentRealizedPnl': position.get('percentRealizedPnl'),
                            'curPrice': position.get('curPrice'),
                            'redeemable': position.get('redeemable'),
                            'mergeable': position.get('mergeable'),
                            'title': position.get('title'),
                            'slug': position.get('slug'),
                            'icon': position.get('icon'),
                            'eventSlug': position.get('eventSlug'),
                            'outcome': position.get('outcome'),
                            'outcomeIndex': position.get('outcomeIndex'),
                            'oppositeOutcome': position.get('oppositeOutcome'),
                            'oppositeAsset': position.get('oppositeAsset'),
                            'endDate': position.get('endDate'),
                            'negativeRisk': position.get('negativeRisk'),
                        }},
                        upsert=True
                    )
        except Exception as e:
            error(f'Error updating positions for {address[:6]}...{address[-4:]}: {e}')


async def connect_rtds():
    """Connect to RTDS WebSocket and subscribe to trader activities"""
    global ws, reconnect_attempts
    
    try:
        info(f'Connecting to RTDS at {RTDS_URL}...')
        
        # Create a connection task to properly handle timeout
        async def _connect():
            return await websockets.connect(
                RTDS_URL,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
        
        # Use wait_for to add timeout, but create the connection task properly
        connect_task = asyncio.create_task(_connect())
        try:
            ws = await asyncio.wait_for(connect_task, timeout=30.0)
            success('RTDS WebSocket connected')
            reconnect_attempts = 0
        except asyncio.TimeoutError:
            connect_task.cancel()
            raise Exception('Connection timeout after 30 seconds')
        
        # Subscribe to activity/trades for each trader address
        subscriptions = [{
            'topic': 'activity',
            'type': 'trades',
        } for _ in USER_ADDRESSES]
        
        subscribe_message = {
            'action': 'subscribe',
            'subscriptions': subscriptions,
        }
        
        await ws.send(json.dumps(subscribe_message))
        success(f'Subscribed to RTDS for {len(USER_ADDRESSES)} trader(s) - monitoring in real-time')
        
        # Listen for messages
        async for message in ws:
            if not is_running:
                break
            
            try:
                # Handle binary messages by converting to string
                if isinstance(message, bytes):
                    try:
                        message = message.decode('utf-8')
                    except UnicodeDecodeError:
                        # Skip binary messages that aren't UTF-8
                        continue
                
                # Skip empty or non-string messages
                if not isinstance(message, str) or not message.strip():
                    continue
                
                # Try to parse as JSON
                try:
                    data = json.loads(message)
                except json.JSONDecodeError as json_err:
                    # Not valid JSON, might be a ping/pong or other control message
                    # Silently skip common control messages and empty strings
                    msg_clean = message.strip()
                    if msg_clean and msg_clean not in ['ping', 'pong']:
                        # Only log unexpected non-JSON messages
                        warning(f'Received non-JSON message (length: {len(message)}): {message[:100]}')
                    continue
                
                # Handle subscription confirmation
                if data.get('action') == 'subscribed' or data.get('status') == 'subscribed':
                    info('RTDS subscription confirmed')
                    continue
                
                # Handle trade activity messages
                if data.get('topic') == 'activity' and data.get('type') == 'trades' and data.get('payload'):
                    activity = data['payload']
                    trader_address = activity.get('proxyWallet', '').lower()
                    
                    if trader_address in [addr.lower() for addr in USER_ADDRESSES]:
                        await process_trade_activity(activity, trader_address)
            except Exception as e:
                # Only log unexpected errors (not JSON parsing errors which are handled above)
                error_msg = str(e)
                # Skip common JSON parsing errors that we've already handled
                if 'Expecting value' not in error_msg and 'JSON' not in error_msg:
                    error(f'Error processing RTDS message: {e}')
                # Silently skip JSON parsing errors for empty/invalid messages
                
    except Exception as e:
        error(f'RTDS WebSocket error: {e}')
        if ws:
            await ws.close()
        raise


async def reconnect_loop():
    """Handle reconnection logic"""
    global reconnect_attempts, ws
    
    while is_running and reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            await connect_rtds()
            # If connection successful, break out of loop
            break
        except Exception as e:
            reconnect_attempts += 1
            if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                delay = RECONNECT_DELAY * min(reconnect_attempts, 5)  # Max 25 seconds
                info(f'Reconnecting to RTDS in {delay}s (attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})...')
                await asyncio.sleep(delay)
            else:
                error(f'Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached. Please restart the bot.')


def stop_trade_monitor():
    """Stop the trade monitor gracefully"""
    global is_running, position_update_task, ws
    
    is_running = False
    
    if position_update_task:
        position_update_task.cancel()
        position_update_task = None
    
    if ws:
        asyncio.create_task(ws.close())
        ws = None
    
    info('Trade monitor shutdown requested...')


async def trade_monitor():
    """Main trade monitor function"""
    global is_first_run, position_update_task
    
    await init()
    success(f'Monitoring {len(USER_ADDRESSES)} trader(s) using RTDS (Real-Time Data Stream)')
    
    # On first run, mark all existing historical trades as already processed
    if is_first_run:
        info('First run: marking all historical trades as processed...')
        for address in USER_ADDRESSES:
            collection = get_user_activity_collection(address)
            result = collection.update_many(
                {'bot': False},
                {'$set': {'bot': True, 'botExcutedTime': 999}}
            )
            if result.modified_count > 0:
                info(f'Marked {result.modified_count} historical trades as processed for {address[:6]}...{address[-4:]}')
        
        is_first_run = False
        success('\nHistorical trades processed. Now monitoring for new trades only.')
    
    # Connect to RTDS
    try:
        await reconnect_loop()
        
        # Update positions periodically (every 30 seconds)
        async def update_positions_periodically():
            while is_running:
                await asyncio.sleep(30)
                if is_running:
                    await update_positions()
        
        position_update_task = asyncio.create_task(update_positions_periodically())
        
        # Keep the process alive
        while is_running:
            await asyncio.sleep(1)
            
    except Exception as e:
        error(f'Failed to connect to RTDS: {e}')
        error('Falling back to HTTP polling is not implemented. Please check your connection.')
        raise
    
    info('Trade monitor stopped')

