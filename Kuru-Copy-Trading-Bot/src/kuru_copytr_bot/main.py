"""Main entry point for Kuru Copy Trading Bot."""

import asyncio
import signal
import sys

import click
from dotenv import load_dotenv

from src.kuru_copytr_bot.bot import CopyTradingBot
from src.kuru_copytr_bot.config.settings import Settings
from src.kuru_copytr_bot.connectors.blockchain.event_subscriber import (
    BlockchainEventSubscriber,
)
from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.connectors.platforms.kuru import KuruClient
from src.kuru_copytr_bot.core.enums import OrderType
from src.kuru_copytr_bot.risk.calculator import PositionSizeCalculator
from src.kuru_copytr_bot.risk.validator import TradeValidator
from src.kuru_copytr_bot.trading.copier import TradeCopier
from src.kuru_copytr_bot.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


class BotRunner:
    """Manages bot lifecycle and component initialization."""

    def __init__(self, settings: Settings):
        """Initialize bot runner.

        Args:
            settings: Bot configuration settings
        """
        self.settings = settings
        self.bot: CopyTradingBot | None = None
        self.running = False

    def initialize_components(self) -> CopyTradingBot:
        """Initialize all bot components.

        Returns:
            Configured CopyTradingBot instance
        """
        logger.info("Initializing bot components")

        # Initialize blockchain connector
        logger.debug(
            "Creating Monad blockchain client",
            rpc_url=self.settings.monad_rpc_url,
            dry_run=self.settings.dry_run,
        )
        monad_client = MonadClient(
            rpc_url=self.settings.monad_rpc_url,
            private_key=self.settings.wallet_private_key,
            dry_run=self.settings.dry_run,
        )

        # Initialize Kuru Exchange client
        logger.debug("Creating Kuru Exchange client")
        kuru_client = KuruClient(
            blockchain=monad_client,
            contract_address=self.settings.market_addresses[
                0
            ],  # Will use first market for operations
            network=self.settings.network,
        )

        # Initialize blockchain event subscribers for each market
        # Convert HTTP RPC URL to WebSocket URL
        rpc_ws_url = self.settings.monad_rpc_url.replace("https://", "wss://").replace(
            "http://", "ws://"
        )

        logger.debug(
            "Creating blockchain event subscribers",
            market_count=len(self.settings.market_addresses),
            rpc_ws_url=rpc_ws_url,
        )

        event_subscribers = []
        for market_address in self.settings.market_addresses:
            # Get market parameters to obtain correct precisions
            market_params = kuru_client.get_market_params(market_address)
            logger.debug(
                "Fetched market parameters for event subscriber",
                market=market_address,
                size_precision=market_params.size_precision,
                price_precision=market_params.price_precision,
            )

            subscriber = BlockchainEventSubscriber(
                rpc_ws_url=rpc_ws_url,
                market_address=market_address,
                orderbook_abi=kuru_client.orderbook_abi,
                size_precision=market_params.size_precision,
                price_precision=market_params.price_precision,
            )
            event_subscribers.append((market_address, subscriber))
            logger.debug("Created blockchain event subscriber", market=market_address)

        # Initialize position size calculator
        logger.debug(
            "Creating position size calculator",
            copy_ratio=float(self.settings.copy_ratio),
            max_position_size=float(self.settings.max_position_size),
            min_order_size=float(self.settings.min_order_size),
        )
        calculator = PositionSizeCalculator(
            copy_ratio=self.settings.copy_ratio,
            max_position_size=self.settings.max_position_size,
            min_order_size=self.settings.min_order_size,
            respect_balance=True,  # Scale down order to fit available balance
            enforce_minimum=True,  # Use minimum order size if calculated size is below minimum
        )

        # Initialize trade validator
        logger.debug(
            "Creating trade validator",
            min_balance=float(self.settings.min_balance_threshold),
            max_total_exposure=float(self.settings.max_total_exposure),
        )
        validator = TradeValidator(
            min_balance=self.settings.min_balance_threshold,
            min_order_size=self.settings.min_order_size,  # Enforce minimum in validator too
            max_position_size=self.settings.max_position_size,
            max_exposure_usd=self.settings.max_total_exposure,
            market_whitelist=self.settings.market_whitelist,
            market_blacklist=self.settings.market_blacklist,
        )

        # Initialize trade copier
        logger.debug("Creating trade copier")
        copier = TradeCopier(
            kuru_client=kuru_client,
            calculator=calculator,
            validator=validator,
            default_order_type=OrderType.LIMIT,
        )

        # Initialize bot orchestrator
        logger.debug(
            "Creating bot orchestrator",
            track_all_market_orders=self.settings.dry_run_track_all_market_orders,
        )
        bot = CopyTradingBot(
            event_subscribers=event_subscribers,
            source_wallets=self.settings.source_wallets,
            copier=copier,
            track_all_market_orders=self.settings.dry_run_track_all_market_orders,
        )

        logger.info("All bot components initialized successfully")
        return bot

    async def run_async(self) -> None:
        """Run the copy trading bot asynchronously."""
        # Initialize components
        click.echo("Initializing Kuru Copy Trading Bot...")
        self.bot = self.initialize_components()

        # Display startup info
        click.echo(f"Monitoring {len(self.settings.market_addresses)} markets")

        if self.settings.dry_run:
            click.echo("\n*** DRY RUN MODE ENABLED - No actual trades will be executed ***\n")

        click.echo("*** BLOCKCHAIN EVENT SUBSCRIPTION - Listening to contract events via RPC ***\n")

        if self.settings.dry_run_track_all_market_orders:
            click.echo("*** MARKET-WIDE TRACKING ENABLED - Monitoring ALL orders on market ***")
            if self.settings.source_wallets:
                click.echo(f"Reference wallets ({len(self.settings.source_wallets)}):")
                for wallet in self.settings.source_wallets:
                    click.echo(f"  - {wallet}")
            else:
                click.echo("No reference wallets configured (tracking all market activity)")
        else:
            click.echo(f"Watching {len(self.settings.source_wallets)} source wallets:")
            for wallet in self.settings.source_wallets:
                click.echo(f"  - {wallet}")

        click.echo("\nPress Ctrl+C to stop\n")

        self.running = True

        # Create a task to run the bot
        bot_task = asyncio.create_task(self.bot.run())

        # Create a task to display stats periodically
        stats_task = asyncio.create_task(self._display_stats_periodically())

        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, _frame):
            """Handle shutdown signals."""
            logger.info("Shutdown signal received", signal=sig)
            self.running = False
            # Cancel the bot task
            bot_task.cancel()
            stats_task.cancel()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Wait for bot task to complete (or be cancelled)
            await asyncio.gather(bot_task, stats_task)
        except asyncio.CancelledError:
            logger.info("Bot tasks cancelled")
        finally:
            # Display final statistics
            self._display_final_stats()

    async def _display_stats_periodically(self) -> None:
        """Display statistics periodically."""
        try:
            while self.running:
                await asyncio.sleep(10)  # Update every 10 seconds
                if self.bot and self.running:
                    stats = self.bot.get_statistics()
                    click.echo(
                        f"\n[Bot Stats] Orders: {stats['successful_orders']} placed | "
                        f"{stats['failed_orders']} failed | "
                        f"{stats['rejected_orders']} rejected | "
                        f"{stats['open_orders']} open\n\n",
                        nl=False,
                    )
        except asyncio.CancelledError:
            pass

    def _display_final_stats(self) -> None:
        """Display final statistics."""
        if self.bot:
            click.echo("\n\n=== Final Bot Statistics ===")
            stats = self.bot.get_statistics()
            click.echo("\nBot Wallet Activity:")
            click.echo(f"  Orders placed: {stats['successful_orders']}")
            click.echo(f"  Orders failed: {stats['failed_orders']}")
            click.echo(f"  Orders rejected: {stats['rejected_orders']}")
            click.echo(f"  Orders canceled: {stats['orders_canceled']}")
            click.echo(f"  Open orders: {stats['open_orders']}")
            if stats["successful_orders"] > 0:
                click.echo(f"  Fill rate: {stats['fill_rate']:.1%}")

            click.echo("\nSource Wallet Activity (monitoring):")
            click.echo(f"  Orders detected: {stats['orders_detected']}")
            click.echo(f"  Cancellations detected: {stats['orders_canceled_detected']}")

            click.echo("\nBot stopped.")

    def run(self) -> None:
        """Run the bot using asyncio."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error("Fatal error in bot runner", error=str(e), exc_info=True)
            raise


@click.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    default=".env",
    help="Path to .env file (default: .env)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    help="Logging level (default: INFO)",
)
@click.option(
    "--json-logs",
    is_flag=True,
    help="Output logs in JSON format instead of human-readable format",
)
def main(env_file: str, log_level: str, json_logs: bool) -> None:
    """Kuru Copy Trading Bot - Mirror trades from expert wallets on Monad testnet.

    This bot monitors specified source wallets via blockchain events and automatically
    mirrors their trades on Kuru Exchange with configurable position sizing
    and risk management.

    Configuration is loaded from environment variables or a .env file.
    """
    # Load environment variables
    load_dotenv(env_file)

    # Configure logging first
    configure_logging(log_level=log_level, json_logs=json_logs)

    logger.info(
        "Starting Kuru Copy Trading Bot",
        log_level=log_level,
        json_logs=json_logs,
        env_file=env_file,
    )

    try:
        # Load settings
        settings = Settings()

        # Create and run bot
        runner = BotRunner(settings)
        runner.run()

    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        click.echo(f"Fatal error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
