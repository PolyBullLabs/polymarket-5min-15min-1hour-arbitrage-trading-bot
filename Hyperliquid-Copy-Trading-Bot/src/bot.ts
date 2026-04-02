import type { UserFillsWsEvent } from '@nktkas/hyperliquid';
import { BotConfig, TraderFill, BotStats, PerpetualsPosition } from './types';
import { HLClient } from './services/hlClient';
import { OrderExecutor } from './services/orderExecutor';
import { RiskManager } from './services/riskManager';
import { getLogger } from './utils/logger';
import { aggressiveBuyPrice, aggressiveSellPrice, notionalUsd, pctDiff } from './utils/math';
import { sleep } from './utils/sleep';
import { logger } from 'ts-moduler';

/** Reconcile if our size differs from expected by more than this %. */
const RECONCILE_THRESHOLD_PCT = 5;

/** Skip copy orders below this USD notional (avoids dust). */
const MIN_NOTIONAL_USD = 5;

export class CopyTradingBot {
  private readonly config: BotConfig;
  private readonly client: HLClient;
  private readonly executor: OrderExecutor;
  private readonly risk: RiskManager;

  private running = false;
  private reconcileTimer?: ReturnType<typeof setInterval>;

  private stats: BotStats = {
    startTime: new Date(),
    tradesCopied: 0,
    tradesFailed: 0,
    tradeSkipped: 0,
    copiedCoins: new Set<string>(),
  };

  /**
   * Tracks coins whose positions we actively manage.
   * Prevents interfering with positions opened outside this bot.
   */
  private managedCoins = new Set<string>();

  constructor(config: BotConfig) {
    this.config = config;
    this.client = new HLClient(config);
    this.executor = new OrderExecutor(this.client);
    this.risk = new RiskManager(config, this.client);
  }

  // ─── Public lifecycle ────────────────────────────────────────────────────

  async start(): Promise<void> {
    const logger = getLogger();
    this.printBanner();

    // Load perpetual market metadata (asset indices, szDecimals, etc.)
    await this.client.loadAssetMeta();

    // Verify our account has sufficient balance
    const accountValue = await this.client.getAccountValue();
    logger.info(`Our account value : $${accountValue.toFixed(2)}`);
    if (accountValue < 10) {
      throw new Error(
        `Insufficient account balance ($${accountValue.toFixed(2)}). Deposit USDC before starting.`,
      );
    }

    // Inspect target trader's current positions
    const targetPositions = await this.client.getPositions(this.config.targetTrader);
    logger.info(`Target trader open positions: ${targetPositions.length}`);
    for (const p of targetPositions) {
      const szi = parseFloat(p.szi);
      logger.info(
        `  ${p.coin.padEnd(8)} ${szi > 0 ? 'LONG ' : 'SHORT'} ` +
          `${Math.abs(szi)} @ entry ${p.entryPx}  (${p.leverage.type} ${p.leverage.value}×)`,
      );
    }

    if (this.config.copyExistingPositions && targetPositions.length > 0) {
      logger.info('COPY_EXISTING_POSITIONS=true — opening copies of current positions...');
      await this.copyExistingPositions(targetPositions);
    }

    this.running = true;
    this.startReconciliation();

    // Subscribe to live fills from the target trader
    logger.info(`Subscribing to live fills for ${this.config.targetTrader}...`);
    await this.subscribeFills();

    logger.info('Bot is live. Press Ctrl+C to stop.\n');
  }

  async stop(): Promise<void> {
    const logger = getLogger();
    this.running = false;

    if (this.reconcileTimer) clearInterval(this.reconcileTimer);

    this.printStats();

    if (this.config.closeOnExit) {
      logger.info('CLOSE_ON_EXIT=true — closing all managed positions...');
      await this.executor.closeAllPositions();
    }

    logger.info('Bot stopped.');
  }

  // ─── WebSocket subscription ──────────────────────────────────────────────

  private async subscribeFills(): Promise<void> {
    await this.client.subs.userFills(
      { user: this.config.targetTrader },
      (event: UserFillsWsEvent) => {
        if (event.isSnapshot) {
          getLogger().debug(`Skipping ${event.fills.length} historical fill(s) (snapshot)`);
          return;
        }

        // Process each fill sequentially (don't flood the exchange API)
        (async () => {
          for (const fill of event.fills) {
            if (!this.running) return;
            await this.processFill(fill as unknown as TraderFill).catch((err) => {
              getLogger().error(`Unhandled error processing fill for ${(fill as { coin: string }).coin}`, {
                err: err instanceof Error ? err.message : String(err),
              });
            });
          }
        })();
      },
    );
  }

