use anyhow::Result;
use ethers::types::Address;

pub fn parse_address(address: &str) -> Result<Address> {
    address.parse().map_err(|e| anyhow::anyhow!("Invalid address: {}", e))
}

pub fn wei_to_eth(wei: ethers::types::U256) -> f64 {
    (wei.as_u128() as f64) / 1e18
}

pub fn eth_to_wei(eth: f64) -> ethers::types::U256 {
    ethers::types::U256::from((eth * 1e18) as u128)
}

pub fn calculate_slippage(amount: ethers::types::U256, slippage_bps: u64) -> ethers::types::U256 {
    amount * (10000 - slippage_bps) / 10000
}
