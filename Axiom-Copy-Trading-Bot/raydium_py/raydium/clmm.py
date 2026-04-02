import base64
import os
from typing import Optional
from solana.rpc.commitment import Processed
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price  # type: ignore
from solders.message import MessageV0  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.system_program import (
    CreateAccountWithSeedParams,
    create_account_with_seed,
)
from solders.transaction import VersionedTransaction  # type: ignore
from spl.token.client import Token
from spl.token.instructions import (
    CloseAccountParams,
    InitializeAccountParams,
    close_account,
    create_associated_token_account,
    get_associated_token_address,
    initialize_account,
)
from raydium_py.utils.common_utils import confirm_txn, get_token_balance
from raydium_py.utils.pool_utils import (
    ClmmPoolKeys, 
    DIRECTION, 
    fetch_clmm_pool_keys, 
    make_clmm_swap_instruction
)
from raydium_py.config import client, payer_keypair, UNIT_BUDGET, UNIT_PRICE
from raydium_py.raydium.constants import ACCOUNT_LAYOUT_LEN, SOL_DECIMAL, TOKEN_PROGRAM_ID, WSOL
from spl.token.constants import TOKEN_2022_PROGRAM_ID


def buy(pair_address: str, sol_in: float = 0.1) -> bool:
    try:
        print(f"Starting buy transaction for pair address: {pair_address}")

        print("Fetching pool keys...")
        pool_keys: Optional[ClmmPoolKeys] = fetch_clmm_pool_keys(pair_address)
        if pool_keys is None:
            print("No pool keys found...")
            return False
        print("Pool keys fetched successfully.")

        if pool_keys.token_mint_0 == WSOL:
            mint = pool_keys.token_mint_1
        else:
            mint = pool_keys.token_mint_0
            
        token_info = client.get_account_info_json_parsed(mint).value
        if token_info.data.program == "spl-token":
            token_program = TOKEN_PROGRAM_ID
        else:
            token_program = TOKEN_2022_PROGRAM_ID
        
        print("Calculating transaction amounts...")
        amount = int(sol_in * SOL_DECIMAL)
        tokens_out = sol_for_tokens(sol_in, pool_keys.sqrt_price_x64, pool_keys.mint_decimals_0, pool_keys.mint_decimals_1)
        print(f"Amount In: {sol_in} | Estimated Amount Out: {tokens_out}")

        print("Checking for existing token account...")
        token_account_check = client.get_token_accounts_by_owner(payer_keypair.pubkey(), TokenAccountOpts(mint), Processed)
        if token_account_check.value:
            token_account = token_account_check.value[0].pubkey
            token_account_instruction = None
            print("Token account found.")
        else:
            token_account = get_associated_token_address(payer_keypair.pubkey(), mint, token_program)
            token_account_instruction = create_associated_token_account(payer_keypair.pubkey(), payer_keypair.pubkey(), mint, token_program)
            print("No existing token account found; creating associated token account.")

        print("Generating seed for WSOL account...")
        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        wsol_token_account = Pubkey.create_with_seed(
            payer_keypair.pubkey(), seed, TOKEN_PROGRAM_ID
        )
        balance_needed = Token.get_min_balance_rent_for_exempt_for_account(client)

        print("Creating and initializing WSOL account...")
        create_wsol_account_instruction = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=payer_keypair.pubkey(),
                to_pubkey=wsol_token_account,
                base=payer_keypair.pubkey(),
                seed=seed,
                lamports=int(balance_needed + amount),
                space=ACCOUNT_LAYOUT_LEN,
                owner=TOKEN_PROGRAM_ID,
            )
        )

        init_wsol_account_instruction = initialize_account(
            InitializeAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                mint=WSOL,
                owner=payer_keypair.pubkey(),
            )
        )

        print("Creating swap instructions...")
        swap_instruction = make_clmm_swap_instruction(
            amount=amount,
            token_account_in=wsol_token_account,
            token_account_out=token_account,
            accounts=pool_keys,
            payer=payer_keypair.pubkey(),
            action=DIRECTION.BUY,
        )

        print("Preparing to close WSOL account after swap...")
        close_wsol_account_instruction = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                dest=payer_keypair.pubkey(),
                owner=payer_keypair.pubkey(),
            )
        )

        instructions = [
            set_compute_unit_limit(UNIT_BUDGET),
            set_compute_unit_price(UNIT_PRICE),
            create_wsol_account_instruction,
            init_wsol_account_instruction,
        ]

        if token_account_instruction:
            instructions.append(token_account_instruction)

        instructions.append(swap_instruction)
        instructions.append(close_wsol_account_instruction)

        print("Compiling transaction message...")
        compiled_message = MessageV0.try_compile(
            payer_keypair.pubkey(),
            instructions,
            [],
            client.get_latest_blockhash().value.blockhash,
        )

        print("Sending transaction...")
        txn_sig = client.send_transaction(
            txn=VersionedTransaction(compiled_message, [payer_keypair]),
            opts=TxOpts(skip_preflight=False),
        ).value
        print("Transaction Signature:", txn_sig)

        print("Confirming transaction...")
        confirmed = confirm_txn(txn_sig)

        print("Transaction confirmed:", confirmed)
        return confirmed
    except Exception as e:
        print("Error occurred during transaction:", e)
        return False


