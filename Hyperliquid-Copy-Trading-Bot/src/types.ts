import type { UserFillsWsEvent } from '@nktkas/hyperliquid';

// ─── Re-export SDK type we use directly ─────────────────────────────────────
export type { UserFillsWsEvent };

// ─── Network / Config ────────────────────────────────────────────────────────

export type Network = 'mainnet' | 'testnet';
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface BotConfig {
  privateKey: `0x${string}`;
  targetTrader: string;

  // Sizing
  sizeMultiplier: number;
  maxPositionSizeUsd: number;
  maxTotalExposureUsd: number;
  maxLeverage: number;

  // Risk
  stopLossPercent: number;
  maxDailyLossUsd: number;

  // Behavior
  copyExistingPositions: boolean;
  closeOnExit: boolean;
  reconcileIntervalMs: number;
  slippageBps: number;

  // Infrastructure
  network: Network;
  logLevel: LogLevel;
  logToFile: boolean;
}

// ─── Asset Metadata ──────────────────────────────────────────────────────────

export interface AssetMeta {
  name: string;
  index: number;       // numeric asset index used in exchange API
  maxLeverage: number;
  szDecimals: number;  // decimal places for size strings
}

// ─── Positions (SDK shape) ───────────────────────────────────────────────────

export interface LeverageInfo {
  type: 'cross' | 'isolated';
  value: number;
  rawUsd?: string;
}

export interface PerpetualsPosition {
  coin: string;
  szi: string;          // signed size: + = long, - = short
  entryPx: string;
  positionValue: string;
  unrealizedPnl: string;
  marginUsed: string;
  leverage: LeverageInfo;
  liquidationPx: string | null;
  maxLeverage: number;
}

// ─── Fill (from SDK UserFillsEvent.fills) ────────────────────────────────────

export type FillSide = 'B' | 'A';  // B = buy/long, A = ask/sell/short

export interface TraderFill {
  coin: string;
  px: string;
  sz: string;
  side: FillSide;
  time: number;
  dir: string;          // "Open Long" | "Close Long" | "Open Short" | "Close Short"
  closedPnl: string;
  hash: string;
  oid: number;
  crossed: boolean;
  fee: string;
  tid: number;
  startPosition: string;
  feeToken: string;
}

// ─── Order Execution ─────────────────────────────────────────────────────────

export interface CopyOrderParams {
  coin: string;
  assetIndex: number;
  isBuy: boolean;
  size: number;
  price: number;
  isReduceOnly: boolean;
  leverage: number;
  reason: string;
}

export interface OrderResult {
  success: boolean;
  orderId?: number;
  error?: string;
}

// ─── Risk ────────────────────────────────────────────────────────────────────

export interface RiskCheckResult {
  allowed: boolean;
  reason?: string;
}

// ─── Stats ───────────────────────────────────────────────────────────────────

export interface BotStats {
  startTime: Date;
  tradesCopied: number;
  tradesFailed: number;
  tradeSkipped: number;
  copiedCoins: Set<string>;
}
