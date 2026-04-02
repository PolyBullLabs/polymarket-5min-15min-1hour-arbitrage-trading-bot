import { BotConfig, RiskCheckResult } from '../types';
import { HLClient } from './hlClient';
import { getLogger } from '../utils/logger';

export class RiskManager {
  private readonly config: BotConfig;
  private readonly client: HLClient;

  private dailyLoss = 0;
  private dailyResetAt: number; // unix ms of next midnight UTC
  private paused = false;

  constructor(config: BotConfig, client: HLClient) {
    this.config = config;
    this.client = client;
    this.dailyResetAt = this.nextMidnightUtc();
  }

  // ─── Public API ──────────────────────────────────────────────────────────

  isPaused(): boolean {
    this.rolloverIfNeeded();
    return this.paused;
  }

  /**
   * Record a realized PnL change. Negative values accumulate toward daily loss limit.
   */
  recordPnl(pnl: number): void {
    this.rolloverIfNeeded();
    if (pnl < 0) this.dailyLoss += Math.abs(pnl);

    if (this.config.maxDailyLossUsd > 0 && this.dailyLoss >= this.config.maxDailyLossUsd) {
      if (!this.paused) {
        this.paused = true;
        getLogger().warn(
          `Daily loss limit $${this.config.maxDailyLossUsd} reached ` +
            `(total so far: $${this.dailyLoss.toFixed(2)}). Bot paused until midnight UTC.`,
        );
      }
    }
  }

  /**
   * Validate whether opening a new position of a given USD notional is safe.
   */
  async checkNewPosition(coin: string, notionalUsd: number): Promise<RiskCheckResult> {
    this.rolloverIfNeeded();

    if (this.paused) {
      return { allowed: false, reason: 'Bot paused — daily loss limit reached' };
    }

    if (notionalUsd <= 0) {
      return { allowed: false, reason: 'Notional must be > 0' };
    }

    if (notionalUsd > this.config.maxPositionSizeUsd) {
      return {
        allowed: false,
        reason:
          `Notional $${notionalUsd.toFixed(2)} exceeds MAX_POSITION_SIZE_USD ` +
          `($${this.config.maxPositionSizeUsd})`,
      };
    }

    if (this.config.maxTotalExposureUsd > 0) {
      const exposure = await this.client.getTotalNotional();
      if (exposure + notionalUsd > this.config.maxTotalExposureUsd) {
        return {
          allowed: false,
          reason:
            `Adding $${notionalUsd.toFixed(2)} would exceed MAX_TOTAL_EXPOSURE_USD ` +
            `($${this.config.maxTotalExposureUsd}). Current: $${exposure.toFixed(2)}`,
        };
      }
    }

    return { allowed: true };
  }

  /**
   * Cap copy size so notional stays within MAX_POSITION_SIZE_USD.
   */
  capSize(desiredSize: number, price: number, szDecimals: number): number {
    const maxSize = this.config.maxPositionSizeUsd / price;
    const capped = Math.min(desiredSize, maxSize);
    const factor = Math.pow(10, szDecimals);
    return Math.floor(capped * factor) / factor; // floor to avoid exceeding limit
  }

  /**
   * Enforce the configured leverage ceiling.
   */
  capLeverage(requested: number, assetMax: number): number {
    return Math.min(requested, this.config.maxLeverage, assetMax);
  }

  // ─── Private ─────────────────────────────────────────────────────────────

  private rolloverIfNeeded(): void {
    if (Date.now() >= this.dailyResetAt) {
      getLogger().info(`Daily loss counter reset (was $${this.dailyLoss.toFixed(2)}). Bot unpaused.`);
      this.dailyLoss = 0;
      this.paused = false;
      this.dailyResetAt = this.nextMidnightUtc();
    }
  }

  private nextMidnightUtc(): number {
    const d = new Date();
    d.setUTCHours(24, 0, 0, 0);
    return d.getTime();
  }
}
