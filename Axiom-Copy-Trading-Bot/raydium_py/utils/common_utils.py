import json
import time
from datetime import datetime
from solana.rpc.commitment import Confirmed, Processed
from solana.rpc.types import TokenAccountOpts
from solders.signature import Signature  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from raydium_py.config import client, payer_keypair


def get_token_balance(mint_str: str) -> float | None:
    mint = Pubkey.from_string(mint_str)

    response = client.get_token_accounts_by_owner_json_parsed(
        payer_keypair.pubkey(),
        TokenAccountOpts(mint=mint),
        commitment=Processed
    )

    if response.value:
        accounts = response.value
        if accounts:
            token_amount = accounts[0].account.data.parsed['info']['tokenAmount']['uiAmount']
            if token_amount:
                return float(token_amount)

    return None


def confirm_txn(txn_sig: Signature, max_retries: int = 20, retry_interval: int = 3) -> bool | None:
    retries = 1
    
    while retries < max_retries:
        try:
            txn_res = client.get_transaction(
                txn_sig, 
                encoding='json',
                commitment=Confirmed, 
                max_supported_transaction_version=0
            )
            
            txn_json = json.loads(txn_res.value.transaction.meta.to_json())
            
            if txn_json['err'] is None:
                print(f'[{datetime.now()}] Transaction [RA] confirmed... try count: {retries}!')

                return True
            
            print(f'[{datetime.now()}] Error: Transaction [RA] not confirmed. Retrying...')

            if txn_json['err']:
                err = txn_json['err']

                print(f'[{datetime.now()}] Transaction [RA] failed! Error: {err}')

                return False
        except Exception as e:
            # print("Awaiting confirmation... try count:", retries)
            retries += 1
            time.sleep(retry_interval)
    
    # print("Max retries reached. Transaction confirmation failed.")

    return None
