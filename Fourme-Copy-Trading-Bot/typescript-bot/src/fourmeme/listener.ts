import { ethers } from 'ethers';
import { CopyTradingBot } from '../core/bot';
import { Config, FourMemeEvent } from '../types';
import { logger } from '../utils/logger';
import { FOUR_MEME_ABI } from '../utils/constants';
import { executeFourMemeTrade } from './executor';

export function runFourMemeListener(
  bot: CopyTradingBot,
  wsProvider: ethers.WebSocketProvider,
  config: Config
): void {
  logger.info('Setting up Four.meme event listener...');

  const memeInterface = new ethers.Interface(FOUR_MEME_ABI);
  const buyTopic = memeInterface.getEvent('TokenPurchase').topicHash;
  const sellTopic = memeInterface.getEvent('TokenSale').topicHash;

  wsProvider.on('logs', async (log: ethers.Log) => {
    try {
      if (log.topics[0] === buyTopic || log.topics[0] === sellTopic) {
        await handleFourMemeEvent(log, bot, config);
      }
    } catch (error) {
      logger.error('Error processing Four.meme log:', error);
    }
  });

  logger.info('Four.meme listener started');
}

async function handleFourMemeEvent(
  log: ethers.Log,
  bot: CopyTradingBot,
  config: Config
): Promise<void> {
  try {
    const tx = await bot.getProvider().getTransaction(log.transactionHash!);
    if (!tx) {
      logger.warn(`Transaction not found: ${log.transactionHash}`);
      return;
    }

    const initiator = tx.from.toLowerCase();
    
    // Check if we should mirror this trade
    if (!bot.shouldMirrorTrade(initiator)) {
      return;
    }

    const isBuy = log.topics[0] === new ethers.Interface(FOUR_MEME_ABI).getEvent('TokenPurchase').topicHash;
    
    logger.info(`Detected Four.meme ${isBuy ? 'buy' : 'sell'} from target wallet: ${initiator}`);
    logger.info(`Transaction: ${log.transactionHash}`);

    // Parse the event
    const event = parseFourMemeEvent(log, isBuy);
    
    if (event) {
      logger.info(`Parsed ${isBuy ? 'buy' : 'sell'} event`);
      
      // Execute copy trade
      await executeFourMemeTrade(event, bot, config);
    }
  } catch (error) {
    logger.error('Error handling Four.meme event:', error);
  }
}

function parseFourMemeEvent(log: ethers.Log, isBuy: boolean): FourMemeEvent | null {
  try {
    // Parse Four.meme event
    // This is simplified - adjust based on actual contract ABI
    
    return {
      txHash: log.transactionHash!,
      blockNumber: log.blockNumber!,
      initiator: ethers.getAddress(ethers.dataSlice(log.topics[1], 12)),
      dex: 'fourmeme',
      isBuy,
      tokenIn: '',
      tokenOut: '',
      amountIn: 0n,
      amountOut: 0n,
    };
  } catch (error) {
    logger.error('Error parsing Four.meme event:', error);
    return null;
  }
}
