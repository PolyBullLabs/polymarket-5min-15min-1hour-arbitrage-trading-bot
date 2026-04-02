import re
import os
import asyncio
import urllib3
import requests
import websockets
from datetime import datetime
from dotenv import load_dotenv
from pump_fun_py.pump_fun import buy as buy_pump_fun
from pump_fun_py.pump_fun import sell as sell_pump_fun
from raydium_py.raydium.amm_v4 import buy as buy_raydium
from raydium_py.raydium.amm_v4 import sell as sell_raydium


load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


wallet_public_key = os.getenv('WALLET_PUBLIC_KEY')
track_wallets = os.getenv('TRACK_WALLETS')
max_slippage = int(os.getenv('MAX_SLIPPAGE'))
sol_in = float(os.getenv('SOL_IN'))
max_sol_spend = float(os.getenv('MAX_SOL_SPEND'))
allow_rebuy = False if os.getenv('ALLOW_REBUY') == 'false' else True
max_buy_attempts = int(os.getenv('MAX_BUY_ATTEMPTS'))
debug = False if os.getenv('DEBUG') == 'false' else True


# temp variables
buy_list = []
start_balance = 0.0
spent = 0.0


def read_cookie():
    try:
        with open('cookie.txt', 'r') as f0:
            txt_cookie = f0.read().strip()

        return txt_cookie
    except:
        return ''


def write_cookie(cookie_str):
    try:
        with open('cookie.txt', 'w+') as f1:
            f1.write(cookie_str.strip())

        return True
    except:
        return False


def load_initial_payload():
    messages = []

    with open('join.txt') as f:
        for message in f.readlines():
            messages.append(
                message.strip()
            )

    return messages


def refresh_access_token():
    try:
        print(f'[{datetime.now()}] Refreshing access token..')

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'no-cache',
            'dnt': '1',
            'origin': 'https://axiom.trade',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://axiom.trade/',
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'cookie': read_cookie()
        }

        response = requests.post(
            url='https://api4.axiom.trade/refresh-access-token',
            headers=headers,
            verify=False
        )

        if response.status_code != 200:
            print(f'[{datetime.now()}] Could not refresh access token!')

            print('-' * 100)

            print(response.text)

            print('-' * 100)

            print(f'[{datetime.now()}] Closing application...')

            exit()

        cookies = response.headers.get('Set-Cookie')

        new_cookie = ''

        re_auth_refresh_token = re.search(
            pattern=r'auth-refresh-token=.*?;',
            string=cookies,
            flags=re.DOTALL
        )

        if re_auth_refresh_token is not None:
            new_cookie += re_auth_refresh_token.group()

        re_auth_access_token = re.search(
            pattern=r'auth-access-token=.*?;',
            string=cookies,
            flags=re.DOTALL
        )

        if re_auth_access_token is not None:
            new_cookie += ' '
            new_cookie += re_auth_access_token.group()

        if not write_cookie(new_cookie):
            raise Exception('Could not write cookie!')

        print(f'[{datetime.now()}] Access token refreshed!')
    except Exception as e:
        print(f'[{datetime.now()}] Could not refresh access token!')

        print('-' * 100)

        print(e)

        print('-' * 100)

        print(f'[{datetime.now()}] Closing application...')

        exit()


