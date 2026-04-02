"""
Create Polymarket CLOB client using official py-clob-client library
"""
import asyncio
from typing import Optional, Dict, Any
from web3 import Web3
from eth_account import Account
from py_clob_client.client import ClobClient as OfficialClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from ..config.env import ENV
from ..utils.logger import info, error, warning


async def is_gnosis_safe(address: str) -> bool:
    """Check if wallet is a Gnosis Safe contract"""
    try:
        w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
        checksum_address = Web3.to_checksum_address(address)
        code = w3.eth.get_code(checksum_address)
        return code != b'0x'
    except Exception as e:
        error(f'Error checking wallet type: {e}')
        return False


class ClobClient:
    """Polymarket CLOB client wrapper using official py-clob-client library"""
    
    def __init__(
        self,
        host: str,
        chain_id: int,
        wallet: Any,
        api_creds: Optional[Dict[str, Any]] = None,
        signature_type: str = 'EOA',
        proxy_wallet: Optional[str] = None
    ):
        self.host = host.rstrip('/')
        self.chain_id = chain_id
        self.wallet = wallet
        self.api_creds = api_creds or {}
        self.signature_type = signature_type
        self.proxy_wallet = proxy_wallet
        
        sig_type_int = 0
        if signature_type == 'POLY_GNOSIS_SAFE' or signature_type == 'POLY_PROXY':
            sig_type_int = 2
        elif signature_type and 'EMAIL' in signature_type.upper():
            sig_type_int = 1
        
        private_key = None
        if hasattr(wallet, 'key'):
            private_key = wallet.key
            if hasattr(private_key, 'hex'):
                private_key = private_key.hex()
            if isinstance(private_key, bytes):
                private_key = private_key.hex()
        if not private_key:
            private_key = ENV.PRIVATE_KEY
        
        if isinstance(private_key, str) and private_key.startswith('0x'):
            private_key = private_key[2:]
        if isinstance(private_key, str):
            private_key = '0x' + private_key
        
        # Initialize official CLOB client
        self._client = OfficialClobClient(
            host=host,
            key=private_key,
            chain_id=chain_id,
            signature_type=sig_type_int,
            funder=proxy_wallet if proxy_wallet else wallet.address
        )
        
        # Don't set API credentials - use L1 authentication (wallet signature) only
        self.api_key = None
        self.api_secret = None
        self.api_passphrase = None
    
    async def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """Get order book for a token"""
        import httpx
        url = f'{self.host}/book?token_id={token_id}'
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def create_market_order(self, order_args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a market order using official py-clob-client"""
        token_id = order_args.get('tokenID')
        if not token_id:
            raise ValueError('tokenID is required')
        
        amount = float(order_args.get('amount', 0))
        side_str = order_args.get('side', 'BUY')
        side_constant = BUY if side_str.upper() == 'BUY' else SELL
        
        market_order = MarketOrderArgs(
            token_id=str(token_id),
            amount=amount,
            side=side_constant,
            order_type=OrderType.FOK
        )
        
        signed_order = self._client.create_market_order(market_order)
        return signed_order
    
    async def post_order(self, signed_order: Dict[str, Any], order_type: str) -> Dict[str, Any]:
        """Post order to Polymarket CLOB API using official py-clob-client"""
        try:
            order_type_enum = OrderType.FOK
            if order_type.upper() == 'GTC':
                order_type_enum = OrderType.GTC
            elif order_type.upper() == 'IOC':
                order_type_enum = OrderType.IOC
            
            # Try to post order - derive API credentials using L1 auth if needed
            try:
                response = self._client.post_order(signed_order, order_type_enum)
            except Exception as e:
                error_msg = str(e)
                # If API credentials are required, derive them using L1 authentication
                if 'API Credentials' in error_msg or 'credentials' in error_msg.lower() or 'API key' in error_msg.lower():
                    try:
                        # Derive API credentials using L1 authentication (wallet signature)
                        # This uses L1 auth internally, so no manual API key needed
                        creds = self._client.create_or_derive_api_creds()
                        if creds:
                            self._client.set_api_creds(creds)
                            if isinstance(creds, dict):
                                self.api_creds = creds
                                self.api_key = creds.get('key')
                                self.api_secret = creds.get('secret')
                                self.api_passphrase = creds.get('passphrase')
                            # Retry the order with derived credentials
                            response = self._client.post_order(signed_order, order_type_enum)
                        else:
                            return {
                                'success': False,
                                'error': 'API credentials not available',
                                'errorMsg': error_msg,
                                'message': error_msg,
                            }
                    except Exception as derive_error:
                        err_str = str(derive_error)
                        hint = (
                            'Check: (1) Internet connection, (2) CLOB_HTTP_URL in .env is correct and reachable '
                            '(e.g. https://clob.polymarket.com/), (3) Polymarket API may be temporarily down. '
                            'Try again in a few minutes or increase REQUEST_TIMEOUT_MS.'
                        )
                        return {
                            'success': False,
                            'error': f'Failed to derive API credentials: {derive_error}',
                            'errorMsg': err_str,
                            'message': f'Failed to derive API credentials: {err_str}. {hint}',
                        }
                else:
                    # If it's not an API credentials error, re-raise
                    raise
            if hasattr(response, 'success'):
                return {
                    'success': response.success,
                    'error': getattr(response, 'error', None),
                    'errorMsg': getattr(response, 'errorMsg', None),
                    'message': getattr(response, 'message', None),
                    'data': response
                }
            elif isinstance(response, dict):
                return {
                    'success': response.get('success', False),
                    'error': response.get('error'),
                    'errorMsg': response.get('errorMsg'),
                    'message': response.get('message'),
                    'data': response
                }
            else:
                return {
                    'success': True,
                    'data': response
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errorMsg': f'Exception while posting order: {e}',
                'message': f'Exception while posting order: {e}',
            }


def _derive_api_creds_sync(client: OfficialClobClient) -> Optional[Dict[str, Any]]:
    """Run create_or_derive_api_creds in sync context (blocking)."""
    return client.create_or_derive_api_creds()


async def _derive_api_creds_with_retries(clob_client: ClobClient) -> bool:
    """Derive API credentials with retries to handle transient network errors."""
    loop = asyncio.get_event_loop()
    last_error = None
    retries = max(1, getattr(ENV, 'NETWORK_RETRY_LIMIT', 3))
    for attempt in range(1, retries + 1):
        try:
            creds = await loop.run_in_executor(
                None,
                _derive_api_creds_sync,
                clob_client._client,
            )
            if creds:
                clob_client._client.set_api_creds(creds)
                if isinstance(creds, dict):
                    clob_client.api_creds = creds
                    clob_client.api_key = creds.get('key')
                    clob_client.api_secret = creds.get('secret')
                    clob_client.api_passphrase = creds.get('passphrase')
                info('API credentials derived successfully (L1 auth)')
                return True
        except Exception as e:
            last_error = e
            err_str = str(e)
            if attempt < retries:
                warning(f'Derive API credentials attempt {attempt}/{retries} failed: {err_str}. Retrying in 2s...')
                await asyncio.sleep(2)
            else:
                error(f'Failed to derive API credentials after {retries} attempts: {last_error}')
    return False


async def create_clob_client() -> ClobClient:
    """Create and initialize CLOB client"""
    chain_id = 137
    host = ENV.CLOB_HTTP_URL
    
    account = Account.from_key(ENV.PRIVATE_KEY)
    
    is_proxy_safe = await is_gnosis_safe(ENV.PROXY_WALLET)
    signature_type = 'POLY_GNOSIS_SAFE' if is_proxy_safe else 'EOA'
    
    info(f'Wallet type detected: {"Gnosis Safe" if is_proxy_safe else "EOA"}')
    
    clob_client = ClobClient(
        host=host,
        chain_id=chain_id,
        wallet=account,
        signature_type=signature_type,
        proxy_wallet=ENV.PROXY_WALLET if is_proxy_safe else None
    )
    
    # Derive API credentials at startup so orders don't fail with "Request exception"
    info('Deriving API credentials (L1 auth)...')
    if not await _derive_api_creds_with_retries(clob_client):
        hint = (
            'Check: (1) Internet connection, (2) CLOB_HTTP_URL in .env (e.g. https://clob.polymarket.com/), '
            '(3) Polymarket API may be down. Increase REQUEST_TIMEOUT_MS or try again later.'
        )
        raise RuntimeError(f'Could not derive API credentials. {hint}')
    
    return clob_client

