import { ethers } from 'ethers';
import { CopyTradingBot } from '../core/bot';
import { Config, PancakeSwapEvent } from '../types';
import { logger } from '../utils/logger';
import { PANCAKE_PAIR_ABI } from '../utils/constants';
import { executePancakeSwapTrade } from './executor';

export function runPancakeSwapListener(
  bot: CopyTradingBot,
  wsProvider: ethers.WebSocketProvider,
  config: Config
): void {
  logger.info('Setting up PancakeSwap event listener...');

  const pairInterface = new ethers.Interface(PANCAKE_PAIR_ABI);
  const swapTopic = pairInterface.getEvent('Swap').topicHash;

  wsProvider.on('logs', async (log: ethers.Log) => {
    try {
      // Check if this is a Swap event
      if (log.topics[0] === swapTopic) {
        await handlePancakeSwapEvent(log, bot, config);
      }
    } catch (error) {
      logger.error('Error processing PancakeSwap log:', error);
    }
  });

  logger.info('PancakeSwap listener started');
}

async function handlePancakeSwapEvent(
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

    logger.info(`Detected PancakeSwap swap from target wallet: ${initiator}`);
    logger.info(`Transaction: ${log.transactionHash}`);

    // Parse the swap event
    const event = parseSwapEvent(log);
    
    if (event) {
      logger.info(`Parsed swap: ${event.tokenIn} -> ${event.tokenOut}`);
      
      // Execute copy trade
      await executePancakeSwapTrade(event, bot, config);
    }
  } catch (error) {
    logger.error('Error handling PancakeSwap event:', error);
  }
}

function parseSwapEvent(log: ethers.Log): PancakeSwapEvent | null {
  try {
    // Parse the Swap event from the log
    // topics[0] = Swap signature hash
    // topics[1] = sender (indexed)
    // topics[2] = to (indexed)
    // data = amount0In, amount1In, amount0Out, amount1Out

    // This is a simplified parser - in production, you'd want more robust parsing
    const data = ethers.dataSlice(log.data, 0);
    
    return {
      txHash: log.transactionHash!,
      blockNumber: log.blockNumber!,
      initiator: ethers.getAddress(ethers.dataSlice(log.topics[1], 12)),
      dex: 'pancakeswap',
      router: '', // Will be filled in executor
      tokenIn: '',
      tokenOut: '',
      amountIn: 0n,
      amountOut: 0n,
    };
  } catch (error) {
    logger.error('Error parsing swap event:', error);
    return null;
  }
}
