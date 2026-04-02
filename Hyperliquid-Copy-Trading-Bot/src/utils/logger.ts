import * as winston from 'winston';
import * as path from 'path';
import * as fs from 'fs';

let _logger: winston.Logger | null = null;

const { combine, timestamp, printf, colorize, json } = winston.format;

const consoleFormat = combine(
  colorize({ all: true }),
  timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  printf(({ timestamp: ts, level, message, ...meta }) => {
    const extra = Object.keys(meta).length ? ' ' + JSON.stringify(meta) : '';
    return `[${ts}] ${level}: ${message}${extra}`;
  }),
);

export function createLogger(level: string, toFile: boolean): winston.Logger {
  const transports: winston.transport[] = [
    new winston.transports.Console({ format: consoleFormat }),
  ];

  if (toFile) {
    const logsDir = path.join(process.cwd(), 'logs');
    if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

    transports.push(
      new winston.transports.File({
        filename: path.join(logsDir, 'error.log'),
        level: 'error',
        format: combine(timestamp(), json()),
      }),
      new winston.transports.File({
        filename: path.join(logsDir, 'bot.log'),
        format: combine(timestamp(), json()),
      }),
    );
  }

  _logger = winston.createLogger({ level, transports });
  return _logger;
}

export function getLogger(): winston.Logger {
  if (!_logger) throw new Error('Logger not initialized — call createLogger() first');
  return _logger;
}
