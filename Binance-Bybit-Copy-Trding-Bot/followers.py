from binance.client import Client
from dotenv import load_dotenv
import os 

load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("MASTER_API_KEY")
api_secret = os.getenv("MASTER_API_SECRET")
MASTER_API_KEY = os.getenv("MASTER_API_KEY")
followers = [
    {
        "api_key": api_key,
        "api_secret": api_secret,
        "multiplier": 0.99  # 비율 (마스터 수량 × 비율)
    },
   
]
import time

def sync_binance_time_for_client(client):
    """각 follower Client별 시간 동기화"""
    try:
        server_time = client.get_server_time()
        server_ts = int(server_time['serverTime'])
        local_ts = int(time.time() * 1000)
        offset = server_ts - local_ts
        client.timestamp_offset = offset
        print(f"[✅ {client.API_KEY[:5]}... 시간 동기화] 오프셋: {offset}ms")
    except Exception as e:
        print(f"[ERROR] 시간 동기화 실패: {e}")


import math

def copy_trade_to_followers(symbol, side, position_side, qty, price, leverage, margin_text):
    
    for follower in followers:
        if follower["api_key"] == MASTER_API_KEY:
            print(f"[SKIP] 자기 자신 계정 복사 방지: {follower.get('name','Unknown')}")
            continue
        client = Client(follower["api_key"], follower["api_secret"])
        sync_binance_time_for_client(client)

        try:
            # 📌 마진 모드 변환
            if "CROSS" in margin_text.upper():
                margin_type_api = "CROSS"
            else:
                margin_type_api = "ISOLATED"

            # 📌 레버리지 동기화
            client.futures_change_leverage(
                symbol=symbol,
                leverage=follower.get("leverage", leverage)
            )

            # 📌 마진 모드 동기화
            try:
                client.futures_change_margin_type(symbol=symbol, marginType=margin_type_api)
            except Exception as e:
                if "No need to change" not in str(e):
                    print(f"[경고] 마진 모드 설정 실패: {follower.get('name','Unknown')} - {e}")

            # 📌 LOT_SIZE 체크
            info = client.futures_exchange_info()
            symbol_info = next((s for s in info['symbols'] if s['symbol'].upper() == symbol.upper()), None)
            if not symbol_info:
                print(f"[ERROR] {symbol} 심볼 정보를 찾을 수 없습니다.")
                continue

            step_size = float(next(f['stepSize'] for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'))
            follower_qty = math.floor(qty * follower["multiplier"] / step_size) * step_size

            # 📌 가격 검증 & 슬리피지 체크
            if price <= 0:
                print(f"[ERROR] 가격이 유효하지 않습니다: {price}")
                continue

            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            slippage = abs(current_price - price) / price
            if slippage > follower.get("slippage_limit", 0.005):
                print(f"[SKIP] {symbol} 슬리피지 {slippage:.2%} > 제한 ({follower.get('slippage_limit',0.5)*100:.1f}%)")
                continue

            # 📌 주문 실행
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=follower_qty,
                positionSide=position_side,
            )

            print(f"[✅ 카피 완료] {follower.get('name','Unknown')} - {symbol} {side} {follower_qty} @ {price} | {margin_type_api} | {leverage}배")

        except Exception as e:
            print(f"[❌ 카피 실패] {follower.get('name','Unknown')} - {symbol} | 오류: {e}")