  // ─── Fill processing ─────────────────────────────────────────────────────

  private async processFill(fill: TraderFill): Promise<void> {
    const logger = getLogger();

    // Skip spot markets — perps use plain names ("BTC"); spot uses "@0" or "BTC/USDC"
    if (fill.coin.includes('/') || fill.coin.startsWith('@')) {
      logger.debug(`Skipping spot fill: ${fill.coin}`);
      return;
    }

    if (this.risk.isPaused()) {
      logger.warn(`Skipping ${fill.coin} fill: bot is paused`);
      this.stats.tradeSkipped++;
      return;
    }

    const isOpen = fill.dir.toLowerCase().includes('open');
    const isClose = fill.dir.toLowerCase().includes('close');
    const isBuy = fill.side === 'B';
    const fillSize = parseFloat(fill.sz);

    logger.info(
      `◆ TARGET FILL  ${fill.coin.padEnd(8)} [${fill.dir.padEnd(12)}] ` +
        `sz=${fillSize}  px=${fill.px}  tx=${fill.hash.slice(0, 10)}...`,
    );

    const asset = this.client.getAsset(fill.coin);
    if (!asset) {
      logger.warn(`No asset metadata for ${fill.coin} — skipping`);
      this.stats.tradeSkipped++;
      return;
    }

    // Get mid price for IOC order pricing
    let mid: number;
    try {
      mid = await this.client.getMidPrice(fill.coin);
    } catch {
      logger.warn(`Cannot get mid price for ${fill.coin}, using fill price`);
      mid = parseFloat(fill.px);
    }

    // ── Calculate copy size ───────────────────────────────────────────────

    let copySize: number;

    if (isClose) {
      copySize = await this.calcCloseSize(fill, asset.szDecimals);
    } else if (isOpen) {
      const raw = fillSize * this.config.sizeMultiplier;
      copySize = this.risk.capSize(raw, mid, asset.szDecimals);
    } else {
      logger.debug(`Unknown fill dir "${fill.dir}" — skipping`);
      this.stats.tradeSkipped++;
      return;
    }

    if (copySize <= 0) {
      logger.debug(`Copy size is 0 for ${fill.coin} — nothing to do`);
      this.stats.tradeSkipped++;
      return;
    }

    // ── Risk check (for opening orders only) ─────────────────────────────

    if (isOpen) {
      const notional = notionalUsd(copySize, mid);

      if (notional < MIN_NOTIONAL_USD) {
        logger.debug(`${fill.coin}: notional $${notional.toFixed(2)} below minimum — skipping`);
        this.stats.tradeSkipped++;
        return;
      }

      const risk = await this.risk.checkNewPosition(fill.coin, notional);
      if (!risk.allowed) {
        logger.warn(`Risk blocked ${fill.coin}: ${risk.reason}`);
        this.stats.tradeSkipped++;
        return;
      }

      // Sync leverage before entering position
      await this.syncLeverage(fill.coin, asset.index, asset.maxLeverage);
      this.managedCoins.add(fill.coin);
    }

    // ── Build aggressive IOC price ────────────────────────────────────────

    const price = isBuy
      ? aggressiveBuyPrice(mid, this.config.slippageBps)
      : aggressiveSellPrice(mid, this.config.slippageBps);

    // ── Execute ───────────────────────────────────────────────────────────

    const result = await this.executor.placeOrder({
      coin: fill.coin,
      assetIndex: asset.index,
      isBuy,
      size: copySize,
      price,
      isReduceOnly: isClose,
      leverage: 1, // already set by syncLeverage above
      reason: `copy-${fill.dir.toLowerCase().replace(/ /g, '-')}`,
    });

    if (result.success) {
      this.stats.tradesCopied++;
      this.stats.copiedCoins.add(fill.coin);
      if (isClose) {
        this.risk.recordPnl(parseFloat(fill.closedPnl));
      }
    } else {
      this.stats.tradesFailed++;
    }
  }

  // ─── Close-size calculation ───────────────────────────────────────────────

