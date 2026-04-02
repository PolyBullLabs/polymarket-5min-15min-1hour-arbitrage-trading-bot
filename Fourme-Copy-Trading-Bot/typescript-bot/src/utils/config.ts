import dotenv from 'dotenv';
import { Config } from '../types';
import { logger } from './logger';

dotenv.config();

function getEnv(key: string, defaultValue?: string): string {
  const value = process.env[key];
  if (!value && !defaultValue) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
  return value || defaultValue!;
}

function getBooleanEnv(key: string, defaultValue: boolean): boolean {
  const value = process.env[key];
  if (!value) return defaultValue;
  return value.toLowerCase() === 'true';
}

function getNumberEnv(key: string, defaultValue: number): number {
  const value = process.env[key];
  if (!value) return defaultValue;
  const num = parseFloat(value);
  if (isNaN(num)) {
    logger.warn(`Invalid number for ${key}, using default: ${defaultValue}`);
    return defaultValue;
  }
  return num;
}

export function loadConfig(): Config {
  const copyKeys = getEnv('COPY_KEYS').split(',').map(k => k.trim());
  const targetWallets = getEnv('TARGET_WALLETS')
    .split(',')
    .map(w => w.toLowerCase().trim());

  if (copyKeys.length === 0) {
    throw new Error('No copy keys provided');
  }

  if (targetWallets.length === 0) {
    throw new Error('No target wallets provided');
  }

  const config: Config = {
    wsUrl: getEnv('WS_URL'),
    bscRpcUrl: getEnv('BSC_RPC_URL'),
    wsUrl2: process.env.WS_URL_2,
    bscRpcUrl2: process.env.BSC_RPC_URL_2,
    pancakeSwapRouterAddr: getEnv('PANCAKE_SWAP_ROUTER_ADDR'),
    pancakeSwapFactoryAddr: getEnv('PANCAKE_SWAP_FACTORY_ADDR'),
    fourMemeAddress: getEnv('FOUR_MEME_ADDRESS'),
    copyKeys,
    targetWallets,
    copyPercent: getNumberEnv('COPY_PERCENT', 1.0),
    slippageBps: getNumberEnv('SLIPPAGE_BPS', 300),
    gasMultiplier: getNumberEnv('GAS_MULTIPLIER', 1.0),
    minGasPriceGwei: getNumberEnv('MIN_GAS_PRICE_GWEI', 5),
    enablePancakeSwap: getBooleanEnv('ENABLE_PANCAKESWAP', true),
    enableFourMeme: getBooleanEnv('ENABLE_FOURMEME', true),
    logLevel: getEnv('LOG_LEVEL', 'info'),
  };

  logger.info('Configuration loaded successfully');
  logger.info(`Copy wallets: ${copyKeys.length}`);
  logger.info(`Target wallets: ${targetWallets.length}`);
  logger.info(`Copy percent: ${config.copyPercent}x`);
  logger.info(`PancakeSwap: ${config.enablePancakeSwap ? 'enabled' : 'disabled'}`);
  logger.info(`Four.meme: ${config.enableFourMeme ? 'enabled' : 'disabled'}`);

  return config;
}

export default loadConfig;
