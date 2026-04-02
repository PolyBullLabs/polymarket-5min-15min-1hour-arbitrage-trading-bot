/**
 * Round a number to a given number of decimal places.
 */
export function roundDecimals(value: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

/**
 * Format a size value as a string with the correct decimal precision.
 */
export function formatSize(size: number, szDecimals: number): string {
  return roundDecimals(size, szDecimals).toFixed(szDecimals);
}

/**
 * Format a price string appropriate for the Hyperliquid exchange.
 * Prices < 1     → 6 decimal places
 * Prices 1–9     → 4 decimal places
 * Prices 10–999  → 2 decimal places
 * Prices ≥ 1000  → 1 decimal place
 */
export function formatPrice(price: number): string {
  if (price < 1) return price.toFixed(6);
  if (price < 10) return price.toFixed(4);
  if (price < 1000) return price.toFixed(2);
  return price.toFixed(1);
}

/**
 * Apply positive slippage to get an aggressive buy price.
 * Ensures IOC market buy orders fill immediately.
 */
export function aggressiveBuyPrice(midPrice: number, slippageBps: number): number {
  return midPrice * (1 + slippageBps / 10_000);
}

/**
 * Apply negative slippage to get an aggressive sell price.
 * Ensures IOC market sell orders fill immediately.
 */
export function aggressiveSellPrice(midPrice: number, slippageBps: number): number {
  return midPrice * (1 - slippageBps / 10_000);
}

/**
 * Notional USD value of a position.
 */
export function notionalUsd(size: number, price: number): number {
  return Math.abs(size) * price;
}

/**
 * Absolute percentage difference between two numbers.
 */
export function pctDiff(a: number, b: number): number {
  if (b === 0) return a === 0 ? 0 : 100;
  return Math.abs((a - b) / b) * 100;
}

/**
 * Clamp a value between min and max.
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
