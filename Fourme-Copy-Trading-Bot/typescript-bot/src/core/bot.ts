import { ethers } from 'ethers';
import { Config, TradeEvent, CopyWallet, ExecutionResult } from '../types';
import { logger } from '../utils/logger';
import { runPancakeSwapListener } from '../pancakeswap/listener';
import { runFourMemeListener } from '../fourmeme/listener';

export class CopyTradingBot {
  private config: Config;
  private provider: ethers.JsonRpcProvider;
  private wsProvider: ethers.WebSocketProvider;
  private copyWallets: CopyWallet[] = [];

  constructor(config: Config) {
    this.config = config;
    this.provider = new ethers.JsonRpcProvider(config.bscRpcUrl);
    this.wsProvider = new ethers.WebSocketProvider(config.wsUrl);
    this.initializeCopyWallets();
  }

  private initializeCopyWallets(): void {
    logger.info('Initializing copy wallets...');
    for (const privateKey of this.config.copyKeys) {
      const wallet = new ethers.Wallet(privateKey, this.provider);
      this.copyWallets.push({
        address: wallet.address.toLowerCase(),
        privateKey,
        nonce: 0,
      });
      logger.info(`Copy wallet initialized: ${wallet.address}`);
    }
  }

  public async start(): Promise<void> {
    logger.info('Starting BNB Copy Trading Bot...');
    
    try {
      // Subscribe to PancakeSwap events
      if (this.config.enablePancakeSwap) {
        logger.info('Starting PancakeSwap listener...');
        runPancakeSwapListener(this, this.wsProvider, this.config);
      }

      // Subscribe to Four.meme events
      if (this.config.enableFourMeme) {
        logger.info('Starting Four.meme listener...');
        runFourMemeListener(this, this.wsProvider, this.config);
      }

      logger.info('Bot started successfully');
    } catch (error) {
      logger.error('Failed to start bot:', error);
      throw error;
    }
  }

  public async stop(): Promise<void> {
    logger.info('Stopping bot...');
    await this.wsProvider.destroy();
    logger.info('Bot stopped');
  }

  public shouldMirrorTrade(initiator: string): boolean {
    const initiatorLower = initiator.toLowerCase();
    
    // Don't mirror our own trades
    if (this.copyWallets.some(w => w.address === initiatorLower)) {
      return false;
    }

    // Only mirror trades from target wallets
    return this.config.targetWallets.includes(initiatorLower);
  }

  public getCopyWallets(): CopyWallet[] {
    return this.copyWallets;
  }

  public getConfig(): Config {
    return this.config;
  }

  public getProvider(): ethers.JsonRpcProvider {
    return this.provider;
  }

  public async updateNonce(walletAddress: string): Promise<void> {
    const wallet = this.copyWallets.find(w => w.address === walletAddress);
    if (wallet) {
      wallet.nonce++;
    }
  }

  public async getBalance(address: string): Promise<bigint> {
    return await this.provider.getBalance(address);
  }
}

export default CopyTradingBot;
