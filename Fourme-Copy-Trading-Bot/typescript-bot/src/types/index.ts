export interface Config {
  wsUrl: string;
  bscRpcUrl: string;
  wsUrl2?: string;
  bscRpcUrl2?: string;
  pancakeSwapRouterAddr: string;
  pancakeSwapFactoryAddr: string;
  fourMemeAddress: string;
  copyKeys: string[];
  targetWallets: string[];
  copyPercent: number;
  slippageBps: number;
  gasMultiplier: number;
  minGasPriceGwei: number;
  enablePancakeSwap: boolean;
  enableFourMeme: boolean;
  logLevel: string;
}

export interface TradeEvent {
  txHash: string;
  blockNumber: number;
  initiator: string;
  dex: 'pancakeswap' | 'fourmeme';
  tokenIn: string;
  tokenOut: string;
  amountIn: bigint;
  amountOut: bigint;
  path?: string[];
}

export interface PancakeSwapEvent extends TradeEvent {
  dex: 'pancakeswap';
  router: string;
}

export interface FourMemeEvent extends TradeEvent {
  dex: 'fourmeme';
  isBuy: boolean;
}

export interface CopyWallet {
  address: string;
  privateKey: string;
  nonce: number;
}

export interface ExecutionResult {
  success: boolean;
  txHash?: string;
  error?: string;
  wallet: string;
}

export interface ApprovalStatus {
  token: string;
  spender: string;
  approved: boolean;
  allowance: bigint;
}
