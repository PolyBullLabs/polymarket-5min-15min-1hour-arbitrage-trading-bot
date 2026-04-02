use anyhow::Result;
use log::info;

pub mod listener;
pub mod executor;

pub fn init() -> Result<()> {
    info!("Four.meme module initialized");
    Ok(())
}
