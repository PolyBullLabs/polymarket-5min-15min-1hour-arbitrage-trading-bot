import { getLogger } from './logger';

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry an async function up to maxAttempts times with exponential back-off.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  opts: { maxAttempts?: number; delayMs?: number; label?: string } = {},
): Promise<T> {
  const { maxAttempts = 3, delayMs = 800, label = 'operation' } = opts;

  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < maxAttempts) {
        const wait = delayMs * attempt; // linear back-off
        try {
          getLogger().warn(`[retry] ${label} failed (${attempt}/${maxAttempts}), retrying in ${wait}ms`, {
            err: err instanceof Error ? err.message : String(err),
          });
        } catch {
          // logger may not be initialized during very early startup
          console.warn(`[retry] ${label} failed (${attempt}/${maxAttempts}), retrying in ${wait}ms`);
        }
        await sleep(wait);
      }
    }
  }
  throw lastError;
}
