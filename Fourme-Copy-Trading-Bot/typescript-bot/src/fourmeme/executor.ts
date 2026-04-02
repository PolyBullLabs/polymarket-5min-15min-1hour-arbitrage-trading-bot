import { ethers } from 'ethers';
import { CopyTradingBot } from '../core/bot';
import { Config, FourMemeEvent, ExecutionResult } from '../types';
import { logger } from '../utils/logger';
import { FOUR_MEME_ABI, FOUR_MEME_GAS_LIMIT } from '../utils/constants';

export async function executeFourMemeTrade(
  event: FourMemeEvent,
  bot: CopyTradingBot,
  config: Config
): Promise<void> {
  const copyWallets = bot.getCopyWallets();
  
  logger.info(`Executing Four.meme ${event.isBuy ? 'buy' : 'sell'} for ${copyWallets.length} copy wallet(s)`);

  for (const copyWallet of copyWallets) {
    try {
      const result = await executeSingleWalletTrade(copyWallet, event, bot, config);
      
      if (result.success) {
        logger.info(`Trade executed successfully: ${result.txHash}`);
        await bot.updateNonce(copyWallet.address);
      } else {
        logger.error(`Trade failed: ${result.error}`);
      }
    } catch (error) {
      logger.error(`Error executing trade for ${copyWallet.address}:`, error);
    }
  }
}

async function executeSingleWalletTrade(
  wallet: any,
  event: FourMemeEvent,
  bot: CopyTradingBot,
  config: Config
): Promise<ExecutionResult> {
  try {
    const walletSigner = new ethers.Wallet(wallet.privateKey, bot.getProvider());
    
    // Calculate copy amount
    const copyAmount = (event.amountIn * BigInt(Math.floor(config.copyPercent * 100))) / 100n;
    
    logger.info(`Executing ${event.isBuy ? 'buy' : 'sell'} for wallet ${wallet.address}`);
    logger.info(`Amount: ${copyAmount}`);

    // Get Four.meme contract
    const fourMeme = new ethers.Contract(
      config.fourMemeAddress,
      FOUR_MEME_ABI,
      walletSigner
    );

    let tx: ethers.ContractTransactionResponse;

    if (event.isBuy) {
      // Execute buy
      tx = await fourMeme.buyTokens({
        value: copyAmount,
        gasLimit: FOUR_MEME_GAS_LIMIT,
      });
    } else {
      // Execute sell
      tx = await fourMeme.sellTokens(copyAmount, {
        gasLimit: FOUR_MEME_GAS_LIMIT,
      });
    }

    const receipt = await tx.wait();
    
    return {
      success: true,
      txHash: receipt.hash,
      wallet: wallet.address,
    };
  } catch (error) {
    logger.error(`Trade execution error:`, error);
    return {
      success: false,
      wallet: wallet.address,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}
