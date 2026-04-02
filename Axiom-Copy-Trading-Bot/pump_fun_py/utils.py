import json
import time
from solana.rpc.commitment import Processed, Confirmed
from solana.rpc.types import TokenAccountOpts
from solders.signature import Signature  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from .config import client
from .coin_data import get_coin_data
from datetime import datetime


def get_token_balance(pub_key: Pubkey, mint_str: str) -> float | None:
    try:
        mint = Pubkey.from_string(mint_str)

        response = client.get_token_accounts_by_owner_json_parsed(
            pub_key,
            TokenAccountOpts(mint=mint),
            commitment=Processed
        )

        accounts = response.value

        if accounts:
            token_amount = accounts[0].account.data.parsed['info']['tokenAmount']['uiAmount']

            return float(token_amount)

        return None
    except Exception as e:
        print(f'[{datetime.now()}] Error fetching token balance [PF]: {e}!')

        return None


def confirm_txn(txn_sig: Signature, max_retries: int = 20, retry_interval: int = 3) -> bool | None:
    retries = 1
    
    while retries < max_retries:
        try:
            txn_res = client.get_transaction(txn_sig, encoding='json', commitment=Confirmed, max_supported_transaction_version=0)
            txn_json = json.loads(txn_res.value.transaction.meta.to_json())
            
            if txn_json['err'] is None:
                print(f'[{datetime.now()}] Transaction [PF] confirmed... try count: {retries}!')

                return True
            
            print(f'[{datetime.now()}] Error: Transaction [PF] not confirmed. Retrying...')

            if txn_json['err']:
                err = txn_json['err']

                print(f'[{datetime.now()}] Transaction [PF] failed! Error: {err}')

                return False
        except Exception as e:
            # print('Awaiting confirmation... try count:', retries)
            retries += 1

            time.sleep(retry_interval)
    
    # print('Max retries reached. Transaction confirmation failed.')
    return None


def get_token_price(mint_str: str) -> float | None:
    try:
        coin_data = get_coin_data(mint_str)
        
        if not coin_data:
            print(f'[{datetime.now()}] Failed to retrieve [PF] coin data!')

            return None
        
        virtual_sol_reserves = coin_data.virtual_sol_reserves / 10**9
        virtual_token_reserves = coin_data.virtual_token_reserves / 10**6

        token_price = virtual_sol_reserves / virtual_token_reserves
        print(f'[{datetime.now()}] Token Price [PF]: {token_price:.20f} SOL!')
        
        return token_price

    except Exception as e:
        print(f'[{datetime.now()}] Error calculating token price [PF]: {e}!')

        return None
