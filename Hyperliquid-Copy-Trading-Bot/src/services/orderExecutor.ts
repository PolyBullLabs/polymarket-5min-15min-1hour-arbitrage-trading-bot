import { HLClient } from './hlClient';
import { CopyOrderParams, OrderResult } from '../types';
import { getLogger } from '../utils/logger';
import { formatSize, formatPrice } from '../utils/math';
import { withRetry, sleep } from '../utils/sleep';

export class OrderExecutor {
  private readonly client: HLClient;

  constructor(client: HLClient) {
    this.client = client;
  }

  // ─── Leverage ─────────────────────────────────────────────────────────────

  async setLeverage(assetIndex: number, leverage: number, isCross = true): Promise<void> {
    const logger = getLogger();
    try {
      await withRetry(
        () => this.client.exchange.updateLeverage({ asset: assetIndex, isCross, leverage }),
        { maxAttempts: 3, delayMs: 500, label: `setLeverage(asset=${assetIndex}, ${leverage}x)` },
      );
      logger.debug(`Leverage set: asset=${assetIndex} ${leverage}x ${isCross ? 'cross' : 'isolated'}`);
    } catch (err) {
      logger.warn(`Failed to update leverage for asset ${assetIndex}`, {
        err: err instanceof Error ? err.message : String(err),
      });
    }
  }

  // ─── Orders ───────────────────────────────────────────────────────────────

  async placeOrder(params: CopyOrderParams): Promise<OrderResult> {
    const logger = getLogger();
    const asset = this.client.getAsset(params.coin);

    if (!asset) {
      return { success: false, error: `Unknown asset: ${params.coin}` };
    }

    const sizeStr = formatSize(params.size, asset.szDecimals);
    const priceStr = formatPrice(params.price);

    if (parseFloat(sizeStr) === 0) {
      return { success: false, error: `Size rounds to 0 for ${params.coin} (raw: ${params.size})` };
    }

    const dir = params.isBuy ? 'BUY ' : 'SELL';
    const mode = params.isReduceOnly ? '[reduce-only]' : '[open    ]';
    logger.info(`→ ${params.coin.padEnd(8)} ${dir} ${sizeStr.padStart(12)} @ ${priceStr.padStart(12)} ${mode}  (${params.reason})`);

    try {
      const result = await withRetry(
        () =>
          this.client.exchange.order({
            orders: [
              {
                a: asset.index,
                b: params.isBuy,
                p: priceStr,
                s: sizeStr,
                r: params.isReduceOnly,
                // IOC = immediate-or-cancel → acts as a market order
                t: { limit: { tif: 'Ioc' } },
              },
            ],
            grouping: 'na',
          }),
        { maxAttempts: 3, delayMs: 800, label: `placeOrder(${params.coin})` },
      );

      for (const status of result.response.data.statuses) {
        if (typeof status === 'string') {
          // "waitingForFill" | "waitingForTrigger" — treat as pending success
          logger.info(`✓ ${params.coin} ${dir} ${sizeStr} — status: ${status}`);
          return { success: true };
        }
        if ('error' in status) {
          const errMsg = String((status as { error: unknown }).error);
          logger.error(`✗ Order rejected: ${params.coin} — ${errMsg}`);
          return { success: false, error: errMsg };
        }
        if ('filled' in status) {
          logger.info(
            `✓ ${params.coin} ${dir} ${sizeStr} FILLED @ avg ${status.filled.avgPx} (oid=${status.filled.oid})`,
          );
          return { success: true, orderId: status.filled.oid };
        }
        if ('resting' in status) {
          logger.info(`✓ ${params.coin} ${dir} ${sizeStr} resting (oid=${status.resting.oid})`);
          return { success: true, orderId: status.resting.oid };
        }
      }

      return { success: true };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(`Order failed after retries: ${params.coin} — ${msg}`);
      return { success: false, error: msg };
    }
  }

  // ─── Close All ────────────────────────────────────────────────────────────

  /**
   * Close every open position with aggressive IOC orders.
   * Called on graceful shutdown when CLOSE_ON_EXIT=true.
   */
  async closeAllPositions(): Promise<void> {
    const logger = getLogger();
    logger.info('Closing all open positions...');

    const positions = await this.client.getPositions(this.client.walletAddress);
    if (positions.length === 0) {
      logger.info('No open positions to close.');
      return;
    }

    const mids = await this.client.getAllMids();

    for (const pos of positions) {
      const szi = parseFloat(pos.szi);
      if (szi === 0) continue;

      const asset = this.client.getAsset(pos.coin);
      if (!asset) {
        logger.warn(`Cannot close ${pos.coin}: asset metadata not found`);
        continue;
      }

      const mid = parseFloat(mids[pos.coin] ?? '0');
      if (mid === 0) {
        logger.warn(`Cannot close ${pos.coin}: no mid price`);
        continue;
      }

      const isLong = szi > 0;
      // 5% slippage on shutdown to guarantee immediate fill
      const closePrice = isLong ? mid * 0.95 : mid * 1.05;

      await this.placeOrder({
        coin: pos.coin,
        assetIndex: asset.index,
        isBuy: !isLong,
        size: Math.abs(szi),
        price: closePrice,
        isReduceOnly: true,
        leverage: pos.leverage.value,
        reason: 'shutdown-close',
      });

      await sleep(300);
    }
  }
}
