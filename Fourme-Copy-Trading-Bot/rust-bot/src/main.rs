use anyhow::Result;
use log::{info, error};
use std::sync::Arc;
use tokio::signal;

mod config;
mod core;
mod pancakeswap;
mod fourmeme;
mod types;
mod utils;

use config::Config;
use core::CopyTradingBot;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logger
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();

    info!("{}", "=".repeat(60));
    info!("BNB Copy Trading Bot - Rust Version");
    info!("{}", "=".repeat(60));

    // Load configuration
    let config = Config::load()?;
    config.print();

    // Create bot instance
    let bot = Arc::new(CopyTradingBot::new(config).await?);

    // Start the bot
    bot.start().await?;

    info!("Bot is running. Press Ctrl+C to stop.");

    // Wait for shutdown signal
    match signal::ctrl_c().await {
        Ok(()) => {
            info!("Received shutdown signal, stopping bot...");
        }
        Err(err) => {
            error!("Unable to listen for shutdown signal: {}", err);
        }
    }

    // Stop the bot
    bot.stop().await?;
    
    info!("Bot stopped successfully");

    Ok(())
}
