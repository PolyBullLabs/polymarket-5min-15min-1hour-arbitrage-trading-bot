import {
  InfoClient,
  ExchangeClient,
  SubscriptionClient,
  HttpTransport,
  WebSocketTransport,
} from '@nktkas/hyperliquid';
import { privateKeyToAccount } from 'viem/accounts';
import type { ClearinghouseStateResponse } from '@nktkas/hyperliquid';
import { BotConfig, AssetMeta, PerpetualsPosition } from '../types';
import { getLogger } from '../utils/logger';
import { withRetry } from '../utils/sleep';

export class HLClient {
  public readonly info: InfoClient;
  public readonly exchange: ExchangeClient;
  public readonly subs: SubscriptionClient;
  public readonly walletAddress: string;

  private assetMap = new Map<string, AssetMeta>();

  constructor(config: BotConfig) {
    const isTestnet = config.network === 'testnet';

    const httpTransport = new HttpTransport({ isTestnet });
    const wsTransport = new WebSocketTransport({ isTestnet });

    const wallet = privateKeyToAccount(config.privateKey);
    this.walletAddress = wallet.address.toLowerCase();

    this.info = new InfoClient({ transport: httpTransport });
    this.exchange = new ExchangeClient({ transport: httpTransport, wallet });
    this.subs = new SubscriptionClient({ transport: wsTransport });
  }

  // ─── Asset Metadata ──────────────────────────────────────────────────────

  async loadAssetMeta(): Promise<void> {
    const logger = getLogger();
    const meta = await withRetry(() => this.info.meta(), { label: 'loadAssetMeta' });

    this.assetMap.clear();
    meta.universe.forEach((asset, index) => {
      this.assetMap.set(asset.name, {
        name: asset.name,
        index,
        maxLeverage: asset.maxLeverage,
        // szDecimals may not be present in all SDK versions — default to 3
        szDecimals: (asset as unknown as { szDecimals?: number }).szDecimals ?? 3,
      });
    });

    logger.info(`Loaded metadata for ${this.assetMap.size} perpetual markets`);
  }

  getAsset(coin: string): AssetMeta | undefined {
    return this.assetMap.get(coin);
  }

  // ─── Market Data ─────────────────────────────────────────────────────────

  async getMidPrice(coin: string): Promise<number> {
    const mids = await withRetry(() => this.info.allMids(), { label: `getMidPrice(${coin})` });
    const mid = (mids as Record<string, string>)[coin];
    if (!mid) throw new Error(`No mid price available for ${coin}`);
    return parseFloat(mid);
  }

  async getAllMids(): Promise<Record<string, string>> {
    return this.info.allMids() as Promise<Record<string, string>>;
  }

  // ─── Account / Positions ─────────────────────────────────────────────────

  async getClearinghouseState(user: string): Promise<ClearinghouseStateResponse> {
    return withRetry(
      () => this.info.clearinghouseState({ user }),
      { label: `clearinghouseState(${user.slice(0, 8)}...)` },
    );
  }

  async getPositions(user: string): Promise<PerpetualsPosition[]> {
    const state = await this.getClearinghouseState(user);
    return state.assetPositions
      .filter((p) => parseFloat(p.position.szi) !== 0)
      .map((p) => ({
        coin: p.position.coin,
        szi: p.position.szi,
        entryPx: p.position.entryPx,
        positionValue: p.position.positionValue,
        unrealizedPnl: p.position.unrealizedPnl,
        marginUsed: p.position.marginUsed,
        leverage: {
          type: p.position.leverage.type,
          value: p.position.leverage.value,
          rawUsd: p.position.leverage.type === 'isolated' ? p.position.leverage.rawUsd : undefined,
        },
        liquidationPx: p.position.liquidationPx,
        maxLeverage: p.position.maxLeverage,
      }));
  }

  async getAccountValue(user?: string): Promise<number> {
    const state = await this.getClearinghouseState(user ?? this.walletAddress);
    return parseFloat(state.marginSummary.accountValue);
  }

  async getTotalNotional(user?: string): Promise<number> {
    const state = await this.getClearinghouseState(user ?? this.walletAddress);
    return parseFloat(state.marginSummary.totalNtlPos);
  }
}
