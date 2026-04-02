import { loadConfig } from './utils/config';
import { logger } from './utils/logger';
import { CopyTradingBot } from './core/bot';

async function main() {
  try {
    logger.info('='.repeat(60));
    logger.info('BNB Copy Trading Bot - TypeScript Version');
    logger.info('='.repeat(60));
    
    // Load configuration
    const config = loadConfig();
    
    // Create bot instance
    const bot = new CopyTradingBot(config);
    
    // Start the bot
    await bot.start();
    
    // Handle graceful shutdown
    process.on('SIGINT', async () => {
      logger.info('Received SIGINT, shutting down gracefully...');
      await bot.stop();
      process.exit(0);
    });
    
    process.on('SIGTERM', async () => {
      logger.info('Received SIGTERM, shutting down gracefully...');
      await bot.stop();
      process.exit(0);
    });
    
    // Keep the process alive
    logger.info('Bot is running. Press Ctrl+C to stop.');
    
  } catch (error) {
    logger.error('Fatal error:', error);
    process.exit(1);
  }
}

// Start the application
main();