def get_balance():
    try:
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBalance',
            'params': [
                wallet_public_key,
                {
                    'commitment': 'confirmed'
                }
            ]
        }

        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'no-cache',
            'dnt': '1',
            'origin': 'https://axiom.trade',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://axiom.trade/',
            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'cookie': read_cookie()
        }

        response = requests.post(
            url='https://axiom.trade/api/sol-balance',
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            return response.json()['result']['value'] / 1_000_000_000
    except:
        return None


# def get_tokens():
#     try:
#         headers = {
#             'accept': 'application/json, text/plain, */*',
#             'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
#             'cache-control': 'no-cache',
#             'dnt': '1',
#             'origin': 'https://axiom.trade',
#             'pragma': 'no-cache',
#             'priority': 'u=1, i',
#             'referer': 'https://axiom.trade/',
#             'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
#             'sec-ch-ua-mobile': '?0',
#             'sec-ch-ua-platform': '"macOS"',
#             'sec-fetch-dest': 'empty',
#             'sec-fetch-mode': 'cors',
#             'sec-fetch-site': 'same-site',
#             'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
#             'cookie': read_cookie()
#         }
#
#         response = requests.get(
#             url=f'https://api2.axiom.trade/dev-tokens?devAddress={wallet_public_key}',
#             headers=headers,
#             verify=False
#         )
#
#         if response.status_code == 200:
#             return response.json()
#     except:
#         return []


def calculate_my_share(total_sol: float) -> float:  # used if you want to copy the SOL qty spent by the trader
    return total_sol * sol_in


def extract_transaction_details(data: str):
    details = {}

    patterns = {
        'transaction_type': r'"type":"(buy|sell)"',
        'trader_level': r'"trader_level":"(.*?)"',
        'token_amount': r'"token_amount":([\d.]+)',
        'maker_address': r'"maker_address":"(.*?)"',
        'price_sol': r'"price_sol":([\d.]+)',
        'price_usd': r'"price_usd":([\d.]+)',
        'total_sol': r'"total_sol":([\d.]+)',
        'total_usd': r'"total_usd":([\d.]+)',
        'created_at': r'"created_at":"(.*?)"',
        'token_address': r'"tokenAddress":"(.*?)"',
        'pair_address': r'"pair_address":"(.*?)"',
        'token_name': r'"tokenName":"(.*?)"',
        'token_code': r'"tokenTicker":"(.*?)"',
        'protocol': r'"protocol":"(.*?)"'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, data)

        if match:
            value = match.group(1)

            details[key] = value

    return details


async def buy_token(dex, name, address, sol_inn, sslippage):
    global spent

    attempts = 0

    while True:
        try:
            await asyncio.sleep(.5)

            if not allow_rebuy:
                if address in buy_list:
                    print(f'[{datetime.now()}] Already bought [{dex.upper()}] "{name}" [{attempts}]!')

                    break

            if attempts > max_buy_attempts:
                print(f'[{datetime.now()}] Already attempted to buy[{dex.upper()}] "{name}" [{attempts}]!')

                break

            attempts += 1

            print(f'[{datetime.now()}] Trying to buy[{dex.upper()}] "{name}" [{attempts}]..')

            buy_list.append(address)

            if dex == 'ra':
                buy = buy_pump_fun(address, sol_inn, sslippage)
            else:
                buy = buy_pump_fun(address, sol_inn, sslippage)

            if buy:
                spent += sol_inn

                print(f'[{datetime.now()}] Bought[{dex.upper()}] "{name}" [{attempts}]!')

                break
        except:
            print(f'[{datetime.now()}] FAILED to buy[{dex.upper()}] "{name}" [{attempts}]!')


async def sell_token(dex, name, address, sslippage):
    attempts = 0

    while True:
        try:
            await asyncio.sleep(.5)

            print(f'[{datetime.now()}] Trying to sell[{dex.upper()}] "{name}" [{attempts}]..')

            if dex == 'ra':
                sell = sell_raydium(address, 100, sslippage)
            else:
                sell = sell_pump_fun(address, 100, sslippage)

            if sell is None or sell:
                break

            attempts += 1
        except:
            print(f'[{datetime.now()}] FAILED to sell[{dex.upper()}] "{name}" [{attempts}]! Trying again..')


async def send_ping(ws):
    while True:
        await asyncio.sleep(25)

        if debug:
            print('Sending PING..')

        ping_payload = '{"method": "ping"}'

        await ws.send(ping_payload)

        if debug:
            print('Sent', ping_payload)


async def get_current_balance():
    global start_balance

    while True:
        gett = get_balance()

        if gett is not None:
            diff = (gett - start_balance)

            start_balance = gett

            if diff != 0.0:
                print(f'[{datetime.now()}] Balance: {start_balance} | Diff: {format(diff, ".9f")}')

        await asyncio.sleep(5)


def filter_messages(msgg):
    # ^(?!.*\b(block_hash|update_pulse|sol_price|sol-priority-fee|eth_price|jito-bribe-fee|btc_price|new_pairs|connection_monitor)\b).*

    message_filter = re.match(
        pattern=f'.*({track_wallets}).*',
        string=msgg,
        flags=re.DOTALL
    )

    if message_filter is not None:
        return extract_transaction_details(message_filter.group())

    return False


async def connect():
    while True:
        try:
            headers = {
                'Origin': 'https://axiom.trade',
                'Cache-Control': 'no-cache',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Pragma': 'no-cache',
                'Connection': 'Upgrade',
                'Sec-WebSocket-Key': 'NaBrA7Cq2xZiTicaYSIbTw==',
                'Cookie': read_cookie(),
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                'Sec-WebSocket-Version': '13',
                'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits'
            }

            print(f'[{datetime.now()}] Connecting..')

            async with websockets.connect('wss://cluster2.axiom.trade?', extra_headers=headers) as ws:
                print(f'[{datetime.now()}] Connected! Sending payload...')

                for payload in load_initial_payload():
                    await ws.send(payload)

                    if debug:
                        print('Sent', payload)

                print(f'[{datetime.now()}] Payload sent!')

                asyncio.create_task(send_ping(ws))
                asyncio.create_task(get_current_balance())

                while True:
                    response = await ws.recv()

                    filtered_message = filter_messages(response)

                    if spent >= max_sol_spend:
                        print(f'[{datetime.now()}] Already spent {spent}! Max: {max_sol_spend}')

                        continue

                    if filtered_message:
                        transaction_type = filtered_message['transaction_type']
                        protocol = filtered_message['protocol']
                        maker_address = filtered_message['maker_address']
                        token_name = filtered_message['token_name']
                        token_address = filtered_message['token_address']
                        pair_address = filtered_message['pair_address']

                        if maker_address not in track_wallets:
                            continue

                        protocol_map = {
                            'Pump V1': {
                                'sell': lambda: sell_token('pf', token_name, token_address, max_slippage),
                                'buy': lambda: buy_token('pf', token_name, token_address, sol_in, max_slippage)
                            },
                            'Raydium V4': {
                                'sell': lambda: sell_token('ra', token_name, pair_address, max_slippage),
                                # 'buy': lambda: sell_token('ra', token_name, token_address, max_slippage),
                            }
                        }

                        perform_action = protocol_map.get(protocol, {}).get(transaction_type)

                        if not perform_action:
                            print(f'[{datetime.now()}] Not supported {transaction_type.upper()}: {protocol}! "{token_name}" : {token_address}')

                            continue

                        await perform_action()
        except websockets.exceptions.ConnectionClosedError as e:
            print(f'[{datetime.now()}] Connection closed: {e}. Trying to reconnect in 5 seconds...')

            refresh_access_token()

            await asyncio.sleep(5)
        except Exception as e:
            print(f'[{datetime.now()}] Error: {e}!')

            break


if __name__ == '__main__':
    refresh_access_token()

    asyncio.run(connect())
