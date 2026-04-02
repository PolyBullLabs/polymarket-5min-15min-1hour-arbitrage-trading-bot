use serde::{Deserialize, Serialize};
use ethers::types::Address;

#[derive(Debug, Clone)]
pub enum DexType {
    PancakeSwap,
    FourMeme,
}

#[derive(Debug, Clone)]
pub struct TradeEvent {
    pub tx_hash: String,
    pub block_number: u64,
    pub initiator: Address,
    pub dex: DexType,
    pub token_in: Address,
    pub token_out: Address,
    pub amount_in: ethers::types::U256,
    pub amount_out: ethers::types::U256,
}

#[derive(Debug, Clone)]
pub struct CopyWallet {
    pub address: Address,
    pub private_key: String,
    pub nonce: u64,
}

#[derive(Debug)]
pub struct ExecutionResult {
    pub success: bool,
    pub tx_hash: Option<String>,
    pub error: Option<String>,
    pub wallet: Address,
}
