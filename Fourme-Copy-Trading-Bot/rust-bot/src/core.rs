use anyhow::Result;
use ethers::{
    providers::{Provider, Ws},
    types::Address,
    utils::parse_ether,
};
use log::{info, error};
use std::sync::Arc;

use crate::config::Config;
use crate::types::CopyWallet;

pub struct CopyTradingBot {
    config: Config,
    provider: Arc<Provider<Ws>>,
    copy_wallets: Vec<CopyWallet>,
}

impl CopyTradingBot {
    pub async fn new(config: Config) -> Result<Self> {
        let provider = Arc::new(Provider::<Ws>::connect(&config.ws_url).await?);
        
        let mut copy_wallets = Vec::new();
        
        info!("Initializing copy wallets...");
        for (idx, private_key) in config.copy_keys.iter().enumerate() {
            // In production, properly parse the private key
            let wallet: ethers::signers::LocalWallet = private_key.parse()?;
            let address = wallet.address();
            
            copy_wallets.push(CopyWallet {
                address,
                private_key: private_key.clone(),
                nonce: 0,
            });
            
            info!("Copy wallet {} initialized: {:?}", idx + 1, address);
        }
        
        Ok(Self {
            config,
            provider,
            copy_wallets,
        })
    }
    
    pub async fn start(&self) -> Result<()> {
        info!("Starting BNB Copy Trading Bot...");
        info!("Bot started successfully");
        Ok(())
    }
    
    pub async fn stop(&self) -> Result<()> {
        info!("Stopping bot...");
        info!("Bot stopped");
        Ok(())
    }
    
    pub fn should_mirror_trade(&self, initiator: Address) -> bool {
        let initiator_lower = format!("{:?}", initiator).to_lowercase();
        
        // Don't mirror our own trades
        if self.copy_wallets.iter().any(|w| {
            format!("{:?}", w.address).to_lowercase() == initiator_lower
        }) {
            return false;
        }
        
        // Only mirror trades from target wallets
        self.config.target_wallets.iter().any(|w| {
            w.eq_ignore_ascii_case(&initiator_lower)
        })
    }
    
    pub fn get_copy_wallets(&self) -> &[CopyWallet] {
        &self.copy_wallets
    }
    
    pub fn get_config(&self) -> &Config {
        &self.config
    }
    
    pub fn get_provider(&self) -> Arc<Provider<Ws>> {
        Arc::clone(&self.provider)
    }
}