def sell(pair_address: str, percentage: int = 100) -> bool:
    try:
        print("Fetching pool keys...")
        pool_keys: Optional[ClmmPoolKeys] = fetch_clmm_pool_keys(pair_address)
        if pool_keys is None:
            print("No pool keys found...")
            return False
        print("Pool keys fetched successfully.")

        if pool_keys.token_mint_0 == WSOL:
            mint = pool_keys.token_mint_1
            token_decimal = pool_keys.mint_decimals_1
        else:
            mint = pool_keys.token_mint_0
            token_decimal = pool_keys.mint_decimals_0
            
        token_info = client.get_account_info_json_parsed(mint).value
        
        if token_info.data.program == "spl-token":
            token_program = TOKEN_PROGRAM_ID
        else:
            token_program = TOKEN_2022_PROGRAM_ID

        print("Retrieving token balance...")
        token_balance = get_token_balance(str(mint))
        print("Token Balance:", token_balance)

        if token_balance == 0 or token_balance is None:
            print("No token balance available to sell.")
            return False

        token_balance = token_balance * (percentage / 100)
        print(f"Selling {percentage}% of the token balance, adjusted balance: {token_balance}")

        print("Calculating transaction amounts...")
        
        sol_out = tokens_for_sol(token_balance, pool_keys.sqrt_price_x64, pool_keys.mint_decimals_0, pool_keys.mint_decimals_1)
        print(f"Amount In: {token_balance} | Estimated Amount Out: {sol_out}")
        
        amount = int(token_balance * 10**token_decimal)
        token_account = get_associated_token_address(payer_keypair.pubkey(), mint, token_program)

        print("Generating seed and creating WSOL account...")
        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        wsol_token_account = Pubkey.create_with_seed(
            payer_keypair.pubkey(), seed, TOKEN_PROGRAM_ID
        )
        balance_needed = Token.get_min_balance_rent_for_exempt_for_account(client)

        create_wsol_account_instruction = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=payer_keypair.pubkey(),
                to_pubkey=wsol_token_account,
                base=payer_keypair.pubkey(),
                seed=seed,
                lamports=int(balance_needed),
                space=ACCOUNT_LAYOUT_LEN,
                owner=TOKEN_PROGRAM_ID,
            )
        )

        init_wsol_account_instruction = initialize_account(
            InitializeAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                mint=WSOL,
                owner=payer_keypair.pubkey(),
            )
        )

        print("Creating swap instructions...")
        swap_instructions = make_clmm_swap_instruction(
            amount=amount,
            token_account_in=token_account,
            token_account_out=wsol_token_account,
            accounts=pool_keys,
            payer=payer_keypair.pubkey(),
            action=DIRECTION.SELL,
        )

        print("Preparing to close WSOL account after swap...")
        close_wsol_account_instruction = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                dest=payer_keypair.pubkey(),
                owner=payer_keypair.pubkey(),
            )
        )

        instructions = [
            set_compute_unit_limit(UNIT_BUDGET),
            set_compute_unit_price(UNIT_PRICE),
            create_wsol_account_instruction,
            init_wsol_account_instruction,
            swap_instructions,
            close_wsol_account_instruction,
        ]

        if percentage == 100:
            print("Preparing to close token account after swap...")
            close_token_account_instruction = close_account(
                CloseAccountParams(
                    program_id=token_program,
                    account=token_account,
                    dest=payer_keypair.pubkey(),
                    owner=payer_keypair.pubkey(),
                )
            )
            instructions.append(close_token_account_instruction)

        print("Compiling transaction message...")
        compiled_message = MessageV0.try_compile(
            payer_keypair.pubkey(),
            instructions,
            [],
            client.get_latest_blockhash().value.blockhash,
        )

        print("Sending transaction...")
        txn_sig = client.send_transaction(
            txn=VersionedTransaction(compiled_message, [payer_keypair]),
            opts=TxOpts(skip_preflight=True),
        ).value
        print("Transaction Signature:", txn_sig)

        print("Confirming transaction...")
        confirmed = confirm_txn(txn_sig)

        print("Transaction confirmed:", confirmed)
        return confirmed

    except Exception as e:
        print("Error occurred during transaction:", e)
        return False


def sqrt_price_x64_to_token_price(sqrt_price_x64: int, mint_decimals_0: int, mint_decimals_1: int) -> float:
    token_price = 2 ** 128 / sqrt_price_x64 ** 2 * 10 ** (mint_decimals_1-mint_decimals_0)

    return token_price


def sol_for_tokens(sol_in: float, sqrt_price_x64: int, mint_decimals_0: int, mint_decimals_1: int) -> float:
    token_price = sqrt_price_x64_to_token_price(sqrt_price_x64, mint_decimals_0, mint_decimals_1)
    tokens_out = sol_in / token_price

    return round(tokens_out, 9)


def tokens_for_sol(tokens_in: float, sqrt_price_x64: int, mint_decimals_0: int, mint_decimals_1: int) -> float:
    token_price = sqrt_price_x64_to_token_price(sqrt_price_x64, mint_decimals_0, mint_decimals_1)
    sol_out = tokens_in * token_price

    return round(sol_out, 9)
