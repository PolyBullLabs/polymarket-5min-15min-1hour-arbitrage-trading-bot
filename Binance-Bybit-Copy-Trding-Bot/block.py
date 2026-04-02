import time
import hmac
import base64
import hashlib
import json
import asyncio
import websockets
import os
from dotenv import load_dotenv
from block_follwers import place_order,close_position
# ====== 환경 변수 ======
load_dotenv(dotenv_path=".env", override=True)
API_KEY = os.getenv("MASTER_API_KEY_BLO")
API_SECRET = os.getenv("MASTER_API_SECRET_BLO")
PASSPHRASE = os.getenv("passphrase")

WS_URL = "wss://openapi.blockfin.com/ws/private"

# ====== 로그인 서명 생성 ======
def sign_websocket_login(secret: str):
    timestamp = str(int(time.time() * 1000))
    nonce = timestamp
    method = "GET"
    path = "/users/self/verify"

    msg = f"{path}{method}{timestamp}{nonce}"
    hex_signature = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest().encode()
    signature = base64.b64encode(hex_signature).decode()
    
    return signature, timestamp, nonce

# ====== WebSocket Listener ======
async def listen_orders():
    async with websockets.connect(WS_URL) as ws:
        # 1️⃣ 로그인 요청
        sign, ts, nonce = sign_websocket_login(API_SECRET)
        login_payload = {
            "op": "login",
            "args": [{
                "apiKey": API_KEY,
                "passphrase": PASSPHRASE,
                "timestamp": ts,
                "sign": sign,
                "nonce": nonce
            }]
        }
        await ws.send(json.dumps(login_payload))
        print("[→] 로그인 요청:", login_payload)

        resp = await ws.recv()
        print("[←] 로그인 응답:", resp)

        # 2️⃣ orders 채널 구독
        sub_payload = {
            "op": "subscribe",
            "args": [{
                "channel": "orders",
                "instType": "SWAP"
            }]
        }
        await ws.send(json.dumps(sub_payload))
        print("[→] orders 채널 구독 요청:", sub_payload)

        # 3️⃣ 실시간 체결 감지
        while True:
            msg = await ws.recv()
            data = json.loads(msg)

            if "data" in data:
                for order in data["data"]:
                    inst_id = order.get("instId")
                    side = order.get("side", "").upper()
                    order_state = order.get("state", "").upper()
                    size = order.get("size", "0")
                    avg_price = order.get("averagePrice")
                    margin_mode = order.get("marginMode")
                    leverage = order.get("leverage")
                    orderType =order.get("orderType")
                    reduce_only = order.get("reduceOnly", "false")
                    price = order.get("price")
                    pnl = order.get("pnl", "0")
                    fee = order.get("fee", "0")

                    # 포지션 방향 및 액션 구분
                    if order_state == "FILLED":
                        if reduce_only == "true":
                            action = "청산"
                            close_position(inst_id = inst_id, size = size)
                        else:
                            action = "진입"
                            place_order(inst_id = inst_id, marginMode = margin_mode, side = side, orderType = orderType, price = price, size =size)
                    elif order_state == "CANCELED":
                        action = "취소"
                    else:
                        action = order_state
                    print(order)
                    print(f"\n[✅ 체결 알림]")
                    print(f"종목: {inst_id}")
                    print(f"방향: {side} | 액션: {action}")
                    print(f"수량: {size} | 평균가: {avg_price}")
                    print(f"마진모드: {margin_mode} | 레버리지: {leverage}배")
                    print(f"PnL: {pnl} | 수수료: {fee}")
                    print(f"상태: {order_state}")
                    print("-" * 40)

if __name__ == "__main__":
    print("[🚀] BlockFin WebSocket 실시간 체결 감지 시작...")
    asyncio.run(listen_orders())
