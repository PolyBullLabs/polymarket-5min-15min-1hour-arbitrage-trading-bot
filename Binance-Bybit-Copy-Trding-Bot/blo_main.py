import asyncio
import json
import time
import hmac
import base64
import hashlib
import websockets
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
from blofin.client import BloFinClient
from blo_follwers import place_buy_order,place_sell_order
# 🔑 환경변수
load_dotenv(dotenv_path=".env", override=True)
API_KEY = os.getenv("MASTER_API_KEY_BLO")
API_SECRET = os.getenv("MASTER_API_SECRET_BLO")
PASSPHRASE = os.getenv("passphrase")

client = BloFinClient(API_KEY, API_SECRET, PASSPHRASE)

def to_kst(ms_timestamp):
    dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=timezone.utc) + timedelta(hours=9)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def sign_ws_login(secret, path="/users/self/verify", method="GET"):
    timestamp = str(int(time.time() * 1000))
    nonce = timestamp
    msg = f"{path}{method}{timestamp}{nonce}"
    hex_signature = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest().encode()
    return base64.b64encode(hex_signature).decode(), timestamp, nonce

async def send_heartbeat(ws):
    while True:
        try:
            await ws.send(json.dumps({"op": "ping"}))
            await asyncio.sleep(25)
        except:
            break
 
def get_position_action(inst_id, side):
    try:
        positions = client.trading.get_positions(inst_id=inst_id)
        pos_amt = 0
        for p in positions.get("data", []):
            amt = float(p.get("pos", 0))
            if amt != 0:
                pos_amt = amt
        
        if pos_amt > 0:
            return "LONG 진입" if side == "BUY" else "롱 청산"
        elif pos_amt < 0:
            return "숏 청산" if side == "BUY" else "SHORT 진입"
        else:
            return "포지션 청산 완료"
    except:
        return "동작 판별 실패"

async def listen_trades():
    uri = "wss://openapi.blofin.com/ws/private"
    async with websockets.connect(uri) as ws:
        sign, timestamp, nonce = sign_ws_login(API_SECRET)
        await ws.send(json.dumps({
            "op": "login",
            "args": [{
                "apiKey": API_KEY,
                "passphrase": PASSPHRASE,
                "timestamp": timestamp,
                "sign": sign,
                "nonce": nonce
            }]
        }))
        print("[✅] WebSocket 로그인 요청 전송")

        while True:
            login_resp = json.loads(await ws.recv())
            if login_resp.get("event") == "login":
                print("[✅] 로그인 성공")
                break

        await ws.send(json.dumps({
            "op": "subscribe",
            "args": [{"channel": "orders", "instType": "SWAP"}]
        }))
        print("[✅] 주문 채널 구독 완료")
        asyncio.create_task(send_heartbeat(ws))

        latest_status = {}

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)

                if "data" in data:
                   
                    for order in data["data"]:
                        print(order)
                        order_id = order.get("orderId")
                        status = order.get("state", "").upper()
                        if latest_status.get(order_id) == status:
                            continue
                        latest_status[order_id] = status

                        inst_id = order.get("instId")
                        side = order.get("side", "N/A").upper()
                        position = order.get("reduceOnly","false")
                        qty = order.get("size", "0")
                        aver = order.get("averagePrice","0")
                        price = order.get("avgPx") or order.get("fillPx") or order.get("price", "0")
                        order_id = order.get("orderId")
                        marginMode = order.get("marginMode")
                        leverage = order.get("leverage")
                        positionSide = order.get("positionSide")
                        order_type = order.get("orderType")
                        if float(price) == 0.0:
                            try:
                                detail = client.trading.get_order_details(inst_id=inst_id, order_id=order_id)
                                price = detail["data"][0].get("avgPx") or detail["data"][0].get("fillPx") or price
                            except:
                                pass

                        update_time = order.get("uTime") or order.get("cTime") or int(time.time() * 1000)

                        if position == "false":
                           pos = "진입"
                        else: 
                            pos = "청산"    
                        if status == "FILLED":
                            if pos =="진입":
                                print(f"\n[✅ 체결 완료] {to_kst(update_time)}")
                                print(f"심볼       : {inst_id}")
                                print(f"방향       : {side} | 포지션:{pos}  ")
                                print(f"수량(Qty)  : {qty} | 가격: {price}")
                                print(f"배율:{leverage}")
                                print(f"상태       : {status}")
                                place_buy_order (inst_id= inst_id,size=qty, price = price,leverage=leverage,marginMode=marginMode,position_side=positionSide,order_type=order_type)   
                            else:
                                print(f"\n[✅ 체결 완료] {to_kst(update_time)}")
                                print(f"심볼       : {inst_id}")
                                print(f"방향       : {side} | 포지션:{pos}  ")
                                print(f"수량(Qty)  : {qty} | 가격: {aver}")
                                print(f"아이디:{order_id}")
                                print(f"상태       : {status}")
                                place_sell_order(inst_id= inst_id,size=qty, price = price,marginMode=marginMode,position_side=positionSide,order_type=order_type)
            except Exception as e:
                print(f"[에러] WebSocket 수신 실패: {e}")
                break

if __name__ == "__main__":
    print("[🚀] BloFin 실시간 체결 감지 시작...")
    asyncio.run(listen_trades())