  /**
   * When the target closes X% of their position, we close the same X% of ours.
   * Uses fill.startPosition (position size before fill) to compute the percentage.
   */
  private async calcCloseSize(fill: TraderFill, szDecimals: number): Promise<number> {
    const logger = getLogger();
    const fillSize = parseFloat(fill.sz);
    const startPosition = parseFloat(fill.startPosition);

    if (startPosition === 0) {
      return fillSize * this.config.sizeMultiplier;
    }

    const closePercent = fillSize / Math.abs(startPosition);

    const ourPositions = await this.client.getPositions(this.client.walletAddress);
    const ourPos = ourPositions.find((p) => p.coin === fill.coin);

    if (!ourPos) {
      logger.debug(`No open position in ${fill.coin} to close`);
      return 0;
    }

    const ourSize = Math.abs(parseFloat(ourPos.szi));
    const closeSize = ourSize * closePercent;

    logger.debug(
      `${fill.coin} close: target closed ${(closePercent * 100).toFixed(1)}% ` +
        `→ closing ${closeSize.toFixed(szDecimals)} of our ${ourSize}`,
    );

    return closeSize;
  }

  // ─── Copy existing positions ──────────────────────────────────────────────

  private async copyExistingPositions(targetPositions: PerpetualsPosition[]): Promise<void> {
    const logger = getLogger();
    const mids = await this.client.getAllMids();

    for (const pos of targetPositions) {
      const szi = parseFloat(pos.szi);
      if (szi === 0) continue;

      const asset = this.client.getAsset(pos.coin);
      if (!asset) {
        logger.warn(`No metadata for ${pos.coin} — skipping`);
        continue;
      }

      const mid = parseFloat(mids[pos.coin] ?? '0');
      if (mid === 0) {
        logger.warn(`No mid price for ${pos.coin} — skipping`);
        continue;
      }

      const isBuy = szi > 0;
      const rawSize = Math.abs(szi) * this.config.sizeMultiplier;
      const copySize = this.risk.capSize(rawSize, mid, asset.szDecimals);
      const notional = notionalUsd(copySize, mid);

      const risk = await this.risk.checkNewPosition(pos.coin, notional);
      if (!risk.allowed) {
        logger.warn(`Skipping existing position ${pos.coin}: ${risk.reason}`);
        continue;
      }

      const leverage = this.risk.capLeverage(pos.leverage.value, asset.maxLeverage);
      await this.executor.setLeverage(asset.index, leverage);

      const price = isBuy
        ? aggressiveBuyPrice(mid, this.config.slippageBps)
        : aggressiveSellPrice(mid, this.config.slippageBps);

      const result = await this.executor.placeOrder({
        coin: pos.coin,
        assetIndex: asset.index,
        isBuy,
        size: copySize,
        price,
        isReduceOnly: false,
        leverage,
        reason: 'copy-existing',
      });

      if (result.success) {
        this.managedCoins.add(pos.coin);
        this.stats.tradesCopied++;
      } else {
        this.stats.tradesFailed++;
      }

      await sleep(500); // rate limit buffer
    }
  }

  // ─── Leverage sync ────────────────────────────────────────────────────────

  private async syncLeverage(coin: string, assetIndex: number, assetMaxLeverage: number): Promise<void> {
    try {
      const targetPositions = await this.client.getPositions(this.config.targetTrader);
      const tp = targetPositions.find((p) => p.coin === coin);
      const targetLeverage = tp?.leverage.value ?? 1;
      const capped = this.risk.capLeverage(targetLeverage, assetMaxLeverage);
      await this.executor.setLeverage(assetIndex, capped);
    } catch {
      getLogger().debug(`Could not sync leverage for ${coin} — proceeding with default`);
    }
  }

  // ─── Reconciliation ───────────────────────────────────────────────────────

  private startReconciliation(): void {
    const logger = getLogger();
    this.reconcileTimer = setInterval(async () => {
      if (!this.running) return;
      try {
        await this.reconcile();
      } catch (err) {
        logger.error('Reconciliation error', {
          err: err instanceof Error ? err.message : String(err),
        });
      }
    }, this.config.reconcileIntervalMs);
    logger.info(`Reconciliation scheduled every ${this.config.reconcileIntervalMs / 1000}s`);
  }

