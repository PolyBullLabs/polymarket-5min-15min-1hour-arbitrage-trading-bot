"""Constants for the Kuru copy trading bot."""

from web3 import Web3

# Monad Blockchain Chain IDs
# Source: https://docs.monad.xyz/developer-essentials/network-information
MONAD_CHAIN_ID = 41454  # Mainnet (not launched yet)
MONAD_TESTNET_CHAIN_ID = 10143  # Testnet - Active

# Kuru Contract Addresses
# Main Kuru Protocol Contracts (Testnet)
KURU_ROUTER_ADDRESS_TESTNET = "0x1f5A250c4A506DA4cE584173c6ed1890B1bf7187"
KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET = "0xdDDaBd30785bA8b45e434a1f134BDf304d6125d9"
KURU_FORWARDER_ADDRESS_TESTNET = "0xa21ca7b4e308e9E2dC4C60620572792634EA21a0"
KURU_DEPLOYER_ADDRESS_TESTNET = "0x1D90616Ad479c3D814021b1f4C43b1a2fFf87626"
KURU_UTILS_ADDRESS_TESTNET = "0xDdAEdbc015fEe6BE50c69Fbf5d771A4563C996B3"

# Official Token Addresses (Testnet)
USDC_ADDRESS_TESTNET = "0xf817257fed379853cDe0fa4F97AB987181B1E5Ea"
KUSDC_ADDRESS_TESTNET = "0xf817257fed379853cDe0fa4F97AB987181B1E5Ea"  # Kuru USDC
USDT_ADDRESS_TESTNET = "0x88b8E2161DEDC77EF4ab7585569D2415a1C1055D"
DAK_ADDRESS_TESTNET = "0x0F0BDEbF0F83cD1EE3974779Bcb7315f9808c714"
CHOG_ADDRESS_TESTNET = "0xE0590015A873bF326bd645c3E1266d4db41C4E6B"
YAKI_ADDRESS_TESTNET = "0xfe140e1dCe99Be9F4F15d657CD9b7BF622270C50"

# Official Market Addresses (Testnet)
MON_USDC_MARKET_ADDRESS_TESTNET = "0xe53E39face99011c338d5C54EC332c7C9e271872"
DAK_MON_MARKET_ADDRESS_TESTNET = "0x94B72620e65577De5FB2b8a8B93328CAf6Ca161b"
CHOG_MON_MARKET_ADDRESS_TESTNET = "0x277bF4a0AAc16f19d7bf592FeFFc8D2d9a890508"
YAKI_MON_MARKET_ADDRESS_TESTNET = "0xD5C1Dc181c359f0199c83045A85Cd2556B325De0"

# Legacy constant for backward compatibility (points to Router)
KURU_CONTRACT_ADDRESS_TESTNET = KURU_ROUTER_ADDRESS_TESTNET
# Backward compatibility for market addresses (without _TESTNET suffix)
MON_USDC_MARKET_ADDRESS = MON_USDC_MARKET_ADDRESS_TESTNET
DAK_MON_MARKET_ADDRESS = DAK_MON_MARKET_ADDRESS_TESTNET
CHOG_MON_MARKET_ADDRESS = CHOG_MON_MARKET_ADDRESS_TESTNET
YAKI_MON_MARKET_ADDRESS = YAKI_MON_MARKET_ADDRESS_TESTNET

# Main Kuru Protocol Contracts (Mainnet)
KURU_FLOW_ENTRYPOINT_ADDRESS_MAINNET = "0xb3e6778480b2E488385E8205eA05E20060B813cb"  # Aggregator
KURU_FLOW_ROUTER_ADDRESS_MAINNET = "0x465D06d4521ae9Ce724E0c182Daad5D8a2Ff7040"
KURU_ROUTER_ADDRESS_MAINNET = "0xd651346d7c789536ebf06dc72aE3C8502cd695CC"  # Market factory
KURU_FORWARDER_ADDRESS_MAINNET = "0x974E61BBa9C4704E8Bcc1923fdC3527B41323FAA"
KURU_MARGIN_ACCOUNT_ADDRESS_MAINNET = "0x2A68ba1833cDf93fa9Da1EEbd7F46242aD8E90c5"
KURU_DEPLOYER_ADDRESS_MAINNET = "0xe29309e308af3EE3B1a414E97c37A58509f27D1E"

# Legacy constant for backward compatibility (points to Router)
KURU_CONTRACT_ADDRESS_MAINNET = KURU_ROUTER_ADDRESS_MAINNET

# ============================================================
# Network-Aware Address Helpers
# ============================================================


def get_kuru_router_address(network: str) -> str:
    """Get Kuru Router address for the specified network."""
    if network == "mainnet":
        return KURU_ROUTER_ADDRESS_MAINNET
    return KURU_ROUTER_ADDRESS_TESTNET


def get_kuru_margin_account_address(network: str) -> str:
    """Get Kuru Margin Account address for the specified network."""
    if network == "mainnet":
        return KURU_MARGIN_ACCOUNT_ADDRESS_MAINNET
    return KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET


