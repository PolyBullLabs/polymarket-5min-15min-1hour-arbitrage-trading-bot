"""
Get USDC balance for an address
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from ..config.env import ENV


USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# Thread pool executor for running sync Web3 calls
_executor = ThreadPoolExecutor(max_workers=5)


def _get_balance_sync(address: str) -> float:
    """Get USDC balance synchronously (internal function)"""
    w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
    # Convert address to checksum format
    checksum_address = Web3.to_checksum_address(address)
    checksum_usdc_address = Web3.to_checksum_address(ENV.USDC_CONTRACT_ADDRESS)
    usdc_contract = w3.eth.contract(address=checksum_usdc_address, abi=USDC_ABI)
    balance_usdc = usdc_contract.functions.balanceOf(checksum_address).call()
    # USDC has 6 decimals
    balance_usdc_real = balance_usdc / 10**6
    return float(balance_usdc_real)


async def get_my_balance_async(address: str) -> float:
    """Get USDC balance for an address (async)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _get_balance_sync, address)


def get_my_balance(address: str) -> float:
    """Get USDC balance for an address (sync wrapper)"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, but can't use run_until_complete
            # So we'll need to use run_in_executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_get_balance_sync, address)
                return future.result()
        else:
            return loop.run_until_complete(get_my_balance_async(address))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(get_my_balance_async(address))