  /**
   * Compare our positions vs. the target's (scaled).
   * Close any managed position that the target has already exited.
   * Log size drift for monitoring.
   */
  private async reconcile(): Promise<void> {
    const logger = getLogger();

    const [targetPositions, ourPositions] = await Promise.all([
      this.client.getPositions(this.config.targetTrader),
      this.client.getPositions(this.client.walletAddress),
    ]);

    const targetMap = new Map(targetPositions.map((p) => [p.coin, p]));
    const ourMap = new Map(ourPositions.map((p) => [p.coin, p]));

    for (const coin of this.managedCoins) {
      const ourPos = ourMap.get(coin);
      if (!ourPos) continue; // already flat

      if (!targetMap.has(coin)) {
        // Target exited — close ours too
        logger.warn(`[reconcile] Target exited ${coin} but we still hold it — closing...`);
        const asset = this.client.getAsset(coin);
        if (!asset) continue;

        const szi = parseFloat(ourPos.szi);
        const isLong = szi > 0;
        const mid = await this.client.getMidPrice(coin).catch(() => 0);
        if (mid === 0) continue;

        await this.executor.placeOrder({
          coin,
          assetIndex: asset.index,
          isBuy: !isLong,
          size: Math.abs(szi),
          price: isLong
            ? aggressiveSellPrice(mid, this.config.slippageBps * 2)
            : aggressiveBuyPrice(mid, this.config.slippageBps * 2),
          isReduceOnly: true,
          leverage: ourPos.leverage.value,
          reason: 'reconcile-close',
        });
      } else {
        // Target still has position — check for size drift
        const targetPos = targetMap.get(coin)!;
        const expected = Math.abs(parseFloat(targetPos.szi)) * this.config.sizeMultiplier;
        const actual = Math.abs(parseFloat(ourPos.szi));
        const drift = pctDiff(actual, expected);
        if (drift > RECONCILE_THRESHOLD_PCT) {
          logger.warn(
            `[reconcile] ${coin} size drift ${drift.toFixed(1)}%: ` +
              `expected ~${expected.toFixed(4)}, have ${actual.toFixed(4)}`,
          );
        }
      }
    }

    const accountValue = await this.client.getAccountValue();
    logger.info(
      `[reconcile] Account=$${accountValue.toFixed(2)} | ` +
        `Copied=${this.stats.tradesCopied} Failed=${this.stats.tradesFailed} ` +
        `Skipped=${this.stats.tradeSkipped} | ` +
        `Managed: [${[...this.managedCoins].join(', ') || 'none'}]`,
    );
  }

  // ─── Display ─────────────────────────────────────────────────────────────

  private printBanner(): void {
    const logger = getLogger();
    const sep = '═'.repeat(62);
    logger.info(sep);
    logger.info('  Hyperliquid Perpetual Copy Trading Bot');
    logger.info(sep);
    logger.info(`  Network          : ${this.config.network}`);
    logger.info(`  Target trader    : ${this.config.targetTrader}`);
    logger.info(`  Our wallet       : ${this.client.walletAddress}`);
    logger.info(`  Size multiplier  : ${this.config.sizeMultiplier}×`);
    logger.info(`  Max pos size     : $${this.config.maxPositionSizeUsd}`);
    logger.info(`  Max total exp.   : $${this.config.maxTotalExposureUsd}`);
    logger.info(`  Max leverage     : ${this.config.maxLeverage}×`);
    logger.info(`  Slippage         : ${this.config.slippageBps} bps`);
    logger.info(`  Copy existing    : ${this.config.copyExistingPositions}`);
    logger.info(`  Close on exit    : ${this.config.closeOnExit}`);
    logger.info(sep);
  }

  private printStats(): void {
    const logger = getLogger();
    const upMs = Date.now() - this.stats.startTime.getTime();
    const h = Math.floor(upMs / 3_600_000);
    const m = Math.floor((upMs % 3_600_000) / 60_000);
    const sep = '═'.repeat(62);
    logger.info(sep);
    logger.info('  Final Statistics');
    logger.info(sep);
    logger.info(`  Uptime           : ${h}h ${m}m`);
    logger.info(`  Trades copied    : ${this.stats.tradesCopied}`);
    logger.info(`  Trades failed    : ${this.stats.tradesFailed}`);
    logger.info(`  Trades skipped   : ${this.stats.tradeSkipped}`);
    logger.info(`  Coins traded     : ${[...this.stats.copiedCoins].join(', ') || 'none'}`);
    logger.info(sep);
  }
}