def get_kuru_forwarder_address(network: str) -> str:
    """Get Kuru Forwarder address for the specified network."""
    if network == "mainnet":
        return KURU_FORWARDER_ADDRESS_MAINNET
    return KURU_FORWARDER_ADDRESS_TESTNET


def get_kuru_deployer_address(network: str) -> str:
    """Get Kuru Deployer address for the specified network."""
    if network == "mainnet":
        return KURU_DEPLOYER_ADDRESS_MAINNET
    return KURU_DEPLOYER_ADDRESS_TESTNET


def get_chain_id(network: str) -> int:
    """Get chain ID for the specified network."""
    if network == "mainnet":
        return MONAD_CHAIN_ID
    return MONAD_TESTNET_CHAIN_ID


def get_usdc_address(network: str) -> str:
    """Get USDC token address for the specified network."""
    if network == "mainnet":
        # Mainnet token addresses not yet available
        raise ValueError("Mainnet token addresses are not yet available")
    return USDC_ADDRESS_TESTNET


# Gas Configuration
DEFAULT_GAS_LIMIT = 300_000  # Default gas limit for transactions
DEFAULT_GAS_PRICE_GWEI = 20  # Default gas price in Gwei (20 Gwei)

# Retry Configuration
MAX_RETRIES = 3  # Maximum number of retry attempts for failed operations
RETRY_BACKOFF_SECONDS = 2  # Initial backoff time in seconds (exponential backoff)

# Transaction Confirmation
CONFIRMATION_BLOCKS = 1  # Number of blocks to wait for confirmation
TRANSACTION_TIMEOUT_SECONDS = 120  # Timeout for transaction confirmation

# Order Configuration
MIN_ORDER_SIZE_USD = 1.0  # Minimum order size in USD
MAX_SLIPPAGE_PERCENT = 5.0  # Maximum allowed slippage percentage

# ============================================================
# Address Validation (Runtime checks at module import)
# ============================================================
# Validate that all contract addresses are properly checksummed
# This ensures we catch any address errors at import time rather than runtime

_ADDRESSES_TO_VALIDATE = {
    # Testnet Addresses
    "KURU_ROUTER_ADDRESS_TESTNET": KURU_ROUTER_ADDRESS_TESTNET,
    "KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET": KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET,
    "KURU_FORWARDER_ADDRESS_TESTNET": KURU_FORWARDER_ADDRESS_TESTNET,
    "KURU_DEPLOYER_ADDRESS_TESTNET": KURU_DEPLOYER_ADDRESS_TESTNET,
    "KURU_UTILS_ADDRESS_TESTNET": KURU_UTILS_ADDRESS_TESTNET,
    "USDC_ADDRESS_TESTNET": USDC_ADDRESS_TESTNET,
    "KUSDC_ADDRESS_TESTNET": KUSDC_ADDRESS_TESTNET,
    "USDT_ADDRESS_TESTNET": USDT_ADDRESS_TESTNET,
    "DAK_ADDRESS_TESTNET": DAK_ADDRESS_TESTNET,
    "CHOG_ADDRESS_TESTNET": CHOG_ADDRESS_TESTNET,
    "YAKI_ADDRESS_TESTNET": YAKI_ADDRESS_TESTNET,
    "MON_USDC_MARKET_ADDRESS_TESTNET": MON_USDC_MARKET_ADDRESS_TESTNET,
    "DAK_MON_MARKET_ADDRESS_TESTNET": DAK_MON_MARKET_ADDRESS_TESTNET,
    "CHOG_MON_MARKET_ADDRESS_TESTNET": CHOG_MON_MARKET_ADDRESS_TESTNET,
    "YAKI_MON_MARKET_ADDRESS_TESTNET": YAKI_MON_MARKET_ADDRESS_TESTNET,
    # Mainnet Addresses
    "KURU_FLOW_ENTRYPOINT_ADDRESS_MAINNET": KURU_FLOW_ENTRYPOINT_ADDRESS_MAINNET,
    "KURU_FLOW_ROUTER_ADDRESS_MAINNET": KURU_FLOW_ROUTER_ADDRESS_MAINNET,
    "KURU_ROUTER_ADDRESS_MAINNET": KURU_ROUTER_ADDRESS_MAINNET,
    "KURU_FORWARDER_ADDRESS_MAINNET": KURU_FORWARDER_ADDRESS_MAINNET,
    "KURU_MARGIN_ACCOUNT_ADDRESS_MAINNET": KURU_MARGIN_ACCOUNT_ADDRESS_MAINNET,
    "KURU_DEPLOYER_ADDRESS_MAINNET": KURU_DEPLOYER_ADDRESS_MAINNET,
}

for _name, _address in _ADDRESSES_TO_VALIDATE.items():
    try:
        if not Web3.is_checksum_address(_address):
            raise ValueError(
                f"{_name} address '{_address}' is not properly checksummed. "
                f"Expected: {Web3.to_checksum_address(_address)}"
            )
    except Exception as e:
        raise ValueError(f"Invalid address for {_name}: {_address}") from e

# Clean up namespace
del _name, _address, _ADDRESSES_TO_VALIDATE
