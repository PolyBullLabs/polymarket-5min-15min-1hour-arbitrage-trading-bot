use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::env;
use log::{info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub ws_url: String,
    pub bsc_rpc_url: String,
    pub ws_url2: Option<String>,
    pub bsc_rpc_url2: Option<String>,
    pub pancake_swap_router_addr: String,
    pub four_meme_address: String,
    pub copy_keys: Vec<String>,
    pub target_wallets: Vec<String>,
    pub copy_percent: f64,
    pub copy_percents: Option<Vec<f64>>,
    pub slippage_bps: u64,
    pub gas_multiplier: f64,
    pub min_gas_price_gwei: f64,
    pub gas_limit_override: Option<u64>,
}

impl Config {
    pub fn load() -> Result<Self> {
        dotenv::dotenv().ok();

        let copy_keys: Vec<String> = env::var("COPY_KEYS")?
            .split(',')
            .map(|k| k.trim().to_string())
            .collect();

        let target_wallets: Vec<String> = env::var("TARGET_WALLETS")?
            .split(',')
            .map(|w| w.trim().to_lowercase())
            .collect();

        let copy_percents: Option<Vec<f64>> = env::var("COPY_PERCENTS")
            .ok()
            .map(|s| {
                s.split(',')
                    .map(|v| v.trim().parse::<f64>().unwrap_or(1.0))
                    .collect()
            });

        Ok(Config {
            ws_url: env::var("WS_URL")?,
            bsc_rpc_url: env::var("BSC_RPC_URL")?,
            ws_url2: env::var("WS_URL_2").ok(),
            bsc_rpc_url2: env::var("BSC_RPC_URL_2").ok(),
            pancake_swap_router_addr: env::var("PANCAKE_SWAP_ROUTER_ADDR")?,
            four_meme_address: env::var("FOUR_MEME_ADDRESS")?,
            copy_keys,
            target_wallets,
            copy_percent: env::var("COPY_PERCENT")
                .unwrap_or_else(|_| "1.0".to_string())
                .parse()
                .unwrap_or(1.0),
            copy_percents,
            slippage_bps: env::var("SLIPPAGE_BPS")
                .unwrap_or_else(|_| "300".to_string())
                .parse()
                .unwrap_or(300),
            gas_multiplier: env::var("GAS_MULTIPLIER")
                .unwrap_or_else(|_| "1.0".to_string())
                .parse()
                .unwrap_or(1.0),
            min_gas_price_gwei: env::var("MIN_GAS_PRICE_GWEI")
                .unwrap_or_else(|_| "5".to_string())
                .parse()
                .unwrap_or(5.0),
            gas_limit_override: env::var("GAS_LIMIT_OVERRIDE").ok().and_then(|s| s.parse().ok()),
        })
    }

    pub fn print(&self) {
        info!("Configuration loaded successfully");
        info!("Copy wallets: {}", self.copy_keys.len());
        info!("Target wallets: {}", self.target_wallets.len());
        info!("Copy percent: {}x", self.copy_percent);
        if let Some(percents) = &self.copy_percents {
            info!("Per-wallet copy percents: {:?}", percents);
        }
    }
}
