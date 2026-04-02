"""
Main entry point for Polymarket Copy Trading Bot
"""
import asyncio
import signal
import sys
from src.config.db import connect_db, close_db
from src.config.env import ENV
from src.utils.create_clob_client import create_clob_client
from src.services.trade_executor import trade_executor, stop_trade_executor
from src.services.trade_monitor import trade_monitor, stop_trade_monitor
from src.utils.logger import startup, info, success, warning, error, separator
from src.utils.system_status import check_system_status, display_system_status

# Global shutdown flag
is_shutting_down = False
shutdown_event = None


def signal_handler(signum=None, frame=None):
    """Handle termination signals (sync wrapper)"""
    global is_shutting_down, shutdown_event
    
    if is_shutting_down:
        warning('Shutdown already in progress, forcing exit...')
        sys.exit(1)
    
    is_shutting_down = True
    # Set the shutdown event to trigger async shutdown
    if shutdown_event is not None:
        shutdown_event.set()


async def graceful_shutdown():
    """Handle graceful shutdown (async)"""
    separator()
    info('Initiating graceful shutdown...')
    
    try:
        # Stop services
        stop_trade_monitor()
        stop_trade_executor()
        
        # Give services time to finish current operations
        info('Waiting for services to finish current operations...')
        await asyncio.sleep(2)
        
        # Close database connection
        close_db()
        
        success('Graceful shutdown completed')
    except Exception as e:
        error(f'Error during shutdown: {e}')


# Handle termination signals
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


async def main():
    """Main async function"""
    global shutdown_event
    
    # Initialize shutdown event
    shutdown_event = asyncio.Event()
    
    try:
        # Welcome message for first-time users
        print('\n[INFO] First time running the bot?')
        print('  Read the guide: GETTING_STARTED.md')
        print('  Run system status check: python -m src.scripts.setup.system_status\n')
        
        await connect_db()
        startup(ENV.USER_ADDRESSES, ENV.PROXY_WALLET)
        
        # Perform initial system status check
        info('Performing initial system status check...')
        status_result = await check_system_status()
        display_system_status(status_result)
        
        if not status_result.get('healthy', False):
            warning('System status check failed, but continuing startup...')
        
        info('Initializing CLOB client...')
        clob_client = await create_clob_client()
        success('CLOB client ready')
        
        separator()
        info('Starting trade monitor...')
        # Start trade monitor in background
        monitor_task = asyncio.create_task(trade_monitor())
        
        info('Starting trade executor...')
        # Start trade executor in background
        executor_task = asyncio.create_task(trade_executor(clob_client))
        
        # Wait for shutdown event
        await shutdown_event.wait()
        
        # If shutdown event is set, cancel tasks and perform graceful shutdown
        if shutdown_event.is_set():
            monitor_task.cancel()
            executor_task.cancel()
            await asyncio.gather(monitor_task, executor_task, return_exceptions=True)  # Wait for tasks to finish cancelling
            await graceful_shutdown()
        
    except KeyboardInterrupt:
        await graceful_shutdown()
    except Exception as e:
        error(f'Fatal error during startup: {e}')
        await graceful_shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Signal handler will handle shutdown

